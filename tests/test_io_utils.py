from __future__ import annotations

from pathlib import Path
import json
import math
import tempfile
import unittest

import pandas as pd

from data_note.models import BaseNoteInfo, NoteData
from data_note.io_utils import dict_to_json, read_bioprojects_input


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

    def test_dict_to_json_writes_nested_context_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "context.json"
            dict_to_json(
                {
                    "species": "Example species",
                    "tables": {"table1": {"native_rows": [["A", 1]]}},
                    "path_value": Path("Fig_1.gif"),
                    "missing_value": pd.NA,
                    "nan_value": math.nan,
                    "set_value": {"b", "a"},
                },
                output_path,
            )

            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(data["species"], "Example species")
        self.assertEqual(data["tables"]["table1"]["native_rows"], [["A", 1]])
        self.assertEqual(data["path_value"], "Fig_1.gif")
        self.assertIsNone(data["missing_value"])
        self.assertIsNone(data["nan_value"])
        self.assertEqual(data["set_value"], ["a", "b"])

    def test_dict_to_json_writes_dataclass_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "note_data.json"
            dict_to_json(
                NoteData(base=BaseNoteInfo(bioproject="PRJEB12345", tolid="ixExample1")),
                output_path,
            )

            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(data["base"]["bioproject"], "PRJEB12345")
        self.assertEqual(data["base"]["tolid"], "ixExample1")
        self.assertIsNone(data["taxonomy"])


if __name__ == "__main__":
    unittest.main()
