from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_ncbi_data import (
    fetch_assembly_info,
    fetch_prim_assembly_info,
    get_organelle_info,
    get_organelle_template_data,
)
from ..process_chromosome_data import get_longest_scaffold


@dataclass(slots=True)
class NcbiDatasetsService:
    primary_info_fetcher: Callable[[str], dict[str, Any]] = fetch_prim_assembly_info
    haplotype_info_fetcher: Callable[[str, str], dict[str, Any]] = fetch_assembly_info
    organelle_template_fetcher: Callable[[str], Any] = get_organelle_template_data
    organelle_info_fetcher: Callable[[str], dict[str, Any]] = get_organelle_info
    longest_scaffold_fetcher: Callable[[str], Any] = get_longest_scaffold

    def build_context(
        self,
        assemblies_type: str | None,
        assembly_accessions: dict[str, Any],
    ) -> dict[str, Any]:
        if assemblies_type == "prim_alt":
            return self._build_primary_context(assembly_accessions)
        if assemblies_type == "hap_asm":
            return self._build_haplotype_context(assembly_accessions)
        return {}

    def _build_primary_context(self, assembly_accessions: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {}
        prim_accession = assembly_accessions["prim_accession"]
        context.update(self.primary_info_fetcher(prim_accession))
        context["organelle_data"] = self.organelle_template_fetcher(prim_accession)
        try:
            context.update(self.organelle_info_fetcher(prim_accession))
        except Exception as exc:
            print(f"Warning: organelle fetch failed for {prim_accession}: {exc}")
            context["organelle_error"] = str(exc)
        context["longest_scaffold_length"] = self.longest_scaffold_fetcher(prim_accession)
        return context

    def _build_haplotype_context(self, assembly_accessions: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {}
        hap1_accession = assembly_accessions["hap1_accession"]
        hap2_accession = assembly_accessions["hap2_accession"]

        context.update(self.haplotype_info_fetcher(hap1_accession, hap2_accession))
        context["organelle_data"] = self.organelle_template_fetcher(hap1_accession)
        try:
            context.update(self.organelle_info_fetcher(hap1_accession))
        except Exception as exc:
            print(f"Warning: organelle fetch failed for {hap1_accession}: {exc}")
            context["organelle_error"] = str(exc)
        context["hap1_longest_scaffold_length"] = self.longest_scaffold_fetcher(hap1_accession)
        context["hap2_longest_scaffold_length"] = self.longest_scaffold_fetcher(hap2_accession)
        return context
