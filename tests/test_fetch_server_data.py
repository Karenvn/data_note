from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from data_note.fetch_server_data import get_merqury_results_haplotype_assemblies


class FetchServerDataTests(unittest.TestCase):
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
