from __future__ import annotations

import unittest

from data_note.models import AnnotationInfo
from data_note.services.annotation_service import AnnotationService


class _AnnotationFetcherStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def fetch_annotation(self, assembly_accession: str, species: str, tax_id: str) -> dict[str, str]:
        self.calls.append((assembly_accession, species, tax_id))
        return {
            "annot_url": "https://beta.ensembl.org/species/example",
            "annot_accession": assembly_accession,
            "genes": "12 345",
            "ensembl_annotation_url": "https://beta.ensembl.org/species/example",
        }


class AnnotationServiceTests(unittest.TestCase):
    def test_build_context_returns_annotation_info(self) -> None:
        fetcher = _AnnotationFetcherStub()
        service = AnnotationService(annotation_fetcher=fetcher)
        annotation = service.build_context("GCA_1.1", "Example species", "12345")

        self.assertIsInstance(annotation, AnnotationInfo)
        self.assertEqual(fetcher.calls, [("GCA_1.1", "Example species", "12345")])
        self.assertEqual(annotation.annot_accession, "GCA_1.1")
        self.assertEqual(annotation.genes, "12 345")

    def test_build_context_returns_empty_when_accession_missing(self) -> None:
        service = AnnotationService(annotation_fetcher=_AnnotationFetcherStub())

        annotation = service.build_context(None, "Example species", "12345")

        self.assertIsInstance(annotation, AnnotationInfo)
        self.assertEqual(annotation.to_context_dict(), {})


if __name__ == "__main__":
    unittest.main()
