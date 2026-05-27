from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from data_note.services.sequencing_fetch_service import SequencingFetchService


class SequencingFetchServiceTests(unittest.TestCase):
    @patch("data_note.services.sequencing_fetch_service.requests.get")
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

        service = SequencingFetchService(session_get=mock_get)
        rows = service.fetch_read_runs_for_bioproject("PRJEB1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_accession"], "ERR1")
        self.assertEqual(rows[0]["study_accession"], "PRJEB1")

    def test_fetch_for_bioprojects_falls_back_to_ena_when_ncbi_sources_are_empty(self) -> None:
        service = SequencingFetchService()
        ena_rows = [
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

        with patch.object(SequencingFetchService, "fetch_runinfo_rows_for_accession", return_value=[]) as mock_runinfo:
            with patch.object(
                SequencingFetchService, "fetch_sra_summary_rows_for_accession", return_value=[]
            ) as mock_summary:
                with patch.object(
                    SequencingFetchService, "fetch_read_runs_for_bioproject", return_value=ena_rows
                ) as mock_ena:
                    result = service.fetch_for_bioprojects_with_sources(["PRJEB1"])

        self.assertEqual(result.dataframe["run_accession"].tolist(), ["ERR1"])
        self.assertEqual(result.source_accessions, ["PRJEB1"])
        mock_runinfo.assert_called_once_with("PRJEB1")
        mock_summary.assert_called_once_with("PRJEB1")
        mock_ena.assert_called_once_with("PRJEB1")

    def test_fetch_rows_for_accession_augments_ncbi_rows_with_ena_alias_fields(self) -> None:
        service = SequencingFetchService()
        ncbi_rows = [
            {
                "run_accession": "ERR1",
                "sample_accession": "SAMEA1",
                "submitted_ftp": "",
                "metadata_source": "ncbi_runinfo",
            }
        ]
        ena_rows = [
            {
                "run_accession": "ERR1",
                "run_alias": "SC_RUN_12345_6#7",
                "experiment_alias": "SC_EXP_12345_6#7",
                "library_source": "GENOMIC",
                "library_selection": "Restriction Digest",
                "submitted_ftp": "ftp.sra.ebi.ac.uk/example/12345_6#7.cram",
                "metadata_source": "ena",
            }
        ]

        with patch.object(SequencingFetchService, "fetch_runinfo_rows_for_accession", return_value=ncbi_rows):
            with patch.object(
                SequencingFetchService, "fetch_sra_summary_rows_for_accession"
            ) as mock_summary:
                with patch.object(
                    SequencingFetchService, "fetch_read_runs_for_bioproject", return_value=ena_rows
                ):
                    rows = service.fetch_rows_for_accession("PRJEB1")

        self.assertEqual(rows[0]["run_alias"], "SC_RUN_12345_6#7")
        self.assertEqual(rows[0]["library_selection"], "Restriction Digest")
        self.assertEqual(rows[0]["submitted_ftp"], "ftp.sra.ebi.ac.uk/example/12345_6#7.cram")
        self.assertEqual(rows[0]["metadata_source"], "ncbi_runinfo")
        self.assertEqual(rows[0]["supplementary_metadata_source"], "ena")
        mock_summary.assert_not_called()

    def test_fetch_for_bioprojects_with_sources_omits_accessions_without_runs(self) -> None:
        service = SequencingFetchService()
        rows_by_accession = {
            "PRJEB85043": [
                {
                    "run_accession": "ERR1",
                    "sample_accession": "SAMEA1",
                }
            ],
            "PRJEB86086": [],
            "PRJEB86087": [],
        }

        with patch.object(
            SequencingFetchService,
            "fetch_rows_for_accession",
            side_effect=lambda accession: rows_by_accession[accession],
        ) as mock_fetch:
            result = service.fetch_for_bioprojects_with_sources(["PRJEB85043", "PRJEB86086", "PRJEB86087"])

        self.assertEqual(result.source_accessions, ["PRJEB85043"])
        self.assertEqual(result.dataframe["run_accession"].tolist(), ["ERR1"])
        self.assertEqual(mock_fetch.call_count, 3)

    def test_fetch_assembly_run_accessions_parses_assembly_run_list(self) -> None:
        mock_get = Mock(
            return_value=Mock(
                status_code=200,
                json=Mock(
                    return_value=[
                        {
                            "assembly_set_accession": "GCA_1.1",
                            "run_accession": "ERR1;ERR2; ERR3",
                        }
                    ]
                ),
            )
        )
        service = SequencingFetchService(session_get=mock_get)

        result = service.fetch_assembly_run_accessions(["GCA_1.1"])

        self.assertEqual(result, {"ERR1", "ERR2", "ERR3"})
        self.assertEqual(
            mock_get.call_args.kwargs["params"]["query"],
            'assembly_set_accession="GCA_1.1"',
        )

    def test_fetch_rows_for_accession_logs_single_debug_message_when_all_sources_are_empty(self) -> None:
        service = SequencingFetchService()

        with patch.object(SequencingFetchService, "fetch_runinfo_rows_for_accession", return_value=[]) as mock_runinfo:
            with patch.object(
                SequencingFetchService, "fetch_sra_summary_rows_for_accession", return_value=[]
            ) as mock_summary:
                with patch.object(
                    SequencingFetchService, "fetch_read_runs_for_bioproject", return_value=[]
                ) as mock_ena:
                    with self.assertLogs("data_note.services.sequencing_fetch_service", level="DEBUG") as logs:
                        rows = service.fetch_rows_for_accession("PRJEB83598")

        self.assertEqual(rows, [])
        self.assertIn(
            "No read-run metadata found for PRJEB83598 across SRA RunInfo, NCBI E-utilities, or ENA filereport.",
            "\n".join(logs.output),
        )
        mock_runinfo.assert_called_once_with("PRJEB83598")
        mock_summary.assert_called_once_with("PRJEB83598")
        mock_ena.assert_called_once_with("PRJEB83598")

    def test_fetch_for_bioprojects_with_sources_logs_once_when_all_candidates_are_empty(self) -> None:
        service = SequencingFetchService()

        with patch.object(SequencingFetchService, "fetch_rows_for_accession", return_value=[]) as mock_fetch:
            with self.assertLogs("data_note.services.sequencing_fetch_service", level="INFO") as logs:
                result = service.fetch_for_bioprojects_with_sources(["PRJEB86086", "PRJEB86087"])

        self.assertTrue(result.dataframe.empty)
        self.assertEqual(result.source_accessions, [])
        self.assertIn(
            "No read-run metadata found across BioProjects: PRJEB86086, PRJEB86087.",
            "\n".join(logs.output),
        )
        self.assertEqual(mock_fetch.call_count, 2)

    @patch("data_note.services.sequencing_fetch_service.requests.get")
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

        service = SequencingFetchService(session_get=mock_get)
        rows = service.fetch_sra_summary_rows_for_accession("PRJEB1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_accession"], "ERR1")
        self.assertEqual(rows[0]["study_accession"], "PRJEB1")
        self.assertEqual(rows[0]["secondary_study_accession"], "ERP1")
        self.assertEqual(rows[0]["instrument_platform"], "PACBIO_SMRT")


if __name__ == "__main__":
    unittest.main()
