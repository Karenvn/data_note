from __future__ import annotations

import unittest

import pandas as pd

from data_note.models import RunGroup, RunRecord, SequencingSummary, TechnologyRecord
from data_note.services.sequencing_service import SequencingService


class SequencingServiceTests(unittest.TestCase):
    def test_empty_context_returns_typed_summary(self) -> None:
        service = SequencingService(
            columns_selector=lambda df: df,
            technology_extractor=lambda df: {"pacbio": {}},
            sequencing_organiser=lambda df: {"PacBio": []},
            totals_summariser=lambda df, technology_data: {"pacbio_reads_millions": "0"},
            run_accession_getter=lambda seq_data: {"pacbio_run_accessions": ""},
        )

        summary = service.empty_context()
        context = summary.to_context_dict()

        self.assertIsInstance(summary, SequencingSummary)
        self.assertEqual(summary.pacbio_protocols, [])
        self.assertIsInstance(summary.technology("pacbio"), TechnologyRecord)
        self.assertIsInstance(summary.run_group("PacBio"), RunGroup)
        self.assertEqual(context["technology_data"], {"pacbio": {}})
        self.assertEqual(context["seq_data"], {"PacBio": []})
        self.assertEqual(context["pacbio_reads_millions"], "0")

    def test_build_context_returns_typed_summary(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "sample_accession": "SAMEA1",
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB1",
                }
            ]
        )
        service = SequencingService(
            runinfo_fetcher=lambda bioprojects: runinfo_df,
            biosample_tolid_getter=lambda biosamples: {"SAMEA1": "ixFooBar1"},
            pacbio_filter=lambda df, tolid, biosample_tolid_map: df,
            columns_selector=lambda df: df,
            technology_extractor=lambda df: {
                "pacbio": {
                    "pacbio_library_name": "LIB1",
                    "pacbio_sample_accession": "SAMEA1",
                }
            },
            sequencing_organiser=lambda df: {"PacBio": [{"read_accession": "ERR1"}]},
            totals_summariser=lambda df, technology_data: {"pacbio_reads_millions": "12.3"},
            pacbio_protocol_checker=lambda df: ["PROTO1"],
            run_accession_getter=lambda seq_data: {"pacbio_run_accessions": "ERR1"},
        )

        summary = service.build_context(["PRJEB1"], "ixFooBar1")
        context = summary.to_context_dict()

        self.assertIsInstance(summary, SequencingSummary)
        self.assertIsInstance(summary.technology("pacbio"), TechnologyRecord)
        self.assertIsInstance(summary.run_group("PacBio"), RunGroup)
        self.assertIsInstance(summary.run_group("PacBio").runs[0], RunRecord)
        self.assertEqual(summary.pacbio_library_name(), "LIB1")
        self.assertEqual(summary.technology("pacbio").sample_accession, "SAMEA1")
        self.assertEqual(summary.run_group("PacBio").runs[0].read_accession, "ERR1")
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_sample_accession"], "SAMEA1")
        self.assertEqual(context["seq_data"]["PacBio"][0]["read_accession"], "ERR1")
        self.assertEqual(context["pacbio_reads_millions"], "12.3")
        self.assertEqual(context["pacbio_protocols"], ["PROTO1"])
        self.assertEqual(context["pacbio_run_accessions"], "ERR1")


if __name__ == "__main__":
    unittest.main()
