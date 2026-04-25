from __future__ import annotations

import logging
import os
from typing import Any

from Bio import Entrez

from .models import (
    AssemblyBundle,
    AssemblySelection,
    AssemblySelectionInput,
    NoteData,
)
from .services import (
    AnnotationService,
    AnnotationQualityWorkflowService,
    AuthorService,
    AssemblyService,
    AssemblyWorkflowService,
    BtkService,
    ChromosomeService,
    CurationService,
    FlowCytometryService,
    NcbiDatasetsService,
    RenderContextBuilder,
    RenderingService,
    SequencingService,
    SequencingWorkflowService,
    ServerDataService,
    TaxonomyService,
)
from . import taxonomy_mapper
from .auto_intro import summarise_genomes
from .bioproject_client import BioprojectClient
from .io_utils import dict_to_csv, read_bioprojects_from_file, read_bioprojects_input
from .profiles import ProgrammeProfile, get_profile


KNOWN_TOLID_FIX = {
    "GCA_945910005.1": "ipIsoGram3",
}

logger = logging.getLogger(__name__)


class DataNoteOrchestrator:
    def __init__(
        self,
        profile: ProgrammeProfile | str | None = None,
        assembly_selection_input: AssemblySelectionInput | None = None,
    ) -> None:
        Entrez.email = os.getenv("ENTREZ_EMAIL", "default_email")
        Entrez.api_key = os.getenv("ENTREZ_API_KEY", "default_api_key")
        self.profile = profile if isinstance(profile, ProgrammeProfile) else get_profile(profile)
        self.assembly_selection_input = assembly_selection_input

        self.bioproject_client = BioprojectClient()
        self.annotation_service = AnnotationService()
        self.author_service = AuthorService()
        self.assembly_service = AssemblyService(
            bioproject_client=self.bioproject_client,
            selection_input=self.assembly_selection_input,
        )
        self.btk_service = BtkService()
        self.chromosome_service = ChromosomeService()
        self.curation_service = CurationService()
        self.flow_cytometry_service = FlowCytometryService()
        self.ncbi_datasets_service = NcbiDatasetsService()
        self.render_context_builder = RenderContextBuilder()
        self.assembly_workflow_service = AssemblyWorkflowService(
            assembly_service=self.assembly_service,
            ncbi_datasets_service=self.ncbi_datasets_service,
            chromosome_service=self.chromosome_service,
            btk_service=self.btk_service,
            render_context_builder=self.render_context_builder,
        )
        self.rendering_service = RenderingService()
        self.sequencing_service = SequencingService()
        self.sequencing_workflow_service = SequencingWorkflowService(
            sequencing_service=self.sequencing_service,
            curation_service=self.curation_service,
            author_service=self.author_service,
            render_context_builder=self.render_context_builder,
        )
        self.server_data_service = ServerDataService()
        self.annotation_quality_workflow_service = AnnotationQualityWorkflowService(
            annotation_service=self.annotation_service,
            server_data_service=self.server_data_service,
            render_context_builder=self.render_context_builder,
        )
        self.taxonomy_service = TaxonomyService()

    @staticmethod
    def read_bioprojects_file(file_path: str) -> list[str]:
        return read_bioprojects_from_file(file_path)

    @staticmethod
    def read_bioproject_input(input_value: str) -> list[str]:
        return read_bioprojects_input(input_value)

    @staticmethod
    def write_context_csv(context: dict[str, Any], csv_path: str) -> None:
        dict_to_csv(context, csv_path)

    def process_bioproject(self, bioproject: str) -> dict[str, Any]:
        note_data = NoteData()

        umbrella_data = self.bioproject_client.fetch_umbrella_project(bioproject)
        umbrella_project_dict = self.bioproject_client.build_umbrella_project_details(umbrella_data, bioproject)
        note_data.base.update(umbrella_project_dict)
        context = self.render_context_builder.snapshot(note_data)

        tax_id = context.tax_id or umbrella_project_dict["tax_id"]
        if taxonomy_mapper.has_tax_id_override(bioproject):
            override = taxonomy_mapper.get_tax_id_override(bioproject)
            override_tax_id = override.get("tax_id")
            if override_tax_id:
                logger.info(
                    "Using tax_id override for %s: %s -> %s (%s)",
                    bioproject,
                    tax_id,
                    override_tax_id,
                    override.get("reason"),
                )
                note_data.base.tax_id_umbrella = tax_id
                tax_id = str(override_tax_id)
                note_data.base.tax_id = tax_id

        note_data.taxonomy = self.taxonomy_service.build_context(tax_id)
        context = self.render_context_builder.snapshot(note_data)

        species = context.species
        if self.profile.uses_flow_cytometry():
            try:
                note_data.flow_cytometry = self.flow_cytometry_service.build_context(species)
            except Exception as exc:
                logger.warning("Failed to process flow cytometry data for %r: %s", species, exc)
        context = self.render_context_builder.snapshot(note_data)

        child_accessions = self.bioproject_client.fetch_child_accessions(umbrella_data)
        note_data.base.child_bioprojects = child_accessions
        note_data.base.update(self.bioproject_client.fetch_parent_projects(bioproject))

        assembly_bundle, context = self.assembly_workflow_service.build_bundle(
            note_data,
            umbrella_data,
            tax_id,
            child_accessions=child_accessions,
            known_tolid_fixes=KNOWN_TOLID_FIX,
        )
        assembly_selection = assembly_bundle.selection
        assemblies_type = assembly_bundle.assemblies_type

        tolid = context.tolid
        try:
            note_data.base.auto_text = summarise_genomes(tax_id, assembly_selection, tolid, show_tables=False)
        except Exception as exc:
            logger.warning("Auto intro failed for %s: %s", bioproject, exc)
            note_data.base.extras["auto_text_error"] = str(exc)
            note_data.base.auto_text = ""

        context = self.sequencing_workflow_service.build_sections(
            note_data,
            bioproject=bioproject,
            child_accessions=child_accessions,
            species=species,
            assembly_selection=assembly_selection,
            tolid=tolid,
        )

        context = self.annotation_quality_workflow_service.build_sections(
            note_data,
            bioproject=bioproject,
            species=species,
            assembly_bundle=assembly_bundle,
            tax_id=context.tax_id,
        )

        corrections_file = os.getenv(
            "DATA_NOTE_CORRECTIONS_FILE",
            os.path.expanduser("~/genome_note_templates/text_corrections.json"),
        )
        context = self.render_context_builder.build(
            note_data,
            self.profile,
            corrections_file=corrections_file,
            known_tolid_fixes=KNOWN_TOLID_FIX,
        )

        final_context = context.to_dict()
        return final_context

    def write_note(self, template_file: str, context: dict[str, Any]) -> str:
        return self.rendering_service.write_note(template_file, context, self.profile)
