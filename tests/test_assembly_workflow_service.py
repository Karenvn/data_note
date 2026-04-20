from __future__ import annotations

import unittest

from data_note.models import (
    AssemblyBundle,
    AssemblyRecord,
    AssemblySelection,
    BaseNoteInfo,
    ChromosomeSummary,
    NoteContext,
    NoteData,
)
from data_note.services.assembly_workflow_service import AssemblyWorkflowService


class _DatasetsStub:
    def to_context_dict(self) -> dict[str, object]:
        return {
            "assembly_level": "chromosome",
            "genome_length_unrounded": 512300000.0,
        }


class _RenderContextBuilderStub:
    def snapshot(self, note_data: NoteData, context=None) -> NoteContext:
        return self._context_for(note_data)

    def derive_note_fields(self, note_data: NoteData, *, context=None, known_tolid_fixes=None) -> NoteContext:
        note_context = self._context_for(note_data)
        note_context.set_formatted_parent_projects()
        note_context.ensure_tolid()
        if known_tolid_fixes:
            note_context.apply_known_tolid_fix(dict(known_tolid_fixes))
        note_data.base.formatted_parent_projects = note_context.formatted_parent_projects
        if note_context.tolid:
            note_data.base.tolid = note_context.tolid
        return note_context

    @staticmethod
    def _context_for(note_data: NoteData) -> NoteContext:
        context = NoteContext.from_mapping(note_data.base.to_context_dict())
        if note_data.assembly is not None:
            context.update(note_data.assembly.to_context_dict())
        return context


class AssemblyWorkflowServiceTests(unittest.TestCase):
    def test_build_bundle_populates_note_data_and_bundle(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )
        chromosome_summary = ChromosomeSummary(
            chromosome_data=[{"molecule": "1"}],
            sex_chromosomes="X",
        )
        service = AssemblyWorkflowService(
            assembly_service=type(
                "AssemblyServiceStub",
                (),
                {"build_context": lambda self, umbrella_data, tax_id, child_accessions=None: selection},
            )(),
            ncbi_datasets_service=type(
                "NcbiDatasetsServiceStub",
                (),
                {"build_context": lambda self, assembly_selection: _DatasetsStub()},
            )(),
            chromosome_service=type(
                "ChromosomeServiceStub",
                (),
                {"build_context": lambda self, assembly_selection, context: chromosome_summary},
            )(),
            btk_service=type(
                "BtkServiceStub",
                (),
                {"build_context": lambda self, assembly_selection: type('BtkStub', (), {'to_context_dict': lambda self: {'summary_accession': 'GCA_1.1'}})()},
            )(),
            render_context_builder=_RenderContextBuilderStub(),
            coverage_calculator=lambda coverage_input: {"perc_assembled": 96.4},
        )
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping(
                {
                    "bioproject": "PRJEB1",
                    "parent_projects": [{"project_name": "Parent", "accession": "PRJEB10"}],
                }
            )
        )

        bundle, context = service.build_bundle(
            note_data,
            {"study_accession": "PRJEB1"},
            "9606",
            child_accessions=["PRJEB1A"],
        )

        self.assertIsInstance(bundle, AssemblyBundle)
        self.assertIs(note_data.assembly, bundle)
        self.assertEqual(note_data.base.assemblies_type, "prim_alt")
        self.assertEqual(note_data.base.assembly_name, "ixExample1.1")
        self.assertEqual(note_data.base.formatted_parent_projects, "Parent (PRJEB10)")
        self.assertEqual(note_data.base.tolid, "ixExample1")
        self.assertEqual(bundle.coverage_fields["perc_assembled"], 96.4)
        self.assertEqual(bundle.chromosomes.sex_chromosomes, "X")
        self.assertEqual(context["tolid"], "ixExample1")

    def test_build_bundle_records_dataset_failure_and_continues(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )
        service = AssemblyWorkflowService(
            assembly_service=type(
                "AssemblyServiceStub",
                (),
                {"build_context": lambda self, umbrella_data, tax_id, child_accessions=None: selection},
            )(),
            ncbi_datasets_service=type(
                "NcbiDatasetsServiceStub",
                (),
                {"build_context": lambda self, assembly_selection: (_ for _ in ()).throw(RuntimeError("datasets unavailable"))},
            )(),
            chromosome_service=type(
                "ChromosomeServiceStub",
                (),
                {"build_context": lambda self, assembly_selection, context: ChromosomeSummary()},
            )(),
            btk_service=type(
                "BtkServiceStub",
                (),
                {"build_context": lambda self, assembly_selection: None},
            )(),
            render_context_builder=_RenderContextBuilderStub(),
            coverage_calculator=lambda coverage_input: {"perc_assembled": 96.4},
        )
        note_data = NoteData(base=BaseNoteInfo.from_mapping({"bioproject": "PRJEB1"}))

        bundle, context = service.build_bundle(
            note_data,
            {"study_accession": "PRJEB1"},
            "9606",
        )

        self.assertIsNone(bundle.datasets)
        self.assertIn("ncbi_datasets_error", note_data.base.extras)
        self.assertEqual(context["tolid"], "ixExample1")
        self.assertEqual(note_data.base.tolid, "ixExample1")


if __name__ == "__main__":
    unittest.main()
