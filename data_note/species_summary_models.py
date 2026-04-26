from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class GenomeAssemblyReport:
    accession: str
    species: str
    assembly_name: str = ""
    submitter: str = ""
    level: str = ""
    refseq_category: str = "na"

    @classmethod
    def from_dataset_report(cls, report: Mapping[str, Any]) -> "GenomeAssemblyReport":
        assembly_info = report.get("assembly_info", {}) or {}
        organism = report.get("organism", {}) or {}
        submitter = str(report.get("submitter") or assembly_info.get("submitter") or "").strip()
        return cls(
            accession=str(report.get("accession") or ""),
            species=str(organism.get("organism_name") or ""),
            assembly_name=str(report.get("assembly_name") or assembly_info.get("assembly_name") or ""),
            submitter=submitter.title(),
            level=str(assembly_info.get("assembly_level") or "").lower(),
            refseq_category=str(assembly_info.get("refseq_category") or "na"),
        )


@dataclass(slots=True)
class GbifFacetCount:
    code: str
    label: str
    count: int


@dataclass(slots=True)
class GbifDistributionSummary:
    usage_key: str
    record_count: int = 0
    countries: list[GbifFacetCount] = field(default_factory=list)
    continents: list[GbifFacetCount] = field(default_factory=list)
    species_url: str | None = None


@dataclass(slots=True)
class SpeciesSummary:
    species_taxid: str
    species: str
    genus: str
    family: str
    genus_taxid: int | str | None = None
    family_taxid: int | str | None = None
    genus_genome_count: int = 0
    family_genome_count: int = 0
    refseq_category: str | None = None
    other_species_assemblies: list[GenomeAssemblyReport] = field(default_factory=list)
    gbif_usage_key: str | None = None
    gbif_distribution: GbifDistributionSummary | None = None
    intro_text: str = ""
    distribution_text: str = ""
