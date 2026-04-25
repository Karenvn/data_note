from __future__ import annotations

from typing import Any
import xml.etree.ElementTree as ET

from .ncbi_datasets_client import NcbiDatasetsClient, RETRY_STATUS_CODES, safe_ncbi_request
from .ncbi_organelle_client import NcbiOrganelleClient
from .ncbi_taxonomy_client import NcbiTaxonomyClient


def parse_ncbi_tax_xml(response_content: bytes | str) -> dict[str, Any]:
    root = ET.fromstring(response_content)
    lineage: list[str] = []
    ranks = {
        "class": None,
        "family": None,
        "order": None,
        "phylum": None,
        "species": None,
        "genus": None,
    }
    for taxon in root.iter("Taxon"):
        rank = taxon.findtext("Rank")
        scientific_name = taxon.findtext("ScientificName")
        if rank in ranks:
            ranks[rank] = scientific_name
        lineage_ex = taxon.find("LineageEx")
        if lineage_ex is not None:
            lineage = [
                name
                for name in (element.findtext("ScientificName") for element in lineage_ex)
                if name
            ]
    if lineage and lineage[0] == "cellular organisms":
        lineage = lineage[1:]
    return {"lineage": "; ".join(lineage), **ranks}


def get_taxonomy_lineage_and_ranks(taxid: str) -> dict[str, Any]:
    return NcbiTaxonomyClient().fetch_lineage_and_ranks(taxid)


def get_datasets_params() -> dict[str, str]:
    return NcbiDatasetsClient.get_datasets_params()


def fetch_and_extract_data(accession: str) -> dict[str, Any] | None:
    return NcbiDatasetsClient().fetch_primary_assembly_info(accession)


def extract_linked_assemblies(report: dict[str, Any]) -> list[str]:
    return NcbiDatasetsClient.extract_linked_assemblies(report)


def fetch_prim_assembly_info(accession: str) -> dict[str, Any] | None:
    return NcbiDatasetsClient().fetch_primary_assembly_info(accession)


def fetch_assembly_info(hap1_accession: str, hap2_accession: str) -> dict[str, Any]:
    return NcbiDatasetsClient().fetch_haplotype_assembly_info(hap1_accession, hap2_accession)


def get_organelle_info(accession: str) -> dict[str, Any]:
    return NcbiOrganelleClient().fetch_organelle_info(accession)


def format_organelle_text(organelle_info: dict[str, Any]) -> dict[str, str]:
    return NcbiOrganelleClient.format_organelle_text(organelle_info)


def get_organelle_template_data(accession: str) -> dict[str, Any]:
    return NcbiOrganelleClient().fetch_organelle_template_data(accession)


def get_organelle_table(accession: str) -> list[dict[str, Any]]:
    return NcbiOrganelleClient().fetch_organelle_table(accession)


__all__ = [
    "NcbiDatasetsClient",
    "NcbiOrganelleClient",
    "NcbiTaxonomyClient",
    "RETRY_STATUS_CODES",
    "extract_linked_assemblies",
    "fetch_and_extract_data",
    "fetch_assembly_info",
    "fetch_prim_assembly_info",
    "format_organelle_text",
    "get_datasets_params",
    "get_organelle_info",
    "get_organelle_table",
    "get_organelle_template_data",
    "get_taxonomy_lineage_and_ranks",
    "parse_ncbi_tax_xml",
    "safe_ncbi_request",
]
