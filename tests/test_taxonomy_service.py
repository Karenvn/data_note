from __future__ import annotations

import unittest

from data_note.models import TaxonomyInfo
from data_note.services.taxonomy_service import TaxonomyService


class TaxonomyServiceTests(unittest.TestCase):
    def test_build_context_returns_taxonomy_info(self) -> None:
        lineage_calls: list[str] = []
        gbif_calls: list[str] = []

        def lineage_fetcher(tax_id: str) -> dict[str, str]:
            lineage_calls.append(tax_id)
            return {
                "species": "Example species",
                "lineage": "Eukaryota; Chordata",
                "phylum": "Chordata",
                "class": "Mammalia",
                "order": "Primates",
                "family": "Hominidae",
                "genus": "Homo",
            }

        def gbif_fetcher(species: str) -> dict[str, str]:
            gbif_calls.append(species)
            return {
                "tax_auth": "(Linnaeus, 1758)",
                "common_name": "human",
                "gbif_url": "https://gbif.example/species/1",
            }

        service = TaxonomyService(lineage_fetcher=lineage_fetcher, gbif_fetcher=gbif_fetcher)
        taxonomy = service.build_context("9606")

        self.assertIsInstance(taxonomy, TaxonomyInfo)
        self.assertEqual(lineage_calls, ["9606"])
        self.assertEqual(gbif_calls, ["Example species"])
        self.assertEqual(taxonomy.tax_id, "9606")
        self.assertEqual(taxonomy.species, "Example species")
        self.assertEqual(taxonomy.class_name, "Mammalia")
        self.assertEqual(taxonomy.common_name, "human")


if __name__ == "__main__":
    unittest.main()
