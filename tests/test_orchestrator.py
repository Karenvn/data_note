from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from data_note.models import AssemblyBundle, AssemblyRecord, AssemblySelection, FlowCytometryInfo, NoteContext, TaxonomyInfo
from data_note.orchestrator import DataNoteOrchestrator
from data_note.species_summary_models import SpeciesSummary


class OrchestratorProfileTests(unittest.TestCase):
    def _build_orchestrator(self, profile_name: str) -> tuple[DataNoteOrchestrator, Mock]:
        orchestrator = DataNoteOrchestrator(profile=profile_name)

        snapshot_context = NoteContext(
            bioproject="PRJEB1",
            tax_id="9606",
            species="Example species",
            tolid="ixExamSpec1",
            assemblies_type="prim_alt",
        )
        final_context = NoteContext(
            bioproject="PRJEB1",
            tax_id="9606",
            species="Example species",
            tolid="ixExamSpec1",
            assemblies_type="prim_alt",
        )
        assembly_bundle = AssemblyBundle(
            selection=AssemblySelection(
                assemblies_type="prim_alt",
                primary=AssemblyRecord(
                    accession="GCA_123456789.1",
                    assembly_name="ixExamSpec1.1",
                    role="primary",
                ),
            )
        )

        orchestrator.taxonomy_service = Mock()
        orchestrator.taxonomy_service.build_context.return_value = TaxonomyInfo(
            tax_id="9606",
            species="Example species",
        )

        flow_cytometry_service = Mock()
        flow_cytometry_service.build_context.return_value = FlowCytometryInfo(
            flow_pg=0.73,
            flow_mb="710.00",
        )
        orchestrator.flow_cytometry_service = flow_cytometry_service

        orchestrator.assembly_workflow_service = Mock()
        orchestrator.assembly_workflow_service.build_bundle.return_value = (assembly_bundle, snapshot_context)
        orchestrator.sequencing_workflow_service = Mock()
        orchestrator.sequencing_workflow_service.build_sections.return_value = snapshot_context
        orchestrator.annotation_quality_workflow_service = Mock()
        orchestrator.annotation_quality_workflow_service.build_sections.return_value = snapshot_context
        orchestrator.render_context_builder = Mock()
        orchestrator.render_context_builder.snapshot.return_value = snapshot_context
        orchestrator.render_context_builder.build.return_value = final_context
        orchestrator.bioproject_client = Mock()
        orchestrator.bioproject_client.fetch_umbrella_project.return_value = {"study_accession": "PRJEB1"}
        orchestrator.bioproject_client.build_umbrella_project_details.return_value = {
            "bioproject": "PRJEB1",
            "tax_id": "9606",
            "species": "Example species",
        }
        orchestrator.bioproject_client.fetch_child_accessions.return_value = ["PRJEB1"]
        orchestrator.bioproject_client.fetch_parent_projects.return_value = {}
        orchestrator.species_summary_service = Mock()
        orchestrator.species_summary_service.build_summary.return_value = SpeciesSummary(
            species_taxid="9606",
            species="Example species",
            genus="Examplegenus",
            family="Exampleidae",
            intro_text="Example automatic summary.",
        )

        return orchestrator, flow_cytometry_service

    def _process_bioproject(self, profile_name: str) -> tuple[dict[str, object], Mock]:
        orchestrator, flow_cytometry_service = self._build_orchestrator(profile_name)
        with (
            patch("data_note.orchestrator.taxonomy_mapper.has_tax_id_override", return_value=False),
        ):
            result = orchestrator.process_bioproject("PRJEB1")
        return result, flow_cytometry_service

    def test_plant_profile_runs_flow_cytometry_enrichment(self) -> None:
        result, flow_cytometry_service = self._process_bioproject("plant")

        self.assertEqual(result["species"], "Example species")
        flow_cytometry_service.build_context.assert_called_once_with("Example species")

    def test_darwin_profile_skips_flow_cytometry_enrichment(self) -> None:
        result, flow_cytometry_service = self._process_bioproject("darwin")

        self.assertEqual(result["species"], "Example species")
        flow_cytometry_service.build_context.assert_not_called()


if __name__ == "__main__":
    unittest.main()
