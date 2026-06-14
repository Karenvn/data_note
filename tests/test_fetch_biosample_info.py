from __future__ import annotations

import unittest

from data_note.fetch_biosample_info import (
    format_elevation_m,
    normalize_collection_date,
    normalize_pipe_delimited_values,
    process_biosamples_sample_dict,
    title_preserving_possessives,
)


class FetchBiosampleInfoTests(unittest.TestCase):
    def test_normalize_pipe_delimited_values_deduplicates_repeated_entries(self) -> None:
        self.assertEqual(
            normalize_pipe_delimited_values("DAVID LEES | DAVID LEES"),
            "DAVID LEES",
        )

    def test_normalize_pipe_delimited_values_preserves_distinct_entries(self) -> None:
        self.assertEqual(
            normalize_pipe_delimited_values("Alice Able | Bob Baker"),
            "Alice Able | Bob Baker",
        )

    def test_normalize_collection_date_strips_placeholder_noon_timestamp(self) -> None:
        self.assertEqual(
            normalize_collection_date("2022-11-01T12:00:00"),
            "2022-11-01",
        )

    def test_normalize_collection_date_preserves_real_datetime(self) -> None:
        self.assertEqual(
            normalize_collection_date("2022-11-01T15:30:45"),
            "2022-11-01T15:30:45",
        )

    def test_process_biosamples_sample_dict_normalizes_collection_date(self) -> None:
        row = {
            "collection_date": "2022-11-01T12:00:00",
            "geographic_location_(region_and_locality)": "Berkshire | Wytham Woods",
            "geographic_location_(country_and/or_sea)": "United Kingdom",
            "geographic_location_(latitude)": "51.772",
            "geographic_location_(longitude)": "-1.338",
            "collected_by": "liam crowley",
            "collecting_institution": "university of oxford",
            "gal": "university of oxford",
        }

        processed = process_biosamples_sample_dict(row, "pacbio")

        self.assertEqual(processed["pacbio_coll_date"], "2022-11-01")

    def test_title_preserving_possessives_keeps_lowercase_possessive_s(self) -> None:
        self.assertEqual(
            title_preserving_possessives("Wytham Woods | Bert's Pheasant Pen"),
            "Wytham Woods | Bert's Pheasant Pen",
        )
        self.assertEqual(title_preserving_possessives("O'SULLIVAN"), "O'Sullivan")

    def test_process_biosamples_sample_dict_preserves_possessive_locality(self) -> None:
        row = {
            "geographic_location_(region_and_locality)": "Wytham Woods | Bert's Pheasant Pen",
            "geographic_location_(country_and/or_sea)": "United Kingdom",
        }

        processed = process_biosamples_sample_dict(row, "pacbio")

        self.assertEqual(
            processed["pacbio_coll_location"],
            "Bert's Pheasant Pen, Wytham Woods, United Kingdom",
        )

    def test_process_biosamples_sample_dict_deduplicates_identifier_and_affiliation(self) -> None:
        row = {
            "identified_by": "DAVID LEES | DAVID LEES",
            "identifier_affiliation": "NATURAL HISTORY MUSEUM | NATURAL HISTORY MUSEUM",
        }

        processed = process_biosamples_sample_dict(row, "pacbio")

        self.assertEqual(processed["pacbio_identifier"], "David Lees")
        self.assertEqual(processed["pacbio_identifier_affiliation"], "Natural History Museum")

    def test_format_elevation_m_preserves_recorded_zero(self) -> None:
        self.assertEqual(format_elevation_m("0"), "0")
        self.assertEqual(format_elevation_m("0.0 m"), "0")

    def test_format_elevation_m_leaves_missing_values_blank(self) -> None:
        for value in (None, "", "null", "not provided", "N/A"):
            with self.subTest(value=value):
                self.assertEqual(format_elevation_m(value), "")

    def test_process_biosamples_sample_dict_does_not_default_missing_elevation_to_zero(self) -> None:
        row = {
            "geographic_location_(region_and_locality)": "Simo | Kuralanletto",
            "geographic_location_(country_and/or_sea)": "Finland",
            "geographic_location_(latitude)": "65.6132896",
            "geographic_location_(longitude)": "24.9997768",
            "elevation": "null",
        }

        processed = process_biosamples_sample_dict(row, "pacbio")

        self.assertEqual(processed["pacbio_coll_lat"], 65.6133)
        self.assertEqual(processed["pacbio_coll_long"], 24.9998)
        self.assertEqual(processed["pacbio_elevation_m"], "")


if __name__ == "__main__":
    unittest.main()
