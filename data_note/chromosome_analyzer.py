from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from .models import AssemblyCoverageInput


@dataclass(slots=True)
class ChromosomeAnalyzer:
    chromosome_length_fetcher: Callable[[str], int] | None = None

    @staticmethod
    def custom_sort_order(molecule: str) -> tuple[Any, Any]:
        match = re.match(r"^(\d+)([A-Za-z]*)$", molecule)
        if match:
            return (int(match.group(1)), match.group(2))
        order_map = {
            "X": (1000, ""),
            "X1": (1000, "1"),
            "X2": (1000, "2"),
            "Y": (2000, ""),
            "W": (3000, ""),
            "Z": (4000, ""),
            "Z1": (4000, "1"),
            "Z2": (4000, "2"),
            "B": (5000, ""),
            "B1": (5000, "1"),
            "B2": (5000, "2"),
        }
        return order_map.get(molecule, (float("inf"), molecule))

    def get_longest_scaffold(self, reports: list[dict[str, Any]]) -> float | None:
        relevant_reports = self._filter_relevant_reports(reports)
        if not relevant_reports:
            return None
        longest = max(relevant_reports, key=lambda report: report.get("length", 0))
        return round(longest.get("length", 0) / 1e6, 2)

    def extract_chromosomes_only(self, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chr_data: dict[str, dict[str, Any]] = {}
        for record in self._filter_relevant_reports(reports):
            name = record.get("chr_name")
            role = record.get("role")
            location = record.get("assigned_molecule_location_type", "")
            if not name:
                continue
            if (role == "assembled-molecule" and location == "Chromosome") or role == "unlocalized-scaffold":
                length = record.get("length", 0)
                entry = chr_data.setdefault(name, {"length": 0, "INSDC": None, "GC": None})
                entry["length"] += length
                if role == "assembled-molecule" and location == "Chromosome":
                    entry["INSDC"] = record.get("genbank_accession")
                    entry["GC"] = record.get("gc_percent")

        chrom_list = []
        for name, info in chr_data.items():
            if name.upper() in {"MT", "PLTD"}:
                continue
            if not info["INSDC"]:
                continue
            chrom_list.append(
                {
                    "INSDC": info["INSDC"],
                    "molecule": name,
                    "length": round(info["length"] / 1e6, 2),
                    "GC": info["GC"],
                }
            )
        chrom_list.sort(key=lambda row: self.custom_sort_order(row["molecule"]))
        return chrom_list

    def combine_haplotype_chromosome_tables(
        self,
        hap1_reports: list[dict[str, Any]],
        hap2_reports: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        hap1 = self.extract_chromosomes_only(hap1_reports)
        hap2 = self.extract_chromosomes_only(hap2_reports)
        hap1.sort(key=lambda row: self.custom_sort_order(row["molecule"]))
        hap2.sort(key=lambda row: self.custom_sort_order(row["molecule"]))
        combined = []
        for index in range(max(len(hap1), len(hap2))):
            combined.append(
                {
                    "hap1_INSDC": hap1[index]["INSDC"] if index < len(hap1) else "",
                    "hap1_molecule": hap1[index]["molecule"] if index < len(hap1) else "",
                    "hap1_length": hap1[index]["length"] if index < len(hap1) else "",
                    "hap1_GC": hap1[index]["GC"] if index < len(hap1) else "",
                    "hap2_INSDC": hap2[index]["INSDC"] if index < len(hap2) else "",
                    "hap2_molecule": hap2[index]["molecule"] if index < len(hap2) else "",
                    "hap2_length": hap2[index]["length"] if index < len(hap2) else "",
                    "hap2_GC": hap2[index]["GC"] if index < len(hap2) else "",
                }
            )
        return combined

    def get_chromosome_lengths(self, reports: list[dict[str, Any]]) -> int:
        chromosomes = self.extract_chromosomes_only(reports)
        return sum(int(chromosome["length"] * 1e6) for chromosome in chromosomes)

    def calculate_percentage_assembled(self, info: AssemblyCoverageInput | dict) -> dict[str, Any]:
        coverage = info if isinstance(info, AssemblyCoverageInput) else AssemblyCoverageInput.from_mapping(info)
        coverage.validate()
        chromosome_length_fetcher = self.chromosome_length_fetcher
        if chromosome_length_fetcher is None:
            raise ValueError("Chromosome length fetcher is required for coverage calculations")

        if coverage.assemblies_type == "prim_alt":
            total_chromosome_length = chromosome_length_fetcher(coverage.primary_accession)
            genome_length = coverage.genome_length_unrounded or 0
            percentage = round((total_chromosome_length / genome_length) * 100, 2) if genome_length else 0
            return {
                "total_chromosome_length": total_chromosome_length,
                "genome_length_unrounded": genome_length,
                "perc_assembled": percentage,
            }

        total_hap1 = chromosome_length_fetcher(coverage.hap1_accession)
        total_hap2 = chromosome_length_fetcher(coverage.hap2_accession)
        genome_hap1 = coverage.hap1_genome_length_unrounded or 0
        genome_hap2 = coverage.hap2_genome_length_unrounded or 0
        percentage_hap1 = round((total_hap1 / genome_hap1) * 100, 2) if genome_hap1 else 0
        percentage_hap2 = round((total_hap2 / genome_hap2) * 100, 2) if genome_hap2 else 0
        return {
            "hap1_chromosome_length": total_hap1,
            "hap2_chromosome_length": total_hap2,
            "hap1_perc_assembled": percentage_hap1,
            "hap2_perc_assembled": percentage_hap2,
        }

    @staticmethod
    def identify_sex_chromosomes(chr_list: list[dict[str, Any]]) -> list[str]:
        valid = {"X", "X1", "X2", "Y", "W", "Z", "Z1", "Z2"}
        found = {chromosome["molecule"].upper() for chromosome in chr_list if chromosome["molecule"].upper() in valid}
        return sorted(found)

    @staticmethod
    def identify_supernumerary_chromosomes(chr_list: list[dict[str, Any]]) -> list[str]:
        valid = {"B", "B1", "B2", "B3", "B4"}
        found = {chromosome["molecule"].upper() for chromosome in chr_list if chromosome["molecule"].upper() in valid}
        return sorted(found)

    @staticmethod
    def _filter_relevant_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            report
            for report in reports
            if report.get("role") in ("assembled-molecule", "unlocalized-scaffold")
        ]


__all__ = ["ChromosomeAnalyzer"]
