from __future__ import annotations

import unittest

from data_note.models import BarcodingInfo, CurationInfo, ExtractionInfo


class CurationModelTests(unittest.TestCase):
    def test_to_context_dict_includes_ticket_and_fields(self) -> None:
        curation = CurationInfo.from_legacy_parts(
            jira_ticket="GRIT-1000",
            jira_fields={
                "manual_breaks": 2,
                "manual_joins": 1,
                "breaks_text": "two breaks",
            },
        )

        context = curation.to_context_dict()

        self.assertEqual(context["jira"], "GRIT-1000")
        self.assertEqual(context["manual_breaks"], 2)
        self.assertEqual(context["breaks_text"], "two breaks")

    def test_empty_curation_info_flattens_to_empty_context(self) -> None:
        self.assertEqual(CurationInfo().to_context_dict(), {})

    def test_extraction_info_round_trips_legacy_keys(self) -> None:
        extraction = ExtractionInfo.from_mapping(
            {
                "sequencing_date": "2026-01-02",
                "dna_yield_ng": "10,000",
                "gqn": "42",
                "protocol": "MagAttract",
                "extra_field": "kept",
            }
        )

        context = extraction.to_context_dict()

        self.assertEqual(context["sequencing_date"], "2026-01-02")
        self.assertEqual(context["dna_yield_ng"], "10,000")
        self.assertEqual(context["gqn"], "42")
        self.assertEqual(context["protocol"], "MagAttract")
        self.assertEqual(context["extra_field"], "kept")

    def test_barcoding_info_round_trips_legacy_keys(self) -> None:
        barcoding = BarcodingInfo.from_mapping(
            {
                "sts_tremoved": "Y",
                "barcode_hub": "BOLD",
                "sample_set_id": "SS-123",
            }
        )

        context = barcoding.to_context_dict()

        self.assertEqual(context["sts_tremoved"], "Y")
        self.assertEqual(context["barcode_hub"], "BOLD")
        self.assertEqual(context["sample_set_id"], "SS-123")


if __name__ == "__main__":
    unittest.main()
