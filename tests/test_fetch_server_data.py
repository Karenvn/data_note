from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from data_note.fetch_server_data import get_merqury_results_haplotype_assemblies, parse_genomescope


class FetchServerDataTests(unittest.TestCase):
    def test_parse_genomescope_leaves_heterozygosity_unset_for_p1_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gscope_dir = Path(tmpdir) / "gscope_results" / "iyLisNyct1"
            gscope_dir.mkdir(parents=True)
            (gscope_dir / "fastk_genomescope_summary.txt").write_text(
                "\n".join(
                    [
                        "GenomeScope version 2.0",
                        "p = 1",
                        "property                      min               max",
                        "Homozygous (a)                100%              100%",
                        "Genome Haploid Length         NA bp             157,813,596 bp",
                        "Genome Repeat Length          9,286,921 bp      9,326,089 bp",
                        "Genome Unique Length          148,195,279 bp    148,820,302 bp",
                        "Read Error Rate               0.386681%         0.386681%",
                    ]
                )
            )

            with patch("data_note.fetch_server_data.GN_ASSETS_ROOT", tmpdir):
                result = parse_genomescope("iyLisNyct1")

        self.assertEqual(result["gscope_size"], "157.81")
        self.assertIsNone(result["gscope_het"])
        self.assertEqual(result["gscope_repeat"], "5.91")

    def test_parse_genomescope_reads_general_heterozygous_label_with_single_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gscope_dir = Path(tmpdir) / "gscope_results" / "dmThaMinu1"
            gscope_dir.mkdir(parents=True)
            (gscope_dir / "fastk_genomescope_summary.txt").write_text(
                "\n".join(
                    [
                        "GenomeScope version 2.0",
                        "p = 6",
                        "property                      min               max",
                        "Homozygous (aaaaaa)           91.3153%",
                        "Heterozygous (not aaaaaa)     8.6847%",
                        "Genome Haploid Length         311,748,721 bp    312,635,786 bp",
                        "Genome Repeat Length          165,329,289 bp    165,799,725 bp",
                        "Genome Unique Length          146,419,432 bp    146,836,061 bp",
                        "Read Error Rate               0.0935184%        0.0935184%",
                    ]
                )
            )

            with patch("data_note.fetch_server_data.GN_ASSETS_ROOT", tmpdir):
                result = parse_genomescope("dmThaMinu1")

        self.assertEqual(result["gscope_het"], "8.68")

    @patch("data_note.fetch_server_data.read_merqury_results")
    def test_haplotype_merqury_requires_hap1_hap2_labels(self, mock_read_merqury_results) -> None:
        stats_df = pd.DataFrame(
            [
                {"Assembly": "primary", "Region": "all", "Found": "10", "Total": "12", "% Covered": "83.33"},
                {"Assembly": "alt", "Region": "all", "Found": "9", "Total": "12", "% Covered": "75.00"},
                {"Assembly": "both", "Region": "all", "Found": "12", "Total": "12", "% Covered": "100.00"},
            ]
        )
        qv_df = pd.DataFrame(
            [
                {"Assembly": "primary", "No Support": "1", "Total": "10", "Error %": "0.1", "QV": "40.0"},
                {"Assembly": "alt", "No Support": "2", "Total": "10", "Error %": "0.2", "QV": "37.0"},
                {"Assembly": "both", "No Support": "3", "Total": "20", "Error %": "0.15", "QV": "38.5"},
            ]
        )
        mock_read_merqury_results.return_value = (stats_df, qv_df)

        result = get_merqury_results_haplotype_assemblies("ilCatProm1")

        self.assertIsNone(result["hap1_QV"])
        self.assertIsNone(result["hap2_QV"])
        self.assertEqual(result["combined_QV"], "38.5")
        self.assertIsNone(result["hap1_kmer_completeness"])
        self.assertIsNone(result["hap2_kmer_completeness"])
        self.assertEqual(result["combined_kmer_completeness"], "100.00")


if __name__ == "__main__":
    unittest.main()
