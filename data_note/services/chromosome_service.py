from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

from ..formatting_utils import format_sex_chromosomes
from ..models import AssemblySelection, ChromosomeSummary
from ..process_chromosome_data import (
    combine_haplotype_chromosome_tables,
    identify_sex_chromosomes,
    identify_supernumerary_chromosomes,
    prim_chromosome_table,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChromosomeService:
    primary_table_fetcher: Callable[[str], list[dict[str, Any]]] = prim_chromosome_table
    haplotype_table_combiner: Callable[[str, str], list[dict[str, Any]]] = combine_haplotype_chromosome_tables
    sex_chromosome_identifier: Callable[[list[dict[str, Any]]], list[str]] = identify_sex_chromosomes
    sex_chromosome_formatter: Callable[[list[str]], str | None] = format_sex_chromosomes
    supernumerary_chromosome_identifier: Callable[[list[dict[str, Any]]], list[str]] = identify_supernumerary_chromosomes
    supernumerary_chromosome_formatter: Callable[[list[str]], str | None] = format_sex_chromosomes

    def build_context(
        self,
        assembly_selection: AssemblySelection,
        context: dict[str, Any],
    ) -> ChromosomeSummary:
        chromosome_summary = ChromosomeSummary()

        try:
            if assembly_selection.assemblies_type == "prim_alt":
                self._populate_primary_context(assembly_selection, chromosome_summary)
            elif assembly_selection.assemblies_type == "hap_asm":
                self._populate_haplotype_context(assembly_selection, context, chromosome_summary)
        except Exception as exc:
            logger.warning("Error processing chromosome data: %s", exc)

        return chromosome_summary

    def _populate_primary_context(
        self,
        assembly_selection: AssemblySelection,
        chromosome_summary: ChromosomeSummary,
    ) -> None:
        if assembly_selection.primary is None:
            return

        chromosome_dict = self.primary_table_fetcher(assembly_selection.primary.accession)
        chromosome_summary.chromosome_data = chromosome_dict
        sex_chromosomes = self.sex_chromosome_identifier(chromosome_dict)
        supernumerary_chromosomes = self.supernumerary_chromosome_identifier(chromosome_dict)
        chromosome_summary.sex_chromosomes = self.sex_chromosome_formatter(sex_chromosomes)
        chromosome_summary.supernumerary_chromosomes = self.supernumerary_chromosome_formatter(
            supernumerary_chromosomes
        )

    def _populate_haplotype_context(
        self,
        assembly_selection: AssemblySelection,
        context: dict[str, Any],
        chromosome_summary: ChromosomeSummary,
    ) -> None:
        if assembly_selection.hap1 is None:
            return

        if context.get("hap2_assembly_level") == "scaffold" and context.get("hap1_assembly_level") == "chromosome":
            chromosome_summary.hap1_chromosome_data = self.primary_table_fetcher(
                assembly_selection.hap1.accession
            )
        elif context.get("hap2_assembly_level") != "scaffold" and assembly_selection.hap2 is not None:
            chromosome_summary.chromosome_data = self.haplotype_table_combiner(
                assembly_selection.hap1.accession,
                assembly_selection.hap2.accession,
            )

        hap1_sex_chromosomes = self.sex_chromosome_identifier(
            chromosome_summary.hap1_chromosome_data or []
            if chromosome_summary.hap1_chromosome_data is not None
            else [
                {"molecule": row["hap1_molecule"]}
                for row in chromosome_summary.chromosome_data or []
                if row.get("hap1_molecule")
            ]
        )
        hap2_sex_chromosomes = self.sex_chromosome_identifier(
            [
                {"molecule": row["hap2_molecule"]}
                for row in chromosome_summary.chromosome_data or []
                if row.get("hap2_molecule")
            ]
        )
        hap1_supernumerary_chromosomes = self.supernumerary_chromosome_identifier(
            chromosome_summary.hap1_chromosome_data or []
            if chromosome_summary.hap1_chromosome_data is not None
            else [
                {"molecule": row["hap1_molecule"]}
                for row in chromosome_summary.chromosome_data or []
                if row.get("hap1_molecule")
            ]
        )
        hap2_supernumerary_chromosomes = self.supernumerary_chromosome_identifier(
            [
                {"molecule": row["hap2_molecule"]}
                for row in chromosome_summary.chromosome_data or []
                if row.get("hap2_molecule")
            ]
        )
        all_sex_chromosomes = sorted(set(hap1_sex_chromosomes + hap2_sex_chromosomes))
        all_supernumerary_chromosomes = sorted(
            set(hap1_supernumerary_chromosomes + hap2_supernumerary_chromosomes)
        )

        chromosome_summary.hap1_sex_chromosomes = self.sex_chromosome_formatter(hap1_sex_chromosomes)
        chromosome_summary.hap2_sex_chromosomes = self.sex_chromosome_formatter(hap2_sex_chromosomes)
        chromosome_summary.all_sex_chromosomes = (
            self.sex_chromosome_formatter(all_sex_chromosomes) if all_sex_chromosomes else None
        )
        chromosome_summary.hap1_supernumerary_chromosomes = self.supernumerary_chromosome_formatter(
            hap1_supernumerary_chromosomes
        )
        chromosome_summary.hap2_supernumerary_chromosomes = self.supernumerary_chromosome_formatter(
            hap2_supernumerary_chromosomes
        )
        chromosome_summary.all_supernumerary_chromosomes = (
            self.supernumerary_chromosome_formatter(all_supernumerary_chromosomes)
            if all_supernumerary_chromosomes
            else None
        )
