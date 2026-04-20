from __future__ import annotations

import unittest

from data_note.models import GenomeScopeSummary, MerquryRecord, MerqurySummary, QualityMetrics


class QualityModelTests(unittest.TestCase):
    def test_genomescope_summary_round_trips_legacy_keys(self) -> None:
        summary = GenomeScopeSummary.from_mapping(
            {
                "gscope_size": "123.4",
                "gscope_het": "0.45",
                "gscope_repeat": "52.1",
                "gscope_error": 0.03,
                "gscope_unique": 47.9,
                "other_metric": "kept",
            }
        )

        self.assertEqual(summary.size_mb, "123.4")
        self.assertEqual(summary.extras["other_metric"], "kept")
        self.assertEqual(summary.to_context_dict()["gscope_repeat"], "52.1")
        self.assertEqual(summary.to_context_dict()["other_metric"], "kept")

    def test_merqury_summary_round_trips_legacy_keys(self) -> None:
        summary = MerqurySummary.from_mapping(
            {
                "prim_QV": "55.2",
                "alt_QV": "54.1",
                "combined_QV": "55.8",
                "prim_kmer_completeness": "98.5",
                "alt_kmer_completeness": "98.2",
                "combined_kmer_completeness": "99.1",
            }
        )

        self.assertIsInstance(summary.record("prim"), MerquryRecord)
        self.assertEqual(summary.record("prim").qv, "55.2")
        self.assertEqual(summary.record("combined").kmer_completeness_percent, "99.1")
        self.assertEqual(summary.to_context_dict()["alt_QV"], "54.1")

    def test_quality_metrics_combines_genomescope_and_merqury(self) -> None:
        metrics = QualityMetrics.from_legacy_parts(
            genomescope={"gscope_size": "321.0"},
            merqury={"hap1_QV": "51.2", "hap1_kmer_completeness": "97.9"},
        )

        context = metrics.to_context_dict()
        self.assertEqual(context["gscope_size"], "321.0")
        self.assertEqual(context["hap1_QV"], "51.2")
        self.assertEqual(context["hap1_kmer_completeness"], "97.9")


if __name__ == "__main__":
    unittest.main()
