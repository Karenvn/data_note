from __future__ import annotations

import unittest

from data_note.local_metadata_provider import PortalCurationMetadataProvider


class _CurationObject:
    def __init__(self, identifier: str, attributes: dict[str, object]) -> None:
        self.id = identifier
        self.attributes = attributes


class PortalCurationMetadataProviderTests(unittest.TestCase):
    def test_select_identifier_prefers_done_curation_over_cancelled(self) -> None:
        curations = [
            _CurationObject("RC-1201", {"grit_status": "Cancelled"}),
            _CurationObject("RC-1254", {"grit_status": "Done"}),
        ]

        selected = PortalCurationMetadataProvider._select_identifier(curations)

        self.assertEqual(selected, "RC-1254")

    def test_select_identifier_uses_latest_done_curation(self) -> None:
        curations = [
            _CurationObject("RC-1000", {"grit_status": "Done", "done_date": "2026-01-01"}),
            _CurationObject("RC-1001", {"grit_status": "Done", "done_date": "2026-01-02"}),
        ]

        selected = PortalCurationMetadataProvider._select_identifier(curations)

        self.assertEqual(selected, "RC-1001")


if __name__ == "__main__":
    unittest.main()
