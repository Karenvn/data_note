from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from data_note.process_sequencing_info import (
    fetch_read_runs_for_bioproject,
    fetch_runinfo_for_bioprojects,
    fetch_sra_summary_rows_for_accession,
)


class ProcessSequencingInfoTests(unittest.TestCase):
    @patch("data_note.process_sequencing_info.requests.get")
    def test_fetch_read_runs_for_bioproject_parses_tsv_rows(self, mock_get: Mock) -> None:
        mock_get.return_value = Mock(
            status_code=200,
            text=(
                "run_accession\tsample_accession\tsubmitted_bytes\tread_count\tbase_count\t"
                "library_strategy\tlibrary_name\tlibrary_construction_protocol\t"
                "instrument_platform\tinstrument_model\tstudy_accession\tsecondary_study_accession\n"
                "ERR1\tSAMEA1\t123\t456\t789\tWGS\tLIB1\tPROTO1\tPACBIO_SMRT\tREVIO\tPRJEB1\tERP1\n"
            ),
        )

        rows = fetch_read_runs_for_bioproject("PRJEB1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_accession"], "ERR1")
        self.assertEqual(rows[0]["study_accession"], "PRJEB1")

    @patch("data_note.process_sequencing_info.fetch_read_runs_for_bioproject")
    @patch("data_note.process_sequencing_info.fetch_sra_summary_rows_for_accession")
    @patch("data_note.process_sequencing_info.fetch_runinfo_rows_for_accession")
    def test_fetch_runinfo_for_bioprojects_falls_back_to_ena_when_ncbi_sources_are_empty(
        self,
        mock_runinfo: Mock,
        mock_summary: Mock,
        mock_ena: Mock,
    ) -> None:
        mock_runinfo.return_value = []
        mock_summary.return_value = []
        mock_ena.return_value = [
            {
                "run_accession": "ERR1",
                "sample_accession": "SAMEA1",
                "submitted_bytes": "123",
                "read_count": "456",
                "base_count": "789",
                "library_strategy": "WGS",
                "library_name": "LIB1",
                "library_construction_protocol": "PROTO1",
                "instrument_platform": "PACBIO_SMRT",
                "instrument_model": "REVIO",
                "study_accession": "PRJEB1",
                "secondary_study_accession": "ERP1",
            }
        ]

        df = fetch_runinfo_for_bioprojects(["PRJEB1"])

        self.assertEqual(df["run_accession"].tolist(), ["ERR1"])
        mock_runinfo.assert_called_once_with("PRJEB1")
        mock_summary.assert_called_once_with("PRJEB1")
        mock_ena.assert_called_once_with("PRJEB1")

    @patch("data_note.process_sequencing_info.requests.get")
    def test_fetch_sra_summary_rows_for_accession_parses_ncbi_esummary(self, mock_get: Mock) -> None:
        mock_get.side_effect = [
            Mock(
                status_code=200,
                json=Mock(return_value={"esearchresult": {"idlist": ["1"]}}),
            ),
            Mock(
                status_code=200,
                json=Mock(
                    return_value={
                        "result": {
                            "uids": ["1"],
                            "1": {
                                "expxml": (
                                    "<Summary>"
                                    "<Platform instrument_model=\"Revio\">PACBIO_SMRT</Platform>"
                                    "<Statistics total_spots=\"456\" total_bases=\"789\" total_size=\"123\"/>"
                                    "</Summary>"
                                    "<Study acc=\"ERP1\"/>"
                                    "<Library_descriptor>"
                                    "<LIBRARY_STRATEGY>WGS</LIBRARY_STRATEGY>"
                                    "<LIBRARY_NAME>LIB1</LIBRARY_NAME>"
                                    "<LIBRARY_CONSTRUCTION_PROTOCOL>PROTO1</LIBRARY_CONSTRUCTION_PROTOCOL>"
                                    "</Library_descriptor>"
                                    "<Bioproject>PRJEB1</Bioproject>"
                                    "<Biosample>SAMEA1</Biosample>"
                                ),
                                "runs": "<Run acc=\"ERR1\" total_spots=\"456\" total_bases=\"789\"/>",
                            },
                        }
                    }
                ),
            ),
        ]

        rows = fetch_sra_summary_rows_for_accession("PRJEB1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_accession"], "ERR1")
        self.assertEqual(rows[0]["study_accession"], "PRJEB1")
        self.assertEqual(rows[0]["secondary_study_accession"], "ERP1")
        self.assertEqual(rows[0]["instrument_platform"], "PACBIO_SMRT")


if __name__ == "__main__":
    unittest.main()
