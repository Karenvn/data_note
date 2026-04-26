from __future__ import annotations

import unittest

from data_note.gbif_taxonomy_client import GbifTaxonomyClient


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class GbifTaxonomyClientTests(unittest.TestCase):
    def test_fetch_species_metadata_uses_exact_species_match(self) -> None:
        def fake_get(url, *, params=None, timeout=None):
            del timeout
            if url.endswith("/species/match"):
                self.assertEqual(params["strict"], "true")
                return _Response(
                    {
                        "usageKey": 2436436,
                        "canonicalName": "Homo sapiens",
                        "rank": "SPECIES",
                        "matchType": "EXACT",
                    }
                )
            if url.endswith("/species/2436436"):
                return _Response(
                    {
                        "key": 2436436,
                        "canonicalName": "Homo sapiens",
                        "authorship": "Linnaeus, 1758",
                        "vernacularName": "human",
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        client = GbifTaxonomyClient(request_get=fake_get)
        metadata = client.fetch_species_metadata("Homo sapiens", tax_id="9606")

        self.assertEqual(metadata["tax_auth"], "Linnaeus, 1758")
        self.assertEqual(metadata["common_name"], "human")
        self.assertEqual(metadata["gbif_usage_key"], 2436436)
        self.assertEqual(metadata["gbif_match_strategy"], "GBIF_MATCH_EXACT")

    def test_fetch_species_metadata_falls_back_to_search_for_current_name_missing_from_match(self) -> None:
        def fake_get(url, *, params=None, timeout=None):
            del timeout
            if url.endswith("/species/match"):
                return _Response({"matchType": "NONE"})
            if url.endswith("/species/search"):
                self.assertEqual(params["q"], "Neogale vison")
                return _Response(
                    {
                        "results": [
                            {
                                "key": 177671599,
                                "canonicalName": "Neogale vison",
                                "rank": "SPECIES",
                                "taxonomicStatus": "ACCEPTED",
                                "taxonID": "452646",
                            },
                            {
                                "key": 293643921,
                                "canonicalName": "Neogale vison",
                                "rank": "SPECIES",
                                "taxonomicStatus": "ACCEPTED",
                                "authorship": "(Schreber, 1777)",
                                "vernacularNames": [{"vernacularName": "American mink", "language": "eng"}],
                            },
                        ]
                    }
                )
            if url.endswith("/species/177671599"):
                return _Response(
                    {
                        "key": 177671599,
                        "canonicalName": "Neogale vison",
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        client = GbifTaxonomyClient(request_get=fake_get)
        metadata = client.fetch_species_metadata("Neogale vison", tax_id="452646")

        self.assertEqual(metadata["gbif_usage_key"], 177671599)
        self.assertEqual(metadata["common_name"], "American mink")
        self.assertEqual(metadata["tax_auth"], "(Schreber, 1777)")
        self.assertEqual(metadata["gbif_match_strategy"], "GBIF_SEARCH_EXACT")


if __name__ == "__main__":
    unittest.main()
