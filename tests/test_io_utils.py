from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from data_note.io_utils import read_bioprojects_input


class IoUtilsTests(unittest.TestCase):
    def test_read_bioprojects_input_accepts_single_bioproject_accession(self) -> None:
        self.assertEqual(read_bioprojects_input("PRJEB12345"), ["PRJEB12345"])

    def test_read_bioprojects_input_reads_bioprojects_from_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("PRJEB12345\nPRJEB67890\n")
            bioproject_file = handle.name
        try:
            self.assertEqual(
                read_bioprojects_input(bioproject_file),
                ["PRJEB12345", "PRJEB67890"],
            )
        finally:
            Path(bioproject_file).unlink()

    def test_read_bioprojects_input_rejects_missing_non_bioproject_value(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read_bioprojects_input("not_a_bioproject_or_file")


if __name__ == "__main__":
    unittest.main()
