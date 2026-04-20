from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..models import AssemblyDatasetRecord, AssemblyDatasetsInfo, AssemblySelection
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
        assembly_selection: AssemblySelection,
    ) -> AssemblyDatasetsInfo:
        if assembly_selection.assemblies_type == "prim_alt":
            return self._build_primary_context(assembly_selection)
        if assembly_selection.assemblies_type == "hap_asm":
            return self._build_haplotype_context(assembly_selection)
        return AssemblyDatasetsInfo(assemblies_type=assembly_selection.assemblies_type)

    def _build_primary_context(self, assembly_selection: AssemblySelection) -> AssemblyDatasetsInfo:
        if assembly_selection.primary is None:
            return AssemblyDatasetsInfo(assemblies_type="prim_alt")

        prim_accession = assembly_selection.primary.accession
        primary_fields = self.primary_info_fetcher(prim_accession) or {}
        shared_fields: dict[str, Any] = {
            "organelle_data": self.organelle_template_fetcher(prim_accession),
        }
        try:
            shared_fields.update(self.organelle_info_fetcher(prim_accession))
        except Exception as exc:
            print(f"Warning: organelle fetch failed for {prim_accession}: {exc}")
            shared_fields["organelle_error"] = str(exc)
        primary_fields["longest_scaffold_length"] = self.longest_scaffold_fetcher(prim_accession)
        return AssemblyDatasetsInfo(
            assemblies_type="prim_alt",
            primary=AssemblyDatasetRecord.from_mapping(primary_fields),
            shared_fields=shared_fields,
        )

    def _build_haplotype_context(self, assembly_selection: AssemblySelection) -> AssemblyDatasetsInfo:
        if assembly_selection.hap1 is None or assembly_selection.hap2 is None:
            return AssemblyDatasetsInfo(assemblies_type="hap_asm")

        hap1_accession = assembly_selection.hap1.accession
        hap2_accession = assembly_selection.hap2.accession

        combined_fields = self.haplotype_info_fetcher(hap1_accession, hap2_accession) or {}
        shared_fields: dict[str, Any] = {
            "organelle_data": self.organelle_template_fetcher(hap1_accession),
        }
        try:
            shared_fields.update(self.organelle_info_fetcher(hap1_accession))
        except Exception as exc:
            print(f"Warning: organelle fetch failed for {hap1_accession}: {exc}")
            shared_fields["organelle_error"] = str(exc)
        combined_fields["hap1_longest_scaffold_length"] = self.longest_scaffold_fetcher(hap1_accession)
        combined_fields["hap2_longest_scaffold_length"] = self.longest_scaffold_fetcher(hap2_accession)
        return AssemblyDatasetsInfo(
            assemblies_type="hap_asm",
            hap1=AssemblyDatasetRecord.from_mapping(combined_fields, prefix="hap1_"),
            hap2=AssemblyDatasetRecord.from_mapping(combined_fields, prefix="hap2_"),
            shared_fields={
                **shared_fields,
                **{
                    key: value
                    for key, value in combined_fields.items()
                    if not key.startswith("hap1_") and not key.startswith("hap2_")
                },
            },
        )
