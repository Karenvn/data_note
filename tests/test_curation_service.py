from __future__ import annotations

import unittest

from data_note.models import AssemblyRecord, AssemblySelection, BarcodingInfo, CurationBundle, CurationInfo, ExtractionInfo
from data_note.services.curation_service import CurationService


class _LocalMetadataService:
    def build_context(self, assembly_selection, *, tolid=None, species=None):
        return CurationInfo.from_legacy_parts(
            jira_ticket="GRIT-1000",
            jira_fields={"manual_breaks": 2},
        )


class CurationServiceTests(unittest.TestCase):
    def test_build_context_combines_local_metadata_extraction_and_barcoding(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )
        service = CurationService(
            local_metadata_service=_LocalMetadataService(),
            sequencing_extraction_fetcher=lambda lookup_id: (
                {"sequencing_date": "2026-01-01"},
                {"dna_yield_ng": "10,000"},
            ),
            extraction_fallback_fetcher=lambda lookup_id: {"gqn": "40"},
            barcoding_fetcher=lambda tolid: {"sts_tremoved": "Y", "sample_set_id": "SS-1"},
        )

        bundle = service.build_context(
            selection,
            species="Example species",
            tolid="ixExample1",
            extraction_lookup_id="LIB1",
        )
        context = bundle.to_context_dict()

        self.assertIsInstance(bundle, CurationBundle)
        self.assertEqual(context["jira"], "GRIT-1000")
        self.assertEqual(context["manual_breaks"], 2)
        self.assertEqual(context["sequencing_date"], "2026-01-01")
        self.assertEqual(context["dna_yield_ng"], "10,000")
        self.assertEqual(context["gqn"], "40")
        self.assertEqual(context["sts_tremoved"], "Y")
        self.assertEqual(context["sample_set_id"], "SS-1")

    def test_build_extraction_returns_empty_when_lookup_missing(self) -> None:
        service = CurationService(
            local_metadata_service=_LocalMetadataService(),
            sequencing_extraction_fetcher=lambda lookup_id: ({}, {}),
            extraction_fallback_fetcher=lambda lookup_id: {},
            barcoding_fetcher=lambda tolid: {},
        )

        extraction = service.build_extraction(None)

        self.assertIsInstance(extraction, ExtractionInfo)
        self.assertEqual(extraction.to_context_dict(), {})

    def test_build_barcoding_returns_empty_when_tolid_missing(self) -> None:
        service = CurationService(
            local_metadata_service=_LocalMetadataService(),
            sequencing_extraction_fetcher=lambda lookup_id: ({}, {}),
            extraction_fallback_fetcher=lambda lookup_id: {},
            barcoding_fetcher=lambda tolid: {"sts_tremoved": "Y"},
        )

        barcoding = service.build_barcoding(None)

        self.assertIsInstance(barcoding, BarcodingInfo)
        self.assertEqual(barcoding.to_context_dict(), {})


if __name__ == "__main__":
    unittest.main()
