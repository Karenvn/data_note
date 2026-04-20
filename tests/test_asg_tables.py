from __future__ import annotations

import unittest

from data_note.tables.asg import make_table5_rows, make_table6_rows


class AsgTableTests(unittest.TestCase):
    def test_make_table5_rows_is_omitted_without_metagenome(self) -> None:
        self.assertIsNone(make_table5_rows({"species": "Example species"}))

    def test_make_table5_rows_builds_from_metagenome_rows(self) -> None:
        table = make_table5_rows(
            {
                "species": "Example species",
                "has_metagenome": True,
                "metagenome_table_headers": [
                    "**Bin**",
                    "**Taxon**",
                    "**Completeness (%)**",
                ],
                "metagenome_table_rows": [
                    ["bin-01", "Gammaproteobacteria", "97.4"],
                    ["bin-02", "Bacteroidia", "91.0"],
                ],
            }
        )

        self.assertIsNotNone(table)
        assert table is not None
        self.assertEqual(table["label"], "tbl:table5")
        self.assertEqual(table["native_headers"][0], "**Bin**")
        self.assertEqual(table["native_rows"][0][0], "bin-01")

    def test_make_table6_rows_uses_software_table_numbering(self) -> None:
        table = make_table6_rows({"species": "Example species"})

        self.assertEqual(table["label"], "tbl:table6")
        self.assertEqual(table["native_headers"], ["**Software**", "**Version**", "**Source**"])


if __name__ == "__main__":
    unittest.main()
