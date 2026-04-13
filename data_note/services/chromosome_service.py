from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..formatting_utils import format_sex_chromosomes
from ..process_chromosome_data import (
    combine_haplotype_chromosome_tables,
    identify_sex_chromosomes,
    prim_chromosome_table,
)


@dataclass(slots=True)
class ChromosomeService:
    primary_table_fetcher: Callable[[str], list[dict[str, Any]]] = prim_chromosome_table
    haplotype_table_combiner: Callable[[str, str], list[dict[str, Any]]] = combine_haplotype_chromosome_tables
    sex_chromosome_identifier: Callable[[list[dict[str, Any]]], list[str]] = identify_sex_chromosomes
    sex_chromosome_formatter: Callable[[list[str]], str | None] = format_sex_chromosomes

    def build_context(
        self,
        assembly_accessions: dict[str, Any],
        assemblies_type: str | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        chromosome_context: dict[str, Any] = {}

        try:
            if assemblies_type == "prim_alt":
                self._populate_primary_context(assembly_accessions, chromosome_context)
            elif assemblies_type == "hap_asm":
                self._populate_haplotype_context(assembly_accessions, context, chromosome_context)
        except Exception as exc:
            print(f"Error processing chromosome data: {exc}")

        return chromosome_context

    def _populate_primary_context(
        self,
        assembly_accessions: dict[str, Any],
        chromosome_context: dict[str, Any],
    ) -> None:
        chromosome_dict = self.primary_table_fetcher(assembly_accessions["prim_accession"])
        chromosome_context["chromosome_data"] = chromosome_dict
        sex_chromosomes = self.sex_chromosome_identifier(chromosome_dict)
        chromosome_context["sex_chromosomes"] = self.sex_chromosome_formatter(sex_chromosomes)

    def _populate_haplotype_context(
        self,
        assembly_accessions: dict[str, Any],
        context: dict[str, Any],
        chromosome_context: dict[str, Any],
    ) -> None:
        if context.get("hap2_assembly_level") == "scaffold" and context.get("hap1_assembly_level") == "chromosome":
            chromosome_context["hap1_chromosome_data"] = self.primary_table_fetcher(
                assembly_accessions["hap1_accession"]
            )
        elif context.get("hap2_assembly_level") != "scaffold":
            chromosome_context["chromosome_data"] = self.haplotype_table_combiner(
                assembly_accessions["hap1_accession"],
                assembly_accessions["hap2_accession"],
            )

        hap1_sex_chromosomes = self.sex_chromosome_identifier(
            chromosome_context.get("hap1_chromosome_data", [])
            if "hap1_chromosome_data" in chromosome_context
            else [
                {"molecule": row["hap1_molecule"]}
                for row in chromosome_context.get("chromosome_data", [])
                if row.get("hap1_molecule")
            ]
        )
        hap2_sex_chromosomes = self.sex_chromosome_identifier(
            [
                {"molecule": row["hap2_molecule"]}
                for row in chromosome_context.get("chromosome_data", [])
                if row.get("hap2_molecule")
            ]
        )
        all_sex_chromosomes = sorted(set(hap1_sex_chromosomes + hap2_sex_chromosomes))

        chromosome_context["hap1_sex_chromosomes"] = self.sex_chromosome_formatter(hap1_sex_chromosomes)
        chromosome_context["hap2_sex_chromosomes"] = self.sex_chromosome_formatter(hap2_sex_chromosomes)
        chromosome_context["all_sex_chromosomes"] = (
            self.sex_chromosome_formatter(all_sex_chromosomes) if all_sex_chromosomes else None
        )
