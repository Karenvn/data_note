from __future__ import annotations

import logging
import os
from typing import Any

from Bio import Entrez

from .models import NoteContext
from .services import (
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
from .table_rows import build_all_tables


KNOWN_TOLID_FIX = {
    "GCA_945910005.1": "ipIsoGram3",
}


class DataNoteOrchestrator:
    def __init__(self) -> None:
        Entrez.email = os.getenv("ENTREZ_EMAIL", "default_email")
        Entrez.api_key = os.getenv("ENTREZ_API_KEY", "default_api_key")

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

        asm_dict = self.fetch_assembly_data(umbrella_data, tax_id, child_accessions)
        print("These are the assemblies selected ", asm_dict)
        context.update(asm_dict)
        context.update(get_parent_bioprojects(bioproject))

        try:
            context.update(self.process_local_data(context.get("assemblies_type"), species, context))
        except Exception as exc:
            print(f"Warning: local data fetch failed for {bioproject}: {exc}")

        context.set_formatted_parent_projects()

        assemblies_type = context.assemblies_type
        assembly_accessions = context.assembly_accessions()

        datasets_ok = True
        try:
            ncbi_context = self.fetch_ncbi_datasets(assemblies_type, assembly_accessions)
            if assemblies_type == "prim_alt":
                context.update(ncbi_context)
                context.assembly_name = context["prim_assembly_name"]
            elif assemblies_type == "hap_asm":
                context.update(ncbi_context)
                context.assembly_name = context["hap1_assembly_name"]
        except Exception as exc:
            datasets_ok = False
            context["ncbi_datasets_error"] = str(exc)
            print(f"Warning: NCBI datasets fetch failed for {bioproject} ({assemblies_type}): {exc}")

        context.ensure_tolid()

        if datasets_ok:
            try:
                context.update(self.process_chromosomes(assembly_accessions, assemblies_type, context))
            except Exception as exc:
                print(f"Warning: chromosome processing failed for {bioproject} ({assemblies_type}): {exc}")

        if datasets_ok and context["assemblies_type"] == "prim_alt":
            info = {
                "assemblies_type": "prim_alt",
                "prim_accession": context["prim_accession"],
                "genome_length_unrounded": context.get("genome_length_unrounded"),
            }
            context.update(calculate_percentage_assembled(info))
        elif datasets_ok and context["assemblies_type"] == "hap_asm":
            info = {
                "assemblies_type": "hap_asm",
                "hap1_accession": context["hap1_accession"],
                "hap2_accession": context["hap2_accession"],
                "hap1_genome_length_unrounded": context.get("hap1_genome_length_unrounded"),
                "hap2_genome_length_unrounded": context.get("hap2_genome_length_unrounded"),
            }
            context.update(calculate_percentage_assembled(info))

        context.apply_known_tolid_fix(KNOWN_TOLID_FIX)

        tolid = context.tolid
        try:
            context.auto_text = summarise_genomes(tax_id, asm_dict, tolid, show_tables=True)
        except Exception as exc:
            print(f"Warning: auto intro failed for {bioproject}: {exc}")
            context["auto_text_error"] = str(exc)
            context.auto_text = ""

        print(f"The TOLID is {tolid}")
        sequencing_projects = child_accessions or [bioproject]
        context.update(self.process_sequencing_workflow(sequencing_projects, tolid))
        pacbio_library_name = context.get("technology_data", {}).get("pacbio", {}).get("pacbio_library_name")
        extraction_lookup_id = pacbio_library_name or tolid

        try:
            context.update(self.process_extraction_info(extraction_lookup_id))
        except Exception as exc:
            logging.warning("Failed to process extraction info for %r: %s", extraction_lookup_id, exc)

        context.update(fetch_barcoding_info(tolid))
        context.update(self.fetch_biosample_data(context.get("technology_data", {})))

        print("Checking for Ensembl annotation...")
        try:
            if assemblies_type == "prim_alt":
                res = create_ensembl_dict(context["prim_accession"], species, context.tax_id)
                print(res)
            elif assemblies_type == "hap_asm":
                res = create_ensembl_dict(context["hap1_accession"], species, context.tax_id)
                print(res)
            else:
                res = {}

            if not res:
                print(
                    f"No Ensembl annotation found for {species} / "
                    f"{context.get('prim_accession') or context.get('hap1_accession')}"
                )
            else:
                context.update(res)
                if os.environ.get("GN_DEBUG_ENSEMBL") == "1":
                    print(f"Ensembl annotation: {res['ensembl_annotation_url']}")
        except Exception as exc:
            print(f"Warning: Ensembl fetch failed for {bioproject} ({assemblies_type}): {exc}")

        if assemblies_type in ["prim_alt", "hap_asm"]:
            context.update(self.fetch_btk_info(assemblies_type, assembly_accessions))

        context.update(self.process_server_data(assemblies_type, context["tolid"]))

        corrections_file = os.getenv(
            "DATA_NOTE_CORRECTIONS_FILE",
            os.path.expanduser("~/genome_note_templates/text_corrections.json"),
        )
        load_and_apply_corrections(context, corrections_file)

        context["ebp_metric"] = calc_ebp_metric(context)

        context = build_all_tables(context)
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
    ) -> dict[str, Any]:
        return self.assembly_service.build_context(umbrella_data, tax_id, child_accessions=child_accessions)

    def empty_sequencing_context(self) -> dict[str, Any]:
        return self.sequencing_service.empty_context()

    def process_sequencing_workflow(self, bioprojects: Any, tolid: str) -> dict[str, Any]:
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

    def fetch_biosample_data(self, technology_data: dict[str, Any]) -> dict[str, Any]:
        print("Accessing BioSample information from BioSamples.")
        biosample_context: dict[str, Any] = {}

        pacbio_sample_dict, rna_sample_dict, hic_sample_dict, isoseq_sample_dict = create_biosample_dict(
            technology_data
        )
        if pacbio_sample_dict:
            biosample_context.update(pacbio_sample_dict)
        if rna_sample_dict:
            biosample_context.update(rna_sample_dict)
        if hic_sample_dict:
            biosample_context.update(hic_sample_dict)
        if isoseq_sample_dict:
            biosample_context.update(isoseq_sample_dict)
        return biosample_context

    def fetch_taxonomic_data(self, tax_id: str) -> dict[str, Any]:
        return self.taxonomy_service.build_context(tax_id)

    def fetch_ncbi_datasets(
        self,
        assemblies_type: str | None,
        assembly_accessions: dict[str, Any],
    ) -> dict[str, Any]:
        return self.ncbi_datasets_service.build_context(assemblies_type, assembly_accessions)

    def process_chromosomes(
        self,
        assembly_accessions: dict[str, Any],
        assemblies_type: str | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return self.chromosome_service.build_context(assembly_accessions, assemblies_type, context)

    def process_local_data(
        self,
        assemblies_type: str | None,
        species: str | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return self.local_metadata_service.build_context(assemblies_type, context, species=species)

    def fetch_btk_info(
        self,
        assemblies_type: str | None,
        assembly_accessions: dict[str, Any],
    ) -> dict[str, Any]:
        return self.btk_service.build_context(assemblies_type, assembly_accessions)

    def process_server_data(self, assemblies_type: str | None, tolid: str) -> dict[str, Any]:
        return self.server_data_service.build_context(assemblies_type, tolid)

    def write_note(self, assemblies_type: str, template_file: str, context: dict[str, Any]) -> str:
        return self.rendering_service.write_note(assemblies_type, template_file, context)
