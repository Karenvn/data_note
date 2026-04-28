from __future__ import annotations

import unittest

from data_note.fetch_biosample_info import (
    normalize_collection_date,
    normalize_pipe_delimited_values,
    process_biosamples_sample_dict,
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

    def test_process_biosamples_sample_dict_deduplicates_identifier_and_affiliation(self) -> None:
        row = {
            "identified_by": "DAVID LEES | DAVID LEES",
            "identifier_affiliation": "NATURAL HISTORY MUSEUM | NATURAL HISTORY MUSEUM",
        }

        processed = process_biosamples_sample_dict(row, "pacbio")

        self.assertEqual(processed["pacbio_identifier"], "David Lees")
        self.assertEqual(processed["pacbio_identifier_affiliation"], "Natural History Museum")


if __name__ == "__main__":
    unittest.main()
