from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
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
    MetagenomeService,
    NcbiDatasetsService,
    BoldResultService,
    OrganelleProvenanceService,
    ProjectProvenanceService,
    RenderContextBuilder,
    RenderingService,
    SequencingService,
    SequencingWorkflowService,
    ServerDataService,
    SoftwareVersionService,
    TaxonomyService,
)
from .species_summary_service import SpeciesSummaryService
from . import taxonomy_mapper
from .bioproject_client import BioprojectClient
from .io_utils import dict_to_csv, dict_to_json, read_bioprojects_from_file, read_bioprojects_input
from .profiles import ProgrammeProfile, get_profile


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProcessedGenomeNote:
    context: dict[str, Any]
    note_data: NoteData


def _default_corrections_file() -> str:
    assets_root = os.getenv("DATA_NOTE_GN_ASSETS") or os.getenv("DATA_NOTE_SERVER_DATA")
    if assets_root:
        return str(Path(assets_root).expanduser() / "text_corrections.json")
    return str(Path.home() / "gn_assets" / "text_corrections.json")


class DataNoteOrchestrator:
    FLOW_IDENTIFIER_FIELDS = (
        "pacbio_specimen_id",
        "hic_specimen_id",
        "rna_specimen_id",
        "isoseq_specimen_id",
        "tolid",
        "pacbio_tolid",
        "hic_tolid",
        "rna_tolid",
        "isoseq_tolid",
    )

    def __init__(
        self,
        profile: ProgrammeProfile | str | None = None,
        include_gbif_distribution: bool = False,
        include_bold_bin: bool = False,
        include_bold_barcode: bool = False,
        sequencing_source: str = "public-with-portal",
        illumina_count_unit: str = "read_pairs",
        assembly_selection_input: AssemblySelectionInput | None = None,
    ) -> None:
        Entrez.email = os.getenv("ENTREZ_EMAIL", "default_email")
        Entrez.api_key = os.getenv("ENTREZ_API_KEY", "default_api_key")
        self.profile = profile if isinstance(profile, ProgrammeProfile) else get_profile(profile)
        self.include_gbif_distribution = include_gbif_distribution
        self.include_bold_bin = include_bold_bin
        self.include_bold_barcode = include_bold_barcode
        self.sequencing_source = sequencing_source
        self.illumina_count_unit = illumina_count_unit
        self.assembly_selection_input = assembly_selection_input

        self.bioproject_client = BioprojectClient()
        self.annotation_service = AnnotationService()
        self.author_service = AuthorService()
        self.bold_result_service = BoldResultService()
        self.assembly_service = AssemblyService(
            bioproject_client=self.bioproject_client,
            selection_input=self.assembly_selection_input,
        )
        self.btk_service = BtkService()
        self.chromosome_service = ChromosomeService()
        self.curation_service = CurationService()
        self.flow_cytometry_service = FlowCytometryService()
        self.metagenome_service = MetagenomeService()
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
        self.sequencing_service = SequencingService(
            sequencing_source=self.sequencing_source,
            illumina_count_unit=self.illumina_count_unit,
        )
        self.sequencing_workflow_service = SequencingWorkflowService(
            sequencing_service=self.sequencing_service,
            curation_service=self.curation_service,
            author_service=self.author_service,
            render_context_builder=self.render_context_builder,
        )
        self.server_data_service = ServerDataService()
        self.software_version_service = SoftwareVersionService()
        self.organelle_provenance_service = OrganelleProvenanceService()
        self.project_provenance_service = ProjectProvenanceService()
        self.species_summary_service = SpeciesSummaryService()
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

    @staticmethod
    def write_context_json(context: dict[str, Any], json_path: str) -> None:
        dict_to_json(context, json_path)

    @staticmethod
    def write_note_data_json(note_data: NoteData, json_path: str) -> None:
        dict_to_json(note_data, json_path)

    def process_bioproject(self, bioproject: str) -> dict[str, Any]:
        return self.process_bioproject_result(bioproject).context

    def process_bioproject_result(self, bioproject: str) -> ProcessedGenomeNote:
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
        child_accessions = self.bioproject_client.fetch_child_accessions(umbrella_data)
        note_data.base.child_bioprojects = child_accessions
        note_data.base.update(self.bioproject_client.fetch_parent_projects(bioproject))

        assembly_bundle, context = self.assembly_workflow_service.build_bundle(
            note_data,
            umbrella_data,
            tax_id,
            child_accessions=child_accessions,
        )
        assembly_selection = assembly_bundle.selection
        assemblies_type = assembly_bundle.assemblies_type

        tolid = context.tolid
        note_data.base.update(
            self.project_provenance_service.build_context(
                bioproject,
                tolid=tolid,
                species=species,
            )
        )
        try:
            species_summary = self.species_summary_service.build_summary(
                tax_id,
                assembly_selection,
                tolid=tolid,
                include_distribution=self.include_gbif_distribution,
                include_bold_bin=self.include_bold_bin,
                common_name=context.get("common_name"),
            )
            note_data.base.auto_text = species_summary.intro_text
            note_data.base.distribution_text = species_summary.distribution_text or None
        except Exception as exc:
            logger.warning("Auto intro failed for %s: %s", bioproject, exc)
            note_data.base.extras["auto_text_error"] = str(exc)
            note_data.base.auto_text = ""
            note_data.base.distribution_text = ""

        if self.include_bold_barcode:
            try:
                note_data.base.barcode_text = self.bold_result_service.build_text(
                    assembly_selection.preferred_accession(),
                    species,
                )
            except Exception as exc:
                logger.warning("Automated BOLD result generation failed for %s: %s", bioproject, exc)
                note_data.base.extras["barcode_text_error"] = str(exc)
                note_data.base.barcode_text = ""

        context = self.sequencing_workflow_service.build_sections(
            note_data,
            bioproject=bioproject,
            child_accessions=child_accessions,
            species=species,
            assembly_selection=assembly_selection,
            tolid=tolid,
        )

        if self.profile.uses_flow_cytometry():
            try:
                note_data.flow_cytometry = self.flow_cytometry_service.build_context(
                    species,
                    identifier_candidates=self._flow_identifier_candidates(context),
                    family_name=context.get("family"),
                )
            except Exception as exc:
                logger.warning("Failed to process flow cytometry data for %r: %s", species, exc)
            context = self.render_context_builder.snapshot(note_data)

        context = self.annotation_quality_workflow_service.build_sections(
            note_data,
            bioproject=bioproject,
            species=species,
            assembly_bundle=assembly_bundle,
            tax_id=context.tax_id,
        )

        software_versions = self.software_version_service.build_context(tolid)
        if software_versions:
            note_data.extra_sections.append(software_versions)
            context = self.render_context_builder.snapshot(note_data)

        organelle_provenance = self.organelle_provenance_service.build_context(tolid)
        if organelle_provenance:
            note_data.extra_sections.append(organelle_provenance)
            context = self.render_context_builder.snapshot(note_data)

        if self.profile.name == "asg":
            metagenome_context = self.metagenome_service.build_context(tolid)
            if metagenome_context:
                note_data.extra_sections.append(metagenome_context)
                context = self.render_context_builder.snapshot(note_data)

        corrections_file = os.getenv(
            "DATA_NOTE_CORRECTIONS_FILE",
            _default_corrections_file(),
        )
        context = self.render_context_builder.build(
            note_data,
            self.profile,
            corrections_file=corrections_file,
        )

        final_context = context.to_dict()
        return ProcessedGenomeNote(context=final_context, note_data=note_data)

    def write_note(self, template_file: str, context: dict[str, Any]) -> str:
        return self.rendering_service.write_note(template_file, context, self.profile)

    @classmethod
    def _flow_identifier_candidates(cls, context: Any) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for field in cls.FLOW_IDENTIFIER_FIELDS:
            value = context.get(field)
            cleaned = str(value).strip() if value is not None else ""
            if not cleaned:
                continue
            folded = cleaned.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            candidates.append(cleaned)
        return candidates
