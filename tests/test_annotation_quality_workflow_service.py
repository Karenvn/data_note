from __future__ import annotations

import os
import unittest

from data_note.models import (
    AnnotationInfo,
    AssemblyBundle,
    AssemblyRecord,
    AssemblySelection,
    BaseNoteInfo,
    NoteContext,
    NoteData,
    QualityMetrics,
    TaxonomyInfo,
)
from data_note.services.annotation_quality_workflow_service import AnnotationQualityWorkflowService


class _RenderContextBuilderStub:
    @staticmethod
    def snapshot(note_data: NoteData, context=None) -> NoteContext:
        merged = NoteContext.from_mapping(note_data.base.to_context_dict())
        if note_data.taxonomy is not None:
            merged.update(note_data.taxonomy.to_context_dict())
        if note_data.assembly is not None:
            merged.update(note_data.assembly.to_context_dict())
        if note_data.annotation is not None:
            merged.update(note_data.annotation.to_context_dict())
        if note_data.quality is not None:
            merged.update(note_data.quality.to_context_dict())
        return merged


class _AnnotationServiceStub:
    def __init__(self, annotation: AnnotationInfo | None = None, *, error: Exception | None = None) -> None:
        self.annotation = annotation or AnnotationInfo.from_mapping({"ensembl_annotation_url": "https://ensembl.example/1"})
        self.error = error
        self.calls: list[tuple[object, object, object]] = []

    def build_context(self, assembly_accession, species, tax_id):
        self.calls.append((assembly_accession, species, tax_id))
        if self.error is not None:
            raise self.error
        return self.annotation


class _ServerDataServiceStub:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def build_context(self, assemblies_type, tolid):
        self.calls.append((assemblies_type, tolid))
        return QualityMetrics.from_legacy_parts(
            genomescope={"gscope_size": "512.3"},
            merqury={"prim_QV": 47.0},
        )


class AnnotationQualityWorkflowServiceTests(unittest.TestCase):
    def test_build_sections_populates_annotation_and_quality(self) -> None:
        annotation_service = _AnnotationServiceStub(
            AnnotationInfo.from_mapping({"ensembl_annotation_url": "https://ensembl.example/1", "genes": "12345"})
        )
        server_data_service = _ServerDataServiceStub()
        messages: list[str] = []
        service = AnnotationQualityWorkflowService(
            annotation_service=annotation_service,
            server_data_service=server_data_service,
            render_context_builder=_RenderContextBuilderStub(),
            progress_printer=messages.append,
        )
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping({"bioproject": "PRJEB1", "tolid": "ixExample1"}),
            taxonomy=TaxonomyInfo(tax_id="9606", species="Example species", lineage="Eukaryota"),
        )
        assembly_bundle = AssemblyBundle(
            selection=AssemblySelection(
                assemblies_type="prim_alt",
                primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
            )
        )

        context = service.build_sections(
            note_data,
            bioproject="PRJEB1",
            species="Example species",
            assembly_bundle=assembly_bundle,
            tax_id="9606",
        )

        self.assertEqual(messages[0], "Checking for Ensembl annotation...")
        self.assertEqual(annotation_service.calls, [("GCA_1.1", "Example species", "9606")])
        self.assertEqual(server_data_service.calls, [("prim_alt", "ixExample1")])
        self.assertEqual(note_data.annotation.ensembl_annotation_url, "https://ensembl.example/1")
        self.assertEqual(note_data.quality.genomescope.size_mb, "512.3")
        self.assertEqual(context["ensembl_annotation_url"], "https://ensembl.example/1")
        self.assertEqual(context["gscope_size"], "512.3")

    def test_build_sections_handles_empty_annotation_and_exception(self) -> None:
        server_data_service = _ServerDataServiceStub()
        messages: list[str] = []
        service = AnnotationQualityWorkflowService(
            annotation_service=_AnnotationServiceStub(error=RuntimeError("ensembl unavailable")),
            server_data_service=server_data_service,
            render_context_builder=_RenderContextBuilderStub(),
            progress_printer=messages.append,
            warning_logger=messages.append,
        )
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping({"bioproject": "PRJEB1", "tolid": "ixExample1"}),
            taxonomy=TaxonomyInfo(tax_id="9606", species="Example species", lineage="Eukaryota"),
        )
        assembly_bundle = AssemblyBundle(
            selection=AssemblySelection(
                assemblies_type="hap_asm",
                hap1=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.hap1.1", role="hap1"),
            )
        )

        context = service.build_sections(
            note_data,
            bioproject="PRJEB1",
            species="Example species",
            assembly_bundle=assembly_bundle,
            tax_id="9606",
        )

        self.assertIn("Warning: Ensembl fetch failed for PRJEB1 (hap_asm): ensembl unavailable", messages)
        self.assertIsNone(note_data.annotation)
        self.assertEqual(server_data_service.calls, [("hap_asm", "ixExample1")])
        self.assertNotIn("ensembl_annotation_url", context)
        self.assertEqual(context["gscope_size"], "512.3")

    def test_build_sections_emits_debug_annotation_message_when_enabled(self) -> None:
        annotation_service = _AnnotationServiceStub(
            AnnotationInfo.from_mapping({"ensembl_annotation_url": "https://ensembl.example/1"})
        )
        server_data_service = _ServerDataServiceStub()
        messages: list[str] = []
        service = AnnotationQualityWorkflowService(
            annotation_service=annotation_service,
            server_data_service=server_data_service,
            render_context_builder=_RenderContextBuilderStub(),
            progress_printer=messages.append,
        )
        note_data = NoteData(base=BaseNoteInfo.from_mapping({"tolid": "ixExample1"}))
        assembly_bundle = AssemblyBundle(
            selection=AssemblySelection(
                assemblies_type="prim_alt",
                primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
            )
        )

        old_value = os.environ.get("GN_DEBUG_ENSEMBL")
        os.environ["GN_DEBUG_ENSEMBL"] = "1"
        try:
            service.build_sections(
                note_data,
                bioproject="PRJEB1",
                species="Example species",
                assembly_bundle=assembly_bundle,
                tax_id="9606",
            )
        finally:
            if old_value is None:
                os.environ.pop("GN_DEBUG_ENSEMBL", None)
            else:
                os.environ["GN_DEBUG_ENSEMBL"] = old_value

        self.assertIn("Ensembl annotation: https://ensembl.example/1", messages)


if __name__ == "__main__":
    unittest.main()
