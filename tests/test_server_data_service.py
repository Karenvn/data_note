from __future__ import annotations

import unittest

from data_note.models import QualityMetrics
from data_note.services.server_data_service import ServerDataService


class ServerDataServiceTests(unittest.TestCase):
    def test_build_context_returns_typed_quality_metrics_for_prim_alt(self) -> None:
        service = ServerDataService(
            prim_alt_merqury_fetcher=lambda tolid: {
                "prim_QV": "55.0",
                "alt_QV": "54.0",
                "combined_QV": "55.6",
                "prim_kmer_completeness": "98.4",
                "alt_kmer_completeness": "98.1",
                "combined_kmer_completeness": "99.0",
            },
            haplotype_merqury_fetcher=lambda tolid: {},
            genomescope_fetcher=lambda tolid: {
                "gscope_size": "200.1",
                "gscope_het": "0.9",
            },
        )

        metrics = service.build_context("prim_alt", "ixExample1")

        self.assertIsInstance(metrics, QualityMetrics)
        self.assertEqual(metrics.genomescope.size_mb, "200.1")
        self.assertEqual(metrics.merqury.record("prim").qv, "55.0")
        self.assertEqual(metrics.to_context_dict()["combined_kmer_completeness"], "99.0")

    def test_build_context_returns_typed_quality_metrics_for_haplotype_assemblies(self) -> None:
        service = ServerDataService(
            prim_alt_merqury_fetcher=lambda tolid: {},
            haplotype_merqury_fetcher=lambda tolid: {
                "hap1_QV": "49.8",
                "hap2_QV": "49.5",
                "combined_QV": "50.1",
                "hap1_kmer_completeness": "97.5",
                "hap2_kmer_completeness": "97.2",
                "combined_kmer_completeness": "98.7",
            },
            genomescope_fetcher=lambda tolid: {"gscope_repeat": "44.2"},
        )

        metrics = service.build_context("hap_asm", "ixExample2")

        self.assertEqual(metrics.genomescope.repeat_percent, "44.2")
        self.assertEqual(metrics.merqury.record("hap1").qv, "49.8")
        self.assertEqual(metrics.to_context_dict()["hap2_kmer_completeness"], "97.2")


if __name__ == "__main__":
    unittest.main()
