from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from .models import AssemblyCoverageInput


@dataclass(slots=True)
class ChromosomeAnalyzer:
    chromosome_length_fetcher: Callable[[str], int] | None = None

    @staticmethod
    def custom_sort_order(molecule: str) -> tuple[Any, ...]:
        molecule = str(molecule)
        split_match = re.match(r"^(\d+)(?:[_\-.](\d+))?([A-Za-z]*)$", molecule)
        if split_match:
            split_value = split_match.group(2)
            return (
                0,
                int(split_match.group(1)),
                int(split_value) if split_value else 0,
                split_match.group(3),
            )

        match = re.match(r"^(\d+)([A-Za-z]*)$", molecule)
        if match:
            return (0, int(match.group(1)), 0, match.group(2))
        order_map = {
            "X": (1, 1000, 0, ""),
            "X1": (1, 1000, 1, ""),
            "X2": (1, 1000, 2, ""),
            "Y": (1, 2000, 0, ""),
            "W": (1, 3000, 0, ""),
            "Z": (1, 4000, 0, ""),
            "Z1": (1, 4000, 1, ""),
            "Z2": (1, 4000, 2, ""),
            "B": (1, 5000, 0, ""),
            "B1": (1, 5000, 1, ""),
            "B2": (1, 5000, 2, ""),
        }
        return order_map.get(molecule.upper(), (2, molecule))

    def get_longest_scaffold(self, reports: list[dict[str, Any]]) -> float | None:
        relevant_reports = [
            report
            for report in reports
            if report.get("role") in ("assembled-molecule", "unlocalized-scaffold", "unplaced-scaffold")
            and report.get("assigned_molecule_location_type") not in ("Mitochondrion", "Chloroplast", "Plastid")
        ]
        if not relevant_reports:
            return None
        longest = max(relevant_reports, key=lambda report: report.get("length", 0))
        return round(longest.get("length", 0) / 1e6, 2)

    def extract_chromosomes_only(self, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chrom_list = []
        for name, info in self._collect_assigned_chromosome_data(reports).items():
            chrom_list.append(
                {
                    "INSDC": info["INSDC"],
                    "molecule": name,
                    "length": round(info["length_bp"] / 1e6, 2),
                    "GC": info["GC"],
                }
            )
        chrom_list.sort(key=lambda row: self.custom_sort_order(row["molecule"]))
        return chrom_list

    def extract_chromosomes_for_pretext_labelling(self, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chrom_list = []
        for name, info in self._collect_assigned_chromosome_data(reports).items():
            length_bp = int(info["length_bp"])
            chrom_list.append(
                {
                    "INSDC": info["INSDC"],
                    "molecule": name,
                    "length": length_bp / 1e6,
                    "length_bp": length_bp,
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
        chromosomes = self._collect_assigned_chromosome_data(reports)
        return sum(int(chromosome["length_bp"]) for chromosome in chromosomes.values())

    def calculate_percentage_assembled(self, info: AssemblyCoverageInput | dict) -> dict[str, Any]:
        coverage = info if isinstance(info, AssemblyCoverageInput) else AssemblyCoverageInput.from_mapping(info)
        coverage.validate()
        chromosome_length_fetcher = self.chromosome_length_fetcher
        if chromosome_length_fetcher is None:
            raise ValueError("Chromosome length fetcher is required for coverage calculations")

        if coverage.assemblies_type == "prim_alt":
            total_chromosome_length = chromosome_length_fetcher(coverage.primary_accession)
            genome_length = coverage.genome_length_unrounded
            percentage = self._calculate_percentage(total_chromosome_length, genome_length)
            return {
                "total_chromosome_length": total_chromosome_length,
                "genome_length_unrounded": genome_length,
                "perc_assembled": percentage,
            }

        total_hap1 = chromosome_length_fetcher(coverage.hap1_accession)
        total_hap2 = chromosome_length_fetcher(coverage.hap2_accession)
        genome_hap1 = coverage.hap1_genome_length_unrounded
        genome_hap2 = coverage.hap2_genome_length_unrounded
        percentage_hap1 = self._calculate_percentage(total_hap1, genome_hap1)
        percentage_hap2 = self._calculate_percentage(total_hap2, genome_hap2)
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

    def _collect_assigned_chromosome_data(self, reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        chr_data: dict[str, dict[str, Any]] = {}
        for record in self._filter_relevant_reports(reports):
            name = record.get("chr_name")
            role = record.get("role")
            location = record.get("assigned_molecule_location_type", "")
            if not name:
                continue
            if (role == "assembled-molecule" and location == "Chromosome") or role == "unlocalized-scaffold":
                length = int(record.get("length") or 0)
                entry = chr_data.setdefault(name, {"length_bp": 0, "INSDC": None, "GC": None})
                entry["length_bp"] += length
                if role == "assembled-molecule" and location == "Chromosome":
                    entry["INSDC"] = record.get("genbank_accession")
                    entry["GC"] = record.get("gc_percent")

        return {
            name: info
            for name, info in chr_data.items()
            if name.upper() not in {"MT", "PLTD"} and info["INSDC"]
        }

    @staticmethod
    def _calculate_percentage(total_chromosome_length: int, genome_length: float | None) -> float | None:
        if genome_length is None or genome_length <= 0:
            return None
        return round((total_chromosome_length / genome_length) * 100, 2)


__all__ = ["ChromosomeAnalyzer"]
