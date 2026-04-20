from __future__ import annotations

import unittest

from data_note.models import (
    AssemblyRecord,
    AssemblySelection,
    AuthorInfo,
    BaseNoteInfo,
    CurationBundle,
    CurationInfo,
    ExtractionInfo,
    NoteContext,
    NoteData,
    SamplingInfo,
    SequencingSummary,
)
from data_note.services.sequencing_workflow_service import SequencingWorkflowService


class _RenderContextBuilderStub:
    @staticmethod
    def snapshot(note_data: NoteData, context=None) -> NoteContext:
        merged = NoteContext.from_mapping(note_data.base.to_context_dict())
        if note_data.taxonomy is not None:
            merged.update(note_data.taxonomy.to_context_dict())
        if note_data.assembly is not None:
            merged.update(note_data.assembly.to_context_dict())
        if note_data.sequencing is not None:
            merged.update(note_data.sequencing.to_context_dict())
        if note_data.curation is not None:
            merged.update(note_data.curation.to_context_dict())
        if note_data.sampling is not None:
            merged.update(note_data.sampling.to_context_dict())
        if note_data.author is not None:
            merged.update(note_data.author.to_context_dict())
        return merged


class _SequencingServiceStub:
    def __init__(self, summary: SequencingSummary) -> None:
        self.summary = summary
        self.calls: list[tuple[object, object]] = []

    def build_context(self, bioprojects, tolid):
        self.calls.append((bioprojects, tolid))
        return self.summary


class _CurationServiceStub:
    def __init__(self, bundle: CurationBundle | None = None, *, error: Exception | None = None) -> None:
        self.bundle = bundle or CurationBundle(
            local_metadata=CurationInfo.from_legacy_parts(jira_ticket="RC-1000"),
            extraction=ExtractionInfo.from_mapping({"sanger_sample_id": "LIB1"}),
        )
        self.error = error
        self.calls: list[dict[str, object]] = []

    def build_context(self, assembly_selection, *, species, tolid, extraction_lookup_id):
        self.calls.append(
            {
                "assembly_selection": assembly_selection,
                "species": species,
                "tolid": tolid,
                "extraction_lookup_id": extraction_lookup_id,
            }
        )
        if self.error is not None:
            raise self.error
        return self.bundle


class _AuthorServiceStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_context(self, context):
        self.calls.append(dict(context))
        return AuthorInfo.from_legacy_parts(
            people=[{"given-names": "Alice", "surname": "Able", "roles": [{"credit": "Resources"}]}],
            affiliations=[{"id": "1", "organization": "Museum of Testing", "country": "GB"}],
            yaml_block="author: []",
        )


class SequencingWorkflowServiceTests(unittest.TestCase):
    def test_build_sections_populates_note_data_and_uses_child_projects(self) -> None:
        sequencing_summary = SequencingSummary.from_legacy_parts(
            technology_data={"pacbio": {"pacbio_sample_accession": "SAMEA1", "pacbio_library_name": "LIB1"}},
            seq_data={"PacBio": [{"read_accession": "ERR1"}]},
            totals={"pacbio_reads_millions": "12.3"},
            pacbio_protocols=["PROTO1"],
            run_accessions={"pacbio_run_accessions": "ERR1"},
        )
        sequencing_service = _SequencingServiceStub(sequencing_summary)
        curation_service = _CurationServiceStub()
        author_service = _AuthorServiceStub()
        service = SequencingWorkflowService(
            sequencing_service=sequencing_service,
            curation_service=curation_service,
            author_service=author_service,
            render_context_builder=_RenderContextBuilderStub(),
            biosample_dict_builder=lambda technology_data: (
                {"pacbio_collector": "Collector A"},
                {"rna_collector": "Collector B"},
                {"hic_collector": "Collector C"},
                {"isoseq_collector": "Collector D"},
            ),
            progress_printer=lambda message: None,
        )

        note_data = NoteData(base=BaseNoteInfo.from_mapping({"bioproject": "PRJEB1", "tolid": "ixExample1"}))
        assembly_selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )

        context = service.build_sections(
            note_data,
            bioproject="PRJEB1",
            child_accessions=["PRJEB1A", "PRJEB1B"],
            species="Example species",
            assembly_selection=assembly_selection,
            tolid="ixExample1",
        )

        self.assertEqual(sequencing_service.calls, [(["PRJEB1A", "PRJEB1B"], "ixExample1")])
        self.assertEqual(curation_service.calls[0]["extraction_lookup_id"], "LIB1")
        self.assertIs(note_data.sequencing, sequencing_summary)
        self.assertIsInstance(note_data.sampling, SamplingInfo)
        self.assertEqual(note_data.sampling.pacbio.collector, "Collector A")
        self.assertIsNotNone(note_data.author)
        self.assertEqual(context["jira"], "RC-1000")
        self.assertEqual(context["pacbio_collector"], "Collector A")
        self.assertEqual(context["author_people"][0]["given-names"], "Alice")

    def test_build_sections_logs_curation_failure_and_continues(self) -> None:
        sequencing_summary = SequencingSummary.from_legacy_parts(
            technology_data={"pacbio": {"pacbio_sample_accession": "SAMEA1"}},
            seq_data={"PacBio": [{"read_accession": "ERR1"}]},
            totals={"pacbio_reads_millions": "12.3"},
            pacbio_protocols=[],
            run_accessions={"pacbio_run_accessions": "ERR1"},
        )
        warnings: list[tuple[object, ...]] = []
        service = SequencingWorkflowService(
            sequencing_service=_SequencingServiceStub(sequencing_summary),
            curation_service=_CurationServiceStub(error=RuntimeError("curation failed")),
            author_service=_AuthorServiceStub(),
            render_context_builder=_RenderContextBuilderStub(),
            biosample_dict_builder=lambda technology_data: ({}, {}, {}, {}),
            warning_logger=lambda *args: warnings.append(args),
            progress_printer=lambda message: None,
        )

        note_data = NoteData(base=BaseNoteInfo.from_mapping({"bioproject": "PRJEB1", "tolid": "ixExample1"}))
        assembly_selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )

        context = service.build_sections(
            note_data,
            bioproject="PRJEB1",
            child_accessions=None,
            species="Example species",
            assembly_selection=assembly_selection,
            tolid="ixExample1",
        )

        self.assertEqual(warnings[0][0], "Failed to process curation data for %r: %s")
        self.assertEqual(warnings[0][1], "PRJEB1")
        self.assertIsNone(note_data.curation)
        self.assertIsNotNone(note_data.author)
        self.assertNotIn("jira", context)


if __name__ == "__main__":
    unittest.main()
