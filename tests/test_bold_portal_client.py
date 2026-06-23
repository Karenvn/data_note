from __future__ import annotations

import unittest

from data_note.bold_portal_client import BoldPortalClient


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class BoldPortalClientTests(unittest.TestCase):
    def test_fetch_species_bin_summary_combines_summary_and_ancillary_data(self) -> None:
        calls: list[tuple[str, dict[str, str]]] = []

        def fake_get(url: str, *, params: dict[str, str], timeout: int) -> _Response:
            del timeout
            calls.append((url, params))
            if url.endswith("/api/summary"):
                return _Response(
                    {
                        "bin_uri": {"BOLD:AAF0863": 40},
                        "marker_code": {"COI-5P": 44, "ND1": 1},
                        "species": {"Conistra rubiginosa": 44},
                    }
                )
            return _Response(
                [
                    {
                        "barcodecluster.uri": "BOLD:AAF0863",
                        "barcodecluster.doi": "10.5883/BOLD:AAF0863",
                        "barcodecluster.avgdist": 0.7771446,
                        "barcodecluster.maxdist": 2.4077046,
                    }
                ]
            )

        summary = BoldPortalClient(session_get=fake_get).fetch_species_bin_summary(
            "Conistra rubiginosa"
        )

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.bin_uri, "BOLD:AAF0863")
        self.assertEqual(summary.doi, "10.5883/BOLD:AAF0863")
        self.assertEqual(summary.sequence_count, 44)
        self.assertEqual(summary.avg_distance, 0.7771446)
        self.assertEqual(summary.max_distance, 2.4077046)
        self.assertEqual(calls[0][1]["query"], "tax:species:Conistra rubiginosa")
        self.assertEqual(calls[1][1]["values"], "BOLD:AAF0863")

    def test_fetch_species_bin_summary_skips_species_with_multiple_bins(self) -> None:
        def fake_get(url: str, *, params: dict[str, str], timeout: int) -> _Response:
            del url, params, timeout
            return _Response(
                {
                    "bin_uri": {"BOLD:AAF0863": 40, "BOLD:AEE8907": 2},
                    "marker_code": {"COI-5P": 42},
                }
            )

        summary = BoldPortalClient(session_get=fake_get).fetch_species_bin_summary(
            "Conistra rubiginosa"
        )

        self.assertIsNone(summary)


if __name__ == "__main__":
    unittest.main()
