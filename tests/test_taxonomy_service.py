from __future__ import annotations

import unittest

from data_note.models import TaxonomyInfo
from data_note.services.taxonomy_service import TaxonomyService


class TaxonomyServiceTests(unittest.TestCase):
    def test_build_context_prefers_ncbi_authority_and_gbif_common_name(self) -> None:
        lineage_calls: list[str] = []
        gbif_calls: list[tuple[str, str]] = []

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
                "tax_auth_ncbi": "(Linnaeus, 1758)",
                "common_name_ncbi": "human ncbi",
            }

        def gbif_fetcher(species: str, tax_id: str) -> dict[str, str]:
            gbif_calls.append((species, tax_id))
            return {
                "tax_auth": "Wrong authority",
                "common_name": "human",
                "gbif_url": "https://gbif.example/species/1",
            }

        service = TaxonomyService(lineage_fetcher=lineage_fetcher, gbif_fetcher=gbif_fetcher)
        taxonomy = service.build_context("9606")

        self.assertIsInstance(taxonomy, TaxonomyInfo)
        self.assertEqual(lineage_calls, ["9606"])
        self.assertEqual(gbif_calls, [("Example species", "9606")])
        self.assertEqual(taxonomy.tax_id, "9606")
        self.assertEqual(taxonomy.species, "Example species")
        self.assertEqual(taxonomy.class_name, "Mammalia")
        self.assertEqual(taxonomy.common_name, "human")
        self.assertEqual(taxonomy.tax_auth, "(Linnaeus, 1758)")
        self.assertEqual(taxonomy.extras["tax_auth_source"], "ncbi_datasets")
        self.assertEqual(taxonomy.extras["common_name_source"], "gbif")

    def test_build_context_falls_back_to_gbif_authority_when_ncbi_missing(self) -> None:
        def lineage_fetcher(tax_id: str) -> dict[str, str]:
            self.assertEqual(tax_id, "12345")
            return {
                "species": "Example species",
                "lineage": "Eukaryota; Chordata",
                "phylum": "Chordata",
                "class": "Mammalia",
                "order": "Primates",
                "family": "Hominidae",
                "genus": "Homo",
            }

        def gbif_fetcher(species: str, tax_id: str) -> dict[str, str]:
            self.assertEqual(species, "Example species")
            self.assertEqual(tax_id, "12345")
            return {
                "tax_auth": "(Schreber, 1777)",
                "common_name": "human",
                "gbif_url": "https://gbif.example/species/1",
            }

        service = TaxonomyService(lineage_fetcher=lineage_fetcher, gbif_fetcher=gbif_fetcher)
        taxonomy = service.build_context("12345")

        self.assertEqual(taxonomy.tax_auth, "(Schreber, 1777)")
        self.assertEqual(taxonomy.extras["tax_auth_source"], "gbif")


if __name__ == "__main__":
    unittest.main()
