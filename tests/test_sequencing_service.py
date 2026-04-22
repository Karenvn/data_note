from __future__ import annotations

import unittest

import pandas as pd

from data_note.models import RunGroup, RunRecord, SequencingSummary, SequencingTotals, TechnologyRecord
from data_note.services.sequencing_fetch_service import SequencingFetchResult, SequencingFetchService
from data_note.services.sequencing_service import SequencingService


class StubSequencingFetchService(SequencingFetchService):
    def __init__(self, dataframe: pd.DataFrame) -> None:
        super().__init__(session_get=lambda *args, **kwargs: None)
        self._dataframe = dataframe

    def fetch_for_bioprojects_with_sources(self, bioprojects: list[str]) -> SequencingFetchResult:
        return SequencingFetchResult(dataframe=self._dataframe, source_accessions=bioprojects)


class SequencingServiceTests(unittest.TestCase):
    def test_empty_context_returns_typed_summary(self) -> None:
        service = SequencingService()

        summary = service.empty_context()
        context = summary.to_context_dict()

        self.assertIsInstance(summary, SequencingSummary)
        self.assertEqual(summary.pacbio_protocols, [])
        self.assertIsInstance(summary.technology("pacbio"), TechnologyRecord)
        self.assertIsInstance(summary.run_group("PacBio"), RunGroup)
        self.assertIsInstance(summary.totals, SequencingTotals)
        self.assertEqual(context["technology_data"]["pacbio"], {})
        self.assertEqual(context["technology_data"]["hic"], {})
        self.assertEqual(context["seq_data"]["PacBio"], [])
        self.assertEqual(context["seq_data"]["Hi-C"], [])
        self.assertEqual(context["pacbio_reads_millions"], "0.00")
        self.assertEqual(context["pacbio_run_accessions"], "")

    def test_build_context_returns_typed_summary(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR1",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 1_073_741_824,
                    "submitted_bytes": 2_147_483_648,
                    "read_count": 1_234_567,
                    "instrument_model": "REVIO",
                    "base_count": 2_500_000_000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB1",
                    "library_construction_protocol": "PROTO1",
                }
            ]
        )
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            biosample_tolid_getter=lambda biosamples: {"SAMEA1": "ixFooBar1"},
        )

        summary = service.build_context(["PRJEB1"], "ixFooBar1")
        context = summary.to_context_dict()

        self.assertIsInstance(summary, SequencingSummary)
        self.assertIsInstance(summary.technology("pacbio"), TechnologyRecord)
        self.assertIsInstance(summary.run_group("PacBio"), RunGroup)
        self.assertIsInstance(summary.run_group("PacBio").runs[0], RunRecord)
        self.assertIsInstance(summary.totals, SequencingTotals)
        self.assertEqual(summary.pacbio_library_name(), "LIB1")
        self.assertEqual(summary.technology("pacbio").sample_accession, "SAMEA1")
        self.assertEqual(summary.technology("pacbio").instrument_model, "REVIO")
        self.assertEqual(summary.technology("pacbio").read_count_millions, "1.23")
        self.assertEqual(summary.run_group("PacBio").runs[0].read_accession, "ERR1")
        self.assertEqual(summary.run_group("PacBio").runs[0].read_count, "1.23e+06")
        self.assertEqual(summary.totals.pacbio_reads_millions, "1.23")
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_sample_accession"], "SAMEA1")
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_instrument_model"], "REVIO")
        self.assertEqual(context["seq_data"]["PacBio"][0]["read_accession"], "ERR1")
        self.assertEqual(context["pacbio_reads_millions"], "1.23")
        self.assertEqual(context["pacbio_protocols"], ["PROTO1"])
        self.assertEqual(context["pacbio_run_accessions"], "ERR1")

    def test_build_context_filters_pacbio_rows_by_tolid(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_MATCH",
                    "sample_accession": "SAMEA_MATCH",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "REVIO",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_MATCH",
                    "library_construction_protocol": "PROTO_MATCH",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_OTHER",
                    "sample_accession": "SAMEA_OTHER",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "REVIO",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_OTHER",
                    "library_construction_protocol": "PROTO_OTHER",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_HIC",
                    "sample_accession": "SAMEA_HIC",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "NovaSeq",
                    "base_count": 2000,
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "Hi-C",
                    "library_name": "LIB_HIC",
                    "library_construction_protocol": "",
                },
            ]
        )
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            biosample_tolid_getter=lambda biosamples: {
                "SAMEA_MATCH": "ixFooBar1",
                "SAMEA_OTHER": "ixOtherBar1",
                "SAMEA_HIC": "ixOtherBar1",
            },
        )

        summary = service.build_context(["PRJEB1"], "ixFooBar1")

        self.assertEqual(
            [run.read_accession for run in summary.run_group("PacBio").runs],
            ["ERR_MATCH"],
        )
        self.assertEqual(
            [run.read_accession for run in summary.run_group("Hi-C").runs],
            ["ERR_HIC"],
        )

    def test_build_context_processes_only_projects_with_read_data(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB85043",
                    "run_accession": "ERR1",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 1_073_741_824,
                    "submitted_bytes": 2_147_483_648,
                    "read_count": 1_234_567,
                    "instrument_model": "REVIO",
                    "base_count": 2_500_000_000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB1",
                    "library_construction_protocol": "PROTO1",
                }
            ]
        )
        fetch_service = StubSequencingFetchService(runinfo_df)
        fetch_service.fetch_for_bioprojects_with_sources = lambda bioprojects: SequencingFetchResult(
            dataframe=runinfo_df,
            source_accessions=["PRJEB85043"],
        )
        service = SequencingService(
            fetch_service=fetch_service,
            biosample_tolid_getter=lambda biosamples: {"SAMEA1": "ixFooBar1"},
        )

        with self.assertLogs("data_note.services.sequencing_service", level="INFO") as logs:
            summary = service.build_context(["PRJEB85043", "PRJEB86086", "PRJEB86087"], "ixFooBar1")

        self.assertEqual(summary.run_group("PacBio").runs[0].read_accession, "ERR1")
        combined_logs = "\n".join(logs.output)
        self.assertIn(
            "Scanning sequencing BioProject candidate(s): PRJEB85043, PRJEB86086, PRJEB86087.",
            combined_logs,
        )
        self.assertIn(
            "Processing sequencing information for bioproject(s): PRJEB85043.",
            combined_logs,
        )


if __name__ == "__main__":
    unittest.main()
