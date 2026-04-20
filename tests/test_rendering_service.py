from __future__ import annotations

import unittest

from data_note.services.rendering_service import RenderingService


class RenderingServiceTests(unittest.TestCase):
    def test_resolve_btk_accession_prefers_primary_then_hap1(self) -> None:
        self.assertEqual(
            RenderingService._resolve_btk_accession(
                {"prim_accession": "GCA_1.1", "hap1_accession": "GCA_h1"}
            ),
            "GCA_1.1",
        )
        self.assertEqual(
            RenderingService._resolve_btk_accession({"hap1_accession": "GCA_h1"}),
            "GCA_h1",
        )
        self.assertIsNone(RenderingService._resolve_btk_accession({}))


if __name__ == "__main__":
    unittest.main()
