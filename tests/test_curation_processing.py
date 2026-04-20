from __future__ import annotations

import unittest

from data_note.models import BarcodingInfo, ExtractionInfo
from data_note.orchestrator import DataNoteOrchestrator
from data_note.services.curation_service import CurationService


class CurationProcessingTests(unittest.TestCase):
    def test_process_extraction_info_returns_typed_extraction_info(self) -> None:
        orchestrator = DataNoteOrchestrator(profile="darwin")
        orchestrator.curation_service = CurationService(
            sequencing_extraction_fetcher=lambda lookup_id: (
                {"sequencing_date": "2026-01-05", "submission_id": "SUB1"},
                {
                    "dna_yield_ng": "8,000",
                    "qubit_ngul": "10.5",
                    "protocol": "MagAttract",
                },
            ),
            extraction_fallback_fetcher=lambda lookup_id: {"gqn": "40"},
            barcoding_fetcher=lambda tolid: {},
        )

        extraction = orchestrator.process_extraction_info("LIB1")
        context = extraction.to_context_dict()

        self.assertIsInstance(extraction, ExtractionInfo)
        self.assertEqual(context["sequencing_date"], "2026-01-05")
        self.assertEqual(context["submission_id"], "SUB1")
        self.assertEqual(context["dna_yield_ng"], "8,000")
        self.assertEqual(context["protocol"], "MagAttract")
        self.assertEqual(context["gqn"], "40")

    def test_process_barcoding_info_returns_typed_barcoding_info(self) -> None:
        orchestrator = DataNoteOrchestrator(profile="darwin")
        orchestrator.curation_service = CurationService(
            sequencing_extraction_fetcher=lambda lookup_id: ({}, {}),
            extraction_fallback_fetcher=lambda lookup_id: {},
            barcoding_fetcher=lambda tolid: {
                "sts_tremoved": "Y",
                "barcode_hub": "BOLD",
                "eln_id": "ELN-1",
            },
        )

        barcoding = orchestrator.process_barcoding_info("ixExample1")
        context = barcoding.to_context_dict()

        self.assertIsInstance(barcoding, BarcodingInfo)
        self.assertEqual(context["sts_tremoved"], "Y")
        self.assertEqual(context["barcode_hub"], "BOLD")
        self.assertEqual(context["eln_id"], "ELN-1")


if __name__ == "__main__":
    unittest.main()
