from __future__ import annotations

import unittest

from data_note.models import BarcodingInfo, ExtractionInfo
from data_note.services.curation_service import CurationService


class CurationProcessingTests(unittest.TestCase):
    def test_process_extraction_info_returns_typed_extraction_info(self) -> None:
        service = CurationService(
            sequencing_extraction_fetcher=lambda lookup_id: (
                {"sequencing_date": "2026-01-05", "submission_id": "SUB1"},
                {
                    "dna_yield_ng": "8,000",
                    "qubit_ngul": "10.5",
                    "protocol": "MagAttract",
                },
            ),
            extraction_fallback_fetcher=lambda lookup_id: {"gqn": "40", "tissue_weight_mg": 84, "tissue_type": "Plant"},
            barcoding_fetcher=lambda tolid: {},
        )

        extraction = service.build_extraction("LIB1")
        context = extraction.to_context_dict()

        self.assertIsInstance(extraction, ExtractionInfo)
        self.assertEqual(context["sequencing_date"], "2026-01-05")
        self.assertEqual(context["submission_id"], "SUB1")
        self.assertEqual(context["dna_yield_ng"], "8,000")
        self.assertEqual(context["protocol"], "MagAttract")
        self.assertEqual(context["gqn"], "40")
        self.assertEqual(context["tissue_weight_mg"], 84)
        self.assertEqual(context["tissue_type"], "Plant")

    def test_process_extraction_info_retries_fallback_with_sanger_sample_id(self) -> None:
        calls: list[str] = []

        def fallback_fetcher(lookup_id: str) -> dict[str, object]:
            calls.append(lookup_id)
            if lookup_id == "DTOL13262041":
                return {
                    "extraction_protocol": "MagAttract Standard 48xrn",
                    "disruption_method": "Powermash",
                    "spri_type": "1x ProNex (manual)",
                }
            return {}

        service = CurationService(
            sequencing_extraction_fetcher=lambda lookup_id: (
                {"sanger_sample_id": "DTOL13262041"},
                {},
            ),
            extraction_fallback_fetcher=fallback_fetcher,
            barcoding_fetcher=lambda tolid: {},
        )

        extraction = service.build_extraction("fCheLab1")
        context = extraction.to_context_dict()

        self.assertEqual(calls, ["fCheLab1", "DTOL13262041"])
        self.assertEqual(context["sanger_sample_id"], "DTOL13262041")
        self.assertEqual(context["extraction_protocol"], "MagAttract Standard 48xrn")
        self.assertEqual(context["disruption_method"], "Powermash")
        self.assertEqual(context["spri_type"], "1x ProNex (manual)")

    def test_process_extraction_info_replaces_zero_tissue_weight_with_fallback_value(self) -> None:
        service = CurationService(
            sequencing_extraction_fetcher=lambda lookup_id: (
                {},
                {
                    "dna_yield_ng": "8,000",
                    "qubit_ngul": "10.5",
                    "volume_ul": "45",
                    "ratio_260_280": "1.74",
                    "ratio_260_230": "2.14",
                    "fragment_size_kb": "11.9",
                    "extraction_date": "2026-01-05",
                    "tissue_weight_mg": 0,
                },
            ),
            extraction_fallback_fetcher=lambda lookup_id: {
                "tissue_weight_mg": "25",
                "tissue_type": "Non-plant",
            },
            barcoding_fetcher=lambda tolid: {},
        )

        extraction = service.build_extraction("fCycLum2")
        context = extraction.to_context_dict()

        self.assertEqual(context["tissue_weight_mg"], "25")
        self.assertEqual(context["tissue_type"], "Non-plant")

    def test_process_barcoding_info_returns_typed_barcoding_info(self) -> None:
        service = CurationService(
            sequencing_extraction_fetcher=lambda lookup_id: ({}, {}),
            extraction_fallback_fetcher=lambda lookup_id: {},
            barcoding_fetcher=lambda tolid: {
                "sts_tremoved": "Y",
                "barcode_hub": "BOLD",
                "eln_id": "ELN-1",
            },
        )

        barcoding = service.build_barcoding("ixExample1")
        context = barcoding.to_context_dict()

        self.assertIsInstance(barcoding, BarcodingInfo)
        self.assertEqual(context["sts_tremoved"], "Y")
        self.assertEqual(context["barcode_hub"], "BOLD")
        self.assertEqual(context["eln_id"], "ELN-1")


if __name__ == "__main__":
    unittest.main()
