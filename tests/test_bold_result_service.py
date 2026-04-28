from __future__ import annotations

from datetime import date
import unittest

from data_note.gbif_occurrence_client import GbifOccurrenceClient
from data_note.gbif_taxonomy_client import GbifTaxonomyClient
from data_note.services.bold_result_service import BoldResultService
from data_note.species_summary_models import GbifDistributionSummary, GbifFacetCount


class _GbifTaxonomyStub(GbifTaxonomyClient):
    def fetch_species_metadata(self, species_name: str, tax_id: str | None = None) -> dict[str, object]:
        return {"gbif_usage_key": "999"}


class _GbifOccurrenceStub(GbifOccurrenceClient):
    def fetch_distribution_summary(self, usage_key: int | str, *, facet_limit: int = 20) -> GbifDistributionSummary:
        return GbifDistributionSummary(
            usage_key=str(usage_key),
            record_count=12,
            countries=[
                GbifFacetCount(code="GR", label="Greece", count=9),
                GbifFacetCount(code="TR", label="Turkey", count=3),
            ],
            species_url="https://gbif.example/species/999",
        )


class BoldResultServiceTests(unittest.TestCase):
    def test_build_text_renders_mismatch_with_distribution(self) -> None:
        service = BoldResultService(
            workflow_runner=lambda accession: {
                "success": True,
                "mt_accession": "OZ217469.1",
                "bin_number": "BOLD:AAC3426",
                "bold_match": "Orthosia dalmatica",
                "bold_similarity": 96.94,
                "bold_process_id": "BGE_00150_D04",
            },
            gbif_taxonomy_client=_GbifTaxonomyStub(),
            gbif_occurrence_client=_GbifOccurrenceStub(),
            today_provider=lambda: date(2026, 4, 27),
        )

        text = service.build_text("GCA_123456789.1", "Orthosia cerasi")

        self.assertIn("mitochondrial assembly (OZ217469.1)", text)
        self.assertIn("BOLD cluster BOLD:AAC3426", text)
        self.assertIn("represented by BGE_00150_D04", text)
        self.assertIn("3.06%", text)
        self.assertIn("Greece and Turkey", text)

    def test_build_text_raises_for_failed_workflow(self) -> None:
        service = BoldResultService(
            workflow_runner=lambda accession: {
                "success": False,
                "error": "No mitochondrial sequence found in assembly metadata.",
            }
        )

        with self.assertRaises(RuntimeError):
            service.build_text("GCA_123456789.1", "Orthosia cerasi")
