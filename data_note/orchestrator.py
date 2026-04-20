from __future__ import annotations

import logging
import os
from typing import Any

from Bio import Entrez

from .models import (
    AssemblyBundle,
    AssemblyCoverageInput,
    AssemblyDatasetsInfo,
    AssemblySelection,
    BtkSummary,
    ChromosomeSummary,
    NoteContext,
    SamplingInfo,
    SequencingSummary,
)
from .services import (
    AuthorService,
    AssemblyService,
    BtkService,
    ChromosomeService,
    LocalMetadataService,
    NcbiDatasetsService,
    RenderingService,
    SequencingService,
    ServerDataService,
    TaxonomyService,
)
from . import taxonomy_mapper
from .auto_intro import summarise_genomes
from .calculate_metrics import calc_ebp_metric
from .fetch_bioproject_assemblies import (
    fetch_data,
    get_child_accessions_for_bioproject,
    get_parent_bioprojects,
    get_umbrella_project_details,
)
from .fetch_biosample_info import create_biosample_dict
from .fetch_ensembl_info import create_ensembl_dict
from .fetch_extraction_data import (
    fallback_fetch_from_lr_sample_prep,
    fetch_barcoding_info,
    get_sequencing_and_extraction_metadata,
)
from .io_utils import dict_to_csv, load_and_apply_corrections, read_bioprojects_from_file
from .process_chromosome_data import calculate_percentage_assembled
from .profiles import ProgrammeProfile, get_profile


KNOWN_TOLID_FIX = {
    "GCA_945910005.1": "ipIsoGram3",
}


