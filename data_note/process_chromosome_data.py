#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from .chromosome_analyzer import ChromosomeAnalyzer
from .models import AssemblyCoverageInput
from .ncbi_sequence_report_client import NcbiSequenceReportClient

_SEQUENCE_REPORT_CLIENT = NcbiSequenceReportClient()
_CHROMOSOME_ANALYZER = ChromosomeAnalyzer()
_COVERAGE_ANALYZER = ChromosomeAnalyzer(
    chromosome_length_fetcher=lambda accession: get_chromosome_lengths(accession)
)


def fetch_sequence_reports(accession: str) -> list[dict[str, Any]]:
    return _SEQUENCE_REPORT_CLIENT.fetch_reports(accession)


def get_longest_scaffold(accession: str) -> float | None:
    return _CHROMOSOME_ANALYZER.get_longest_scaffold(fetch_sequence_reports(accession))


def custom_sort_order(molecule: str) -> tuple[Any, Any]:
    return _CHROMOSOME_ANALYZER.custom_sort_order(molecule)


def extract_chromosomes_only(accession: str) -> list[dict[str, Any]]:
    return _CHROMOSOME_ANALYZER.extract_chromosomes_only(fetch_sequence_reports(accession))


def prim_chromosome_table(accession: str) -> list[dict[str, Any]]:
    return extract_chromosomes_only(accession)


def combine_haplotype_chromosome_tables(hap1_acc: str, hap2_acc: str) -> list[dict[str, Any]]:
    return _CHROMOSOME_ANALYZER.combine_haplotype_chromosome_tables(
        fetch_sequence_reports(hap1_acc),
        fetch_sequence_reports(hap2_acc),
    )


def get_chromosome_lengths(accession: str) -> int:
    return _CHROMOSOME_ANALYZER.get_chromosome_lengths(fetch_sequence_reports(accession))


def calculate_percentage_assembled(info: AssemblyCoverageInput | dict[str, Any]) -> dict[str, Any]:
    return _COVERAGE_ANALYZER.calculate_percentage_assembled(info)


def identify_sex_chromosomes(chr_list: list[dict[str, Any]]) -> list[str]:
    return _CHROMOSOME_ANALYZER.identify_sex_chromosomes(chr_list)


def identify_supernumerary_chromosomes(chr_list: list[dict[str, Any]]) -> list[str]:
    return _CHROMOSOME_ANALYZER.identify_supernumerary_chromosomes(chr_list)


__all__ = [
    "ChromosomeAnalyzer",
    "NcbiSequenceReportClient",
    "calculate_percentage_assembled",
    "combine_haplotype_chromosome_tables",
    "custom_sort_order",
    "extract_chromosomes_only",
    "fetch_sequence_reports",
    "get_chromosome_lengths",
    "get_longest_scaffold",
    "identify_sex_chromosomes",
    "identify_supernumerary_chromosomes",
    "prim_chromosome_table",
]
