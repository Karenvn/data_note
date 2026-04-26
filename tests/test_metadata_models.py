from __future__ import annotations

import unittest

from data_note.models import AnnotationInfo, TaxonomyInfo


class MetadataModelTests(unittest.TestCase):
    def test_taxonomy_info_round_trips_legacy_parts(self) -> None:
        taxonomy = TaxonomyInfo.from_legacy_parts(
            tax_id="12345",
            lineage_data={
                "species": "Example species",
                "lineage": "Eukaryota; Arthropoda",
                "class": "Insecta",
                "order": "Coleoptera",
                "family": "Elateridae",
                "genus": "Denticollis",
                "ncbi_extra": "keep me",
            },
            gbif_data={
                "tax_auth": "(Linnaeus, 1758)",
                "common_name": "example beetle",
                "gbif_url": "https://gbif.example/species/12345",
                "gbif_match_strategy": "GBIF_MATCH_EXACT",
                "gbif_extra": "also keep me",
            },
        )

        self.assertEqual(taxonomy.tax_id, "12345")
        self.assertEqual(taxonomy.class_name, "Insecta")
        self.assertEqual(taxonomy.tax_auth, "(Linnaeus, 1758)")
        self.assertEqual(taxonomy.extras["ncbi_extra"], "keep me")
        self.assertEqual(taxonomy.extras["gbif_extra"], "also keep me")

        context = taxonomy.to_context_dict()
        self.assertEqual(context["tax_id"], "12345")
        self.assertEqual(context["class"], "Insecta")
        self.assertEqual(context["common_name"], "example beetle")
        self.assertEqual(context["ncbi_extra"], "keep me")

    def test_annotation_info_preserves_unknown_fields(self) -> None:
        annotation = AnnotationInfo.from_mapping(
            {
                "annot_url": "https://beta.ensembl.org/species/example",
                "annot_accession": "GCA_123.1",
                "genes": "10 000",
                "ensembl_source": "ensembl_organisms",
                "custom_annotation_field": "keep me",
            }
        )

        self.assertEqual(annotation.annot_accession, "GCA_123.1")
        self.assertEqual(annotation.genes, "10 000")
        self.assertEqual(annotation.extras["custom_annotation_field"], "keep me")

        context = annotation.to_context_dict()
        self.assertEqual(context["annot_url"], "https://beta.ensembl.org/species/example")
        self.assertEqual(context["custom_annotation_field"], "keep me")


if __name__ == "__main__":
    unittest.main()
