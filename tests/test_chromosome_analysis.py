from __future__ import annotations

import unittest
from pathlib import Path

from data_note.chromosome_analyzer import ChromosomeAnalyzer
from data_note.models import AssemblyCoverageInput
from data_note.ncbi_sequence_report_client import NcbiSequenceReportClient
from data_note.pretext_images import (
    _choose_mbp_tick_interval,
    _filter_chromosomes_for_labelling,
    _select_pretext_source,
)


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class NcbiSequenceReportClientTests(unittest.TestCase):
    def test_fetch_reports_reads_sequence_reports(self) -> None:
        def fake_get(url, headers=None, params=None, timeout=None):
            self.assertEqual(
                url,
                "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/GCA_123456789.1/sequence_reports",
            )
            self.assertEqual(headers["accept"], "application/json")
            self.assertIsNone(params)
            self.assertEqual(timeout, 30)
            return _Response(200, {"reports": [{"chr_name": "1"}]})

        client = NcbiSequenceReportClient(request_get=fake_get)
        self.assertEqual(client.fetch_reports("GCA_123456789.1"), [{"chr_name": "1"}])


class ChromosomeAnalyzerTests(unittest.TestCase):
    def test_custom_sort_order_handles_split_chromosome_labels(self) -> None:
        labels = ["5", "2_2", "1_2", "X", "1_1", "2_1", "10", "B1"]

        self.assertEqual(
            sorted(labels, key=ChromosomeAnalyzer.custom_sort_order),
            ["1_1", "1_2", "2_1", "2_2", "5", "10", "X", "B1"],
        )

    def test_pretext_labelling_always_uses_size_order(self) -> None:
        chroms = [
            {"molecule": "4_1", "length": 2145.96},
            {"molecule": "1_1", "length": 2144.89},
            {"molecule": "2_1", "length": 2139.36},
            {"molecule": "1_2", "length": 368.54},
        ]

        self.assertEqual(
            [row["molecule"] for row in _filter_chromosomes_for_labelling(
                chroms,
                exclude_molecules=None,
                min_fraction=0.0,
            )],
            ["4_1", "1_1", "2_1", "1_2"],
        )

    def test_select_pretext_source_prefers_custom_order_image(self) -> None:
        self.assertEqual(
            _select_pretext_source(
                [
                    Path("/tmp/aLisVul1.1.primary.curated_FullMap.png"),
                    Path("/tmp/aLisVul1.1.primary.curated_CustomOrder.png"),
                ]
            ).name,
            "aLisVul1.1.primary.curated_CustomOrder.png",
        )

    def test_choose_mbp_tick_interval_avoids_crowded_long_genome_labels(self) -> None:
        class Font:
            @staticmethod
            def getbbox(text):
                return (0, 0, len(str(text)) * 30, 20)

        self.assertEqual(_choose_mbp_tick_interval(23_000, 3_850, Font()), 2000)

    def test_extract_chromosomes_only_combines_unlocalized_scaffolds(self) -> None:
        analyzer = ChromosomeAnalyzer()
        reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "1",
                "length": 100_000_000,
                "genbank_accession": "CM000001.1",
                "gc_percent": 41.0,
            },
            {
                "role": "unlocalized-scaffold",
                "assigned_molecule_location_type": "",
                "chr_name": "1",
                "length": 5_000_000,
                "genbank_accession": "unused",
                "gc_percent": None,
            },
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "MT",
                "length": 16_000,
                "genbank_accession": "CMITO1",
                "gc_percent": 43.5,
            },
        ]

        chromosomes = analyzer.extract_chromosomes_only(reports)

        self.assertEqual(
            chromosomes,
            [
                {
                    "INSDC": "CM000001.1",
                    "molecule": "1",
                    "length": 105.0,
                    "GC": 41.0,
                }
            ],
        )

    def test_combine_haplotype_chromosome_tables_aligns_rows(self) -> None:
        analyzer = ChromosomeAnalyzer()
        hap1_reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "1",
                "length": 100_000_000,
                "genbank_accession": "H1_1",
                "gc_percent": 40.0,
            }
        ]
        hap2_reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "1",
                "length": 98_000_000,
                "genbank_accession": "H2_1",
                "gc_percent": 39.0,
            },
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "X",
                "length": 12_000_000,
                "genbank_accession": "H2_X",
                "gc_percent": 38.0,
            },
        ]

        combined = analyzer.combine_haplotype_chromosome_tables(hap1_reports, hap2_reports)

        self.assertEqual(combined[0]["hap1_INSDC"], "H1_1")
        self.assertEqual(combined[0]["hap2_INSDC"], "H2_1")
        self.assertEqual(combined[1]["hap1_INSDC"], "")
        self.assertEqual(combined[1]["hap2_INSDC"], "H2_X")

    def test_get_chromosome_lengths_uses_raw_base_pairs(self) -> None:
        analyzer = ChromosomeAnalyzer()
        reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "1",
                "length": 1_234_567,
                "genbank_accession": "CM000001.1",
                "gc_percent": 41.0,
            },
            {
                "role": "unlocalized-scaffold",
                "assigned_molecule_location_type": "",
                "chr_name": "1",
                "length": 2_345_678,
                "genbank_accession": "unused",
                "gc_percent": None,
            },
            {
                "role": "unplaced-scaffold",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "Un",
                "length": 9_999,
                "genbank_accession": "unused",
                "gc_percent": None,
            },
        ]

        self.assertEqual(analyzer.get_chromosome_lengths(reports), 3_580_245)
        self.assertEqual(analyzer.extract_chromosomes_only(reports)[0]["length"], 3.58)

    def test_get_longest_scaffold_includes_unplaced_scaffolds(self) -> None:
        analyzer = ChromosomeAnalyzer()
        reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Mitochondrion",
                "chr_name": "MT",
                "length": 18_000_000,
                "genbank_accession": "CMITO1",
            },
            {
                "role": "unplaced-scaffold",
                "assigned_molecule_location_type": "Chromosome",
                "chr_name": "Un",
                "length": 12_345_678,
                "genbank_accession": "JAAA010000001.1",
            },
            {
                "role": "unlocalized-scaffold",
                "assigned_molecule_location_type": "",
                "chr_name": "1",
                "length": 8_000_000,
                "genbank_accession": "JAAA010000002.1",
            },
        ]

        self.assertEqual(analyzer.get_longest_scaffold(reports), 12.35)

    def test_calculate_percentage_assembled_uses_injected_length_fetcher(self) -> None:
        analyzer = ChromosomeAnalyzer(
            chromosome_length_fetcher=lambda accession: {
                "GCA_1.1": 100_000_000,
                "GCA_2.1": 90_000_000,
            }[accession]
        )

        primary_result = analyzer.calculate_percentage_assembled(
            AssemblyCoverageInput(
                assemblies_type="prim_alt",
                primary_accession="GCA_1.1",
                genome_length_unrounded=125_000_000,
            )
        )
        haplotype_result = analyzer.calculate_percentage_assembled(
            AssemblyCoverageInput(
                assemblies_type="hap_asm",
                hap1_accession="GCA_1.1",
                hap2_accession="GCA_2.1",
                hap1_genome_length_unrounded=125_000_000,
                hap2_genome_length_unrounded=100_000_000,
            )
        )

        self.assertEqual(primary_result["perc_assembled"], 80.0)
        self.assertEqual(haplotype_result["hap1_perc_assembled"], 80.0)
        self.assertEqual(haplotype_result["hap2_perc_assembled"], 90.0)

    def test_calculate_percentage_assembled_returns_none_for_missing_denominator(self) -> None:
        analyzer = ChromosomeAnalyzer(chromosome_length_fetcher=lambda accession: 100_000_000)

        primary_result = analyzer.calculate_percentage_assembled(
            AssemblyCoverageInput(
                assemblies_type="prim_alt",
                primary_accession="GCA_1.1",
                genome_length_unrounded=None,
            )
        )
        haplotype_result = analyzer.calculate_percentage_assembled(
            AssemblyCoverageInput(
                assemblies_type="hap_asm",
                hap1_accession="GCA_1.1",
                hap2_accession="GCA_2.1",
                hap1_genome_length_unrounded=0,
                hap2_genome_length_unrounded=None,
            )
        )

        self.assertIsNone(primary_result["perc_assembled"])
        self.assertIsNone(haplotype_result["hap1_perc_assembled"])
        self.assertIsNone(haplotype_result["hap2_perc_assembled"])


if __name__ == "__main__":
    unittest.main()
