from __future__ import annotations

import unittest

import pandas as pd

from data_note.models import RunGroup, RunRecord, SequencingSummary, SequencingTotals, TechnologyRecord
from data_note.services.sequencing_fetch_service import SequencingFetchResult, SequencingFetchService
from data_note.services.sequencing_portal_service import PortalSequencingService
from data_note.services.sequencing_service import SequencingService


class StubSequencingFetchService(SequencingFetchService):
    def __init__(self, dataframe: pd.DataFrame) -> None:
        super().__init__(session_get=lambda *args, **kwargs: None)
        self._dataframe = dataframe

    def fetch_for_bioprojects_with_sources(self, bioprojects: list[str]) -> SequencingFetchResult:
        return SequencingFetchResult(dataframe=self._dataframe, source_accessions=bioprojects)


class _PortalObject:
    def __init__(self, identifier: str, attributes: dict | None = None) -> None:
        self.id = identifier
        self.attributes = attributes or {}


class _PortalDatasource:
    def __init__(self, runs: list[_PortalObject]) -> None:
        self.runs = runs

    def get_by_id(self, object_type: str, identifiers: list[str]):
        return [_PortalObject(identifiers[0])]

    def get_to_many_relations(self, object_object, relation: str):
        return self.runs


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
            sequencing_source="public",
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
            sequencing_source="public",
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
            sequencing_source="public",
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

    def test_build_context_repairs_zero_hic_count_from_portal_and_reports_pairs(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB76517",
                    "run_accession": "ERR13301066",
                    "sample_accession": "SAMEA14449644",
                    "fastq_bytes": 0,
                    "submitted_bytes": 316_171_686_708,
                    "read_count": 0,
                    "instrument_model": "Illumina NovaSeq 6000",
                    "base_count": 0,
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "Hi-C",
                    "library_layout": "PAIRED",
                    "library_name": "",
                    "library_construction_protocol": "Hi-C - Arima v2",
                    "metadata_source": "ncbi_runinfo",
                    "read_count_basis": "spots",
                }
            ]
        )
        portal_runs = [
            _PortalObject(
                "45569_1#1",
                {
                    "tolqc_reporting_category": "hic",
                    "tolqc_reads": 6_676_902_688,
                    "tolqc_bases": 1_008_212_305_888,
                    "tolqc_read_length_mean": 151.0,
                    "tolqc_lims_qc": "pass",
                    "tolqc_manual_qc": "pass",
                    "mlwh_pipeline_id_lims": "Hi-C - Arima v2",
                    "mlwh_library_id": "DN952587P:E1",
                    "mlwh_biosample_accession": "SAMEA14449644",
                    "mlwh_biospecimen_accession": "SAMEA14449591",
                    "mlwh_irods_file": "45569_1#1.cram",
                    "mlwh_tag_index": 1,
                },
            ),
            _PortalObject(
                "m84093_231209_122002_s3#2016",
                {
                    "tolqc_reporting_category": "pacbio",
                    "tolqc_reads": 3_595_667,
                    "tolqc_bases": 51_394_669_472,
                    "mlwh_biosample_accession": "SAMEA10369855",
                    "mlwh_biospecimen_accession": "SAMEA10369846",
                },
            ),
        ]
        portal_service = PortalSequencingService(datasource_factory=lambda: _PortalDatasource(portal_runs))
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            portal_service=portal_service,
            biosample_tolid_getter=lambda biosamples: {
                "SAMEA14449644": "lsIriFoet1",
                "SAMEA14449591": "daPseLute1",
                "SAMEA10369855": "daArtMari1",
                "SAMEA10369846": "daArtMari1",
            },
            sequencing_source="public-with-portal",
            illumina_count_unit="read_pairs",
        )

        summary = service.build_context(["PRJEB76517"], "lsIriFoet1")
        context = summary.to_context_dict()

        self.assertEqual(context["hic_reads_millions"], "3\u202f338.45")
        self.assertEqual(context["hic_bases_gb"], "1\u202f008.21")
        self.assertEqual(context["hic_read_count_unit"], "read pairs")
        self.assertEqual(context["hic_read_count_source"], "portal_tolqc")
        self.assertEqual(context["sequencing_portal_matched_runs"], "45569_1#1")
        self.assertEqual(context["sequencing_portal_excluded_runs"], "m84093_231209_122002_s3#2016")
        self.assertIn("SAMEA10369855", context["sequencing_portal_warnings"])
        self.assertIn("SAMEA14449591", context["sequencing_portal_warnings"])
        hic_run = context["seq_data"]["Hi-C"][0]
        self.assertEqual(hic_run["portal_run_id"], "45569_1#1")
        self.assertEqual(hic_run["portal_reads"], "6676902688")
        self.assertEqual(hic_run["mlwh_library_id"], "DN952587P:E1")

    def test_ena_paired_illumina_read_counts_are_normalised_to_pairs(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_RNA",
                    "sample_accession": "SAMEA_RNA",
                    "fastq_bytes": 0,
                    "submitted_bytes": 0,
                    "read_count": 80,
                    "instrument_model": "Illumina NovaSeq X",
                    "base_count": 12_000,
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "RNA-Seq",
                    "library_layout": "PAIRED",
                    "library_name": "",
                    "library_construction_protocol": "RNA PolyA",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                }
            ]
        )
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            biosample_tolid_getter=lambda biosamples: {"SAMEA_RNA": "ixFooBar1"},
            sequencing_source="public",
            illumina_count_unit="read_pairs",
        )

        summary = service.build_context(["PRJEB1"], "ixFooBar1")

        self.assertEqual(summary.totals.rna_total_reads, "40.00")
        self.assertEqual(summary.totals.extras["rna_read_count_unit"], "read pairs")

    def test_build_context_exposes_multiplexing_from_public_aliases(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB104567",
                    "run_accession": "ERR15996643",
                    "run_alias": "SC_PacBio_RUN_m84047_250808_174518_s3:s1:tbc2020",
                    "experiment_alias": "SC_PacBio_EXP_m84047_250808_174518_s3:s1:tbc2020",
                    "sample_accession": "SAMEA118260618",
                    "fastq_bytes": "17131398556",
                    "submitted_bytes": "26424128708;16",
                    "read_count": "7241360",
                    "instrument_model": "Revio",
                    "base_count": "56049164578",
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_layout": "SINGLE",
                    "library_name": "PSYCHE15752215",
                    "library_construction_protocol": "PacBio - HiFi",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
                {
                    "study_accession": "PRJEB104567",
                    "run_accession": "ERR15985865",
                    "run_alias": "SC_RUN_51012_6#2",
                    "experiment_alias": "SC_EXP_51012_6#2",
                    "sample_accession": "SAMEA118260617",
                    "fastq_bytes": "20483007733;20331726580",
                    "submitted_bytes": "27093394437",
                    "read_count": "612698734",
                    "instrument_model": "Illumina NovaSeq X",
                    "base_count": "92517508834",
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "Hi-C",
                    "library_layout": "PAIRED",
                    "library_name": "",
                    "library_construction_protocol": "Hi-C - Arima v2",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
                {
                    "study_accession": "PRJEB104567",
                    "run_accession": "ERR16910178",
                    "run_alias": "SC_RUN_51987_7#77",
                    "experiment_alias": "SC_EXP_51987_7#77",
                    "sample_accession": "SAMEA118260619",
                    "fastq_bytes": "2973829163;3006588253",
                    "submitted_bytes": "3946408065",
                    "read_count": "98872246",
                    "instrument_model": "Illumina NovaSeq X",
                    "base_count": "14929709146",
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "RNA-Seq",
                    "library_layout": "PAIRED",
                    "library_name": "",
                    "library_construction_protocol": "RNA PolyA",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
            ]
        )
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            biosample_tolid_getter=lambda biosamples: {
                "SAMEA118260618": "ilBupPini2",
                "SAMEA118260617": "ilBupPini2",
                "SAMEA118260619": "ilBupPini2",
            },
            sequencing_source="public",
            illumina_count_unit="read_pairs",
        )

        summary = service.build_context(["PRJEB104567"], "ilBupPini2")
        context = summary.to_context_dict()

        self.assertTrue(context["sequencing_multiplexing_detected"])
        self.assertEqual(context["pacbio_multiplex_identifiers"], "tbc2020")
        self.assertEqual(context["hic_multiplex_identifiers"], "2")
        self.assertEqual(context["rna_multiplex_identifiers"], "77")
        self.assertEqual(context["pacbio_sequencing_runs"], "m84047_250808_174518_s3")
        self.assertEqual(context["hic_sequencing_runs"], "51012_6")
        self.assertIn("PacBio HiFi ERR15996643: barcode tbc2020", context["sequencing_multiplexing_summary"])
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_multiplex_label"], "barcode tbc2020")
        self.assertEqual(context["seq_data"]["Hi-C"][0]["multiplex_identifier"], "2")
        self.assertEqual(context["seq_data"]["Hi-C"][0]["fastq_bytes"], "38.01")


if __name__ == "__main__":
    unittest.main()