class DataNoteOrchestrator:
    def __init__(self, profile: ProgrammeProfile | str | None = None) -> None:
        Entrez.email = os.getenv("ENTREZ_EMAIL", "default_email")
        Entrez.api_key = os.getenv("ENTREZ_API_KEY", "default_api_key")
        self.profile = profile if isinstance(profile, ProgrammeProfile) else get_profile(profile)

        self.author_service = AuthorService()
        self.assembly_service = AssemblyService()
        self.btk_service = BtkService()
        self.chromosome_service = ChromosomeService()
        self.local_metadata_service = LocalMetadataService()
        self.ncbi_datasets_service = NcbiDatasetsService()
        self.rendering_service = RenderingService()
        self.sequencing_service = SequencingService()
        self.server_data_service = ServerDataService()
        self.taxonomy_service = TaxonomyService()

    @staticmethod
    def read_bioprojects_file(file_path: str) -> list[str]:
        return read_bioprojects_from_file(file_path)

    @staticmethod
    def write_context_csv(context: dict[str, Any], csv_path: str) -> None:
        dict_to_csv(context, csv_path)

    def process_bioproject(self, bioproject: str) -> dict[str, Any]:
        context = NoteContext()

        umbrella_data = fetch_data(bioproject)
        umbrella_project_dict = get_umbrella_project_details(umbrella_data, bioproject)
        print(umbrella_project_dict)
        context.update(umbrella_project_dict)

        tax_id = context.tax_id or umbrella_project_dict["tax_id"]
        if taxonomy_mapper.has_tax_id_override(bioproject):
            override = taxonomy_mapper.get_tax_id_override(bioproject)
            override_tax_id = override.get("tax_id")
            if override_tax_id:
                print(f"  -> Using tax_id override for {bioproject}: {tax_id} -> {override_tax_id}")
                print(f"    Reason: {override.get('reason')}")
                context.tax_id_umbrella = tax_id
                tax_id = str(override_tax_id)
                context.tax_id = tax_id

        print("The tax_id for this assembly is: ", tax_id)
        context.update(self.fetch_taxonomic_data(tax_id))

        species = context.species
        child_accessions = get_child_accessions_for_bioproject(umbrella_data)
        context.child_bioprojects = child_accessions

        assembly_selection = self.fetch_assembly_data(umbrella_data, tax_id, child_accessions)
        assembly_bundle = AssemblyBundle(selection=assembly_selection)
        print("These are the assemblies selected ", assembly_bundle.selection.to_context_dict())
        context.assemblies_type = assembly_bundle.assemblies_type
        context.assembly_name = assembly_bundle.preferred_assembly_name()
        context.update(get_parent_bioprojects(bioproject))

        try:
            context.update(self.process_local_data(assembly_selection, species, context.tolid))
        except Exception as exc:
            print(f"Warning: local data fetch failed for {bioproject}: {exc}")

        context.set_formatted_parent_projects()

        assemblies_type = assembly_bundle.assemblies_type
        datasets_ok = True
        try:
            assembly_bundle.datasets = self.fetch_ncbi_datasets(assembly_selection)
        except Exception as exc:
            datasets_ok = False
            context["ncbi_datasets_error"] = str(exc)
            print(f"Warning: NCBI datasets fetch failed for {bioproject} ({assemblies_type}): {exc}")

        context.ensure_tolid()

        if datasets_ok:
            try:
                chromosome_context = context.to_dict()
                chromosome_context.update(assembly_bundle.to_context_dict())
                assembly_bundle.chromosomes = self.process_chromosomes(assembly_selection, chromosome_context)
            except Exception as exc:
                print(f"Warning: chromosome processing failed for {bioproject} ({assemblies_type}): {exc}")

        if datasets_ok and assemblies_type in {"prim_alt", "hap_asm"}:
            coverage_context = context.to_dict()
            coverage_context.update(assembly_bundle.to_context_dict())
            coverage_input = AssemblyCoverageInput.from_selection_and_context(assembly_selection, coverage_context)
            assembly_bundle.coverage_fields = calculate_percentage_assembled(coverage_input)

        if assemblies_type in ["prim_alt", "hap_asm"]:
            assembly_bundle.btk = self.fetch_btk_info(assembly_selection)

        context.update(assembly_bundle.to_context_dict())

        context.apply_known_tolid_fix(KNOWN_TOLID_FIX)

        tolid = context.tolid
        try:
            context.auto_text = summarise_genomes(tax_id, assembly_selection, tolid, show_tables=True)
        except Exception as exc:
            print(f"Warning: auto intro failed for {bioproject}: {exc}")
            context["auto_text_error"] = str(exc)
            context.auto_text = ""

        print(f"The TOLID is {tolid}")
        sequencing_projects = child_accessions or [bioproject]
        sequencing_summary = self.process_sequencing_workflow(sequencing_projects, tolid)
        context.update(sequencing_summary.to_context_dict())
        pacbio_library_name = sequencing_summary.pacbio_library_name()
        extraction_lookup_id = pacbio_library_name or tolid

        try:
            context.update(self.process_extraction_info(extraction_lookup_id))
        except Exception as exc:
            logging.warning("Failed to process extraction info for %r: %s", extraction_lookup_id, exc)

        context.update(fetch_barcoding_info(tolid))
        sampling_info = self.fetch_biosample_data(sequencing_summary.technology_data)
        context.update(sampling_info.to_context_dict())
        context.update(self.build_author_context(context))

        print("Checking for Ensembl annotation...")
        try:
            ensembl_accession = assembly_bundle.preferred_accession()
            if ensembl_accession:
                res = create_ensembl_dict(ensembl_accession, species, context.tax_id)
                print(res)
            else:
                res = {}

            if not res:
                print(
                    f"No Ensembl annotation found for {species} / "
                    f"{assembly_bundle.preferred_accession()}"
                )
            else:
                context.update(res)
                if os.environ.get("GN_DEBUG_ENSEMBL") == "1":
                    print(f"Ensembl annotation: {res['ensembl_annotation_url']}")
        except Exception as exc:
            print(f"Warning: Ensembl fetch failed for {bioproject} ({assemblies_type}): {exc}")

        context.update(self.process_server_data(assemblies_type, context["tolid"]))

        corrections_file = os.getenv(
            "DATA_NOTE_CORRECTIONS_FILE",
            os.path.expanduser("~/genome_note_templates/text_corrections.json"),
        )
        load_and_apply_corrections(context, corrections_file)

        context["ebp_metric"] = calc_ebp_metric(context)

        context = self.profile.build_tables(context)
        if not isinstance(context, NoteContext):
            context = NoteContext.from_mapping(context)

        final_context = context.to_dict()
        print(f"The context dict has {len(final_context)} key-value pairs.")
        print("Final context: ", final_context)
        return final_context

    def fetch_assembly_data(
        self,
        umbrella_data: dict[str, Any],
        tax_id: str,
        child_accessions: list[str] | None = None,
    ) -> AssemblySelection:
        return self.assembly_service.build_context(umbrella_data, tax_id, child_accessions=child_accessions)

    def empty_sequencing_context(self) -> SequencingSummary:
        return self.sequencing_service.empty_context()

    def process_sequencing_workflow(self, bioprojects: Any, tolid: str) -> SequencingSummary:
        return self.sequencing_service.build_context(bioprojects, tolid)

    def process_extraction_info(self, library_name: str | None) -> dict[str, Any]:
        extraction_context: dict[str, Any] = {}
        lookup_id = str(library_name).strip() if library_name is not None else ""
        if not lookup_id:
            return extraction_context

        seq_attrs, extraction_attrs = get_sequencing_and_extraction_metadata(lookup_id)
        if seq_attrs:
            extraction_context.update({key: value for key, value in seq_attrs.items()})

        important_fields = [
            "dna_yield_ng",
            "qubit_ngul",
            "volume_ul",
            "ratio_260_280",
            "ratio_260_230",
            "fragment_size_kb",
            "extraction_date",
        ]

        needs_fallback = False
        if not extraction_attrs:
            needs_fallback = True
        else:
            missing = [key for key in important_fields if extraction_attrs.get(key) in (None, "", float("nan"))]
            if len(missing) >= len(important_fields) - 1:
                needs_fallback = True

        if extraction_attrs:
            extraction_context.update({key: value for key, value in extraction_attrs.items()})

        def _is_missing(value: Any) -> bool:
            if value is None or value == "":
                return True
            try:
                return value != value
            except Exception:
                return False

        if needs_fallback:
            print("Extraction info incomplete or missing. Falling back to local LR_sample_prep.tsv.")
            fallback_attrs = fallback_fetch_from_lr_sample_prep(lookup_id)
            if fallback_attrs:
                for key, value in fallback_attrs.items():
                    if _is_missing(extraction_context.get(key)):
                        extraction_context[key] = value
            else:
                print(f"No fallback extraction info found for {lookup_id}.")
        elif _is_missing(extraction_context.get("gqn")):
            fallback_attrs = fallback_fetch_from_lr_sample_prep(lookup_id)
            if fallback_attrs and not _is_missing(fallback_attrs.get("gqn")):
                extraction_context["gqn"] = fallback_attrs.get("gqn")

        extraction_protocol = extraction_context.get("extraction_protocol")
        legacy_protocol = extraction_context.get("protocol")
        if _is_missing(extraction_protocol) and not _is_missing(legacy_protocol):
            extraction_context["extraction_protocol"] = legacy_protocol
        elif _is_missing(legacy_protocol) and not _is_missing(extraction_protocol):
            extraction_context["protocol"] = extraction_protocol

        if _is_missing(extraction_context.get("sanger_sample_id")):
            extraction_context["sanger_sample_id"] = lookup_id

        return extraction_context

    def fetch_biosample_data(self, technology_data: dict[str, Any]) -> SamplingInfo:
        print("Accessing BioSample information from BioSamples.")
        pacbio_sample_dict, rna_sample_dict, hic_sample_dict, isoseq_sample_dict = create_biosample_dict(
            technology_data
        )
        return SamplingInfo.from_legacy_dicts(
            pacbio=pacbio_sample_dict,
            rna=rna_sample_dict,
            hic=hic_sample_dict,
            isoseq=isoseq_sample_dict,
        )

    def build_author_context(self, context: Mapping[str, Any]) -> dict[str, Any]:
        return self.author_service.build_context(context)

    def fetch_taxonomic_data(self, tax_id: str) -> dict[str, Any]:
        return self.taxonomy_service.build_context(tax_id)

    def fetch_ncbi_datasets(
        self,
        assembly_selection: AssemblySelection,
    ) -> AssemblyDatasetsInfo:
        return self.ncbi_datasets_service.build_context(assembly_selection)

    def process_chromosomes(
        self,
        assembly_selection: AssemblySelection,
        context: dict[str, Any],
    ) -> ChromosomeSummary:
        return self.chromosome_service.build_context(assembly_selection, context)

    def process_local_data(
        self,
        assembly_selection: AssemblySelection,
        species: str | None,
        tolid: str | None,
    ) -> dict[str, Any]:
        return self.local_metadata_service.build_context(assembly_selection, tolid=tolid, species=species)

    def fetch_btk_info(
        self,
        assembly_selection: AssemblySelection,
    ) -> BtkSummary:
        return self.btk_service.build_context(assembly_selection)

    def process_server_data(self, assemblies_type: str | None, tolid: str) -> dict[str, Any]:
        return self.server_data_service.build_context(assemblies_type, tolid)

    def write_note(self, template_file: str, context: dict[str, Any]) -> str:
        return self.rendering_service.write_note(template_file, context)
