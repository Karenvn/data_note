from __future__ import annotations

import unittest

from data_note.gbif_occurrence_client import GbifOccurrenceClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class GbifOccurrenceClientTests(unittest.TestCase):
    def test_fetch_distribution_summary_uses_facets(self) -> None:
        calls: list[tuple[str, dict[str, object] | None]] = []

        def fake_get(url: str, *, params=None, timeout=None):
            del timeout
            calls.append((url, params))
            if url.endswith("/occurrence/search"):
                return _FakeResponse(
                    {
                        "count": 42,
                        "facets": [
                            {
                                "field": "CONTINENT",
                                "counts": [
                                    {"name": "NORTH_AMERICA", "count": 30},
                                    {"name": "EUROPE", "count": 12},
                                ],
                            },
                            {
                                "field": "COUNTRY",
                                "counts": [
                                    {"name": "US", "count": 20},
                                    {"name": "CA", "count": 10},
                                    {"name": "GB", "count": 12},
                                ],
                            },
                        ],
                    }
                )
            if url.endswith("/enumeration/country"):
                return _FakeResponse(
                    [
                        {"iso2": "US", "title": "United States of America"},
                        {"iso2": "CA", "title": "Canada"},
                        {"iso2": "GB", "title": "United Kingdom of Great Britain and Northern Ireland"},
                    ]
                )
            raise AssertionError(f"Unexpected URL: {url}")

        client = GbifOccurrenceClient(request_get=fake_get)
        summary = client.fetch_distribution_summary(2435099, facet_limit=5)

        self.assertEqual(summary.record_count, 42)
        self.assertEqual(summary.continents[0].label, "North America")
        self.assertEqual(summary.countries[0].label, "United States of America")
        self.assertEqual(calls[0][1]["facet"], ["country", "continent"])
        self.assertEqual(calls[0][1]["facetLimit"], 5)

        text = client.render_distribution_summary(summary)
        self.assertIn("42 GBIF occurrence records", text)
        self.assertIn("North America (30)", text)
        self.assertIn("United States of America (20)", text)
        self.assertIn("https://www.gbif.org/species/2435099", text)

    def test_render_distribution_summary_handles_no_records(self) -> None:
        def fake_get(url: str, *, params=None, timeout=None):
            del params, timeout
            if url.endswith("/occurrence/search"):
                return _FakeResponse({"count": 0, "facets": []})
            raise AssertionError(f"Unexpected URL: {url}")

        client = GbifOccurrenceClient(request_get=fake_get)
        summary = client.fetch_distribution_summary(1)

        text = client.render_distribution_summary(summary)
        self.assertIn("No GBIF occurrence records with coordinates", text)


if __name__ == "__main__":
    unittest.main()
