from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from data_note.process_sequencing_info import (
    fetch_read_runs_for_bioproject,
    fetch_runinfo_for_bioprojects,
    fetch_sra_summary_rows_for_accession,
)


class ProcessSequencingInfoTests(unittest.TestCase):
    @patch("data_note.process_sequencing_info.DEFAULT_SEQUENCING_FETCH_SERVICE")
    def test_fetch_read_runs_for_bioproject_delegates_to_fetch_service(self, mock_service: Mock) -> None:
        mock_service.fetch_read_runs_for_bioproject.return_value = [
            {"run_accession": "ERR1", "study_accession": "PRJEB1"}
        ]

        rows = fetch_read_runs_for_bioproject("PRJEB1")

        self.assertEqual(rows, [{"run_accession": "ERR1", "study_accession": "PRJEB1"}])
        mock_service.fetch_read_runs_for_bioproject.assert_called_once_with("PRJEB1")

    @patch("data_note.process_sequencing_info.DEFAULT_SEQUENCING_FETCH_SERVICE")
    def test_fetch_runinfo_for_bioprojects_delegates_to_fetch_service(self, mock_service: Mock) -> None:
        mock_service.fetch_for_bioprojects.return_value = pd.DataFrame([{"run_accession": "ERR1"}])

        df = fetch_runinfo_for_bioprojects(["PRJEB1"])

        self.assertEqual(df["run_accession"].tolist(), ["ERR1"])
        mock_service.fetch_for_bioprojects.assert_called_once_with(["PRJEB1"])

    @patch("data_note.process_sequencing_info.DEFAULT_SEQUENCING_FETCH_SERVICE")
    def test_fetch_sra_summary_rows_for_accession_delegates_to_fetch_service(self, mock_service: Mock) -> None:
        mock_service.fetch_sra_summary_rows_for_accession.return_value = [
            {"run_accession": "ERR1", "study_accession": "PRJEB1"}
        ]

        rows = fetch_sra_summary_rows_for_accession("PRJEB1")

        self.assertEqual(rows, [{"run_accession": "ERR1", "study_accession": "PRJEB1"}])
        mock_service.fetch_sra_summary_rows_for_accession.assert_called_once_with("PRJEB1")


if __name__ == "__main__":
    unittest.main()
