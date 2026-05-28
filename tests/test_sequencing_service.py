from __future__ import annotations

import unittest
import warnings

import pandas as pd

from data_note.models import (
    AssemblyRecord,
    AssemblySelection,
    RunGroup,
    RunRecord,
    SequencingSummary,
    SequencingTotals,
    TechnologyRecord,
)
from data_note.services.sequencing_fetch_service import SequencingFetchResult, SequencingFetchService
from data_note.services.sequencing_portal_service import PortalSequencingService
from data_note.services.sequencing_service import SequencingService


class StubSequencingFetchService(SequencingFetchService):
    def __init__(self, dataframe: pd.DataFrame, assembly_run_accessions: set[str] | None = None) -> None:
        super().__init__(session_get=lambda *args, **kwargs: None)
        self._dataframe = dataframe
        self._assembly_run_accessions = assembly_run_accessions or set()

    def fetch_for_bioprojects_with_sources(self, bioprojects: list[str]) -> SequencingFetchResult:
        return SequencingFetchResult(dataframe=self._dataframe, source_accessions=bioprojects)

    def fetch_assembly_run_accessions(self, assembly_accessions: list[str]) -> set[str]:
        return self._assembly_run_accessions


class _PortalObject:
    def __init__(
        self,
        identifier: str,
        attributes: dict | None = None,
        *,
        to_one_relationships: dict | None = None,
        to_many_relationships: dict | None = None,
    ) -> None:
        self.id = identifier
        self.attributes = attributes or {}
        self.to_one_relationships = to_one_relationships or {}
        self.to_many_relationships = to_many_relationships or {}


class _PortalDatasource:
    def __init__(
        self,
        runs: list[_PortalObject] | None = None,
        *,
        runs_by_tolid: dict[str, list[_PortalObject]] | None = None,
        objects_by_type: dict[str, dict[str, _PortalObject]] | None = None,
    ) -> None:
        self.runs = runs or []
        self.runs_by_tolid = runs_by_tolid or {}
        self.objects_by_type = objects_by_type or {}

    def get_by_id(self, object_type: str, identifiers: list[str]):
        if object_type != "tolid":
            objects = self.objects_by_type.get(object_type, {})
            return [objects.get(identifier, _PortalObject(identifier)) for identifier in identifiers]
        return [_PortalObject(identifiers[0])]

    def get_to_many_relations(self, object_object, relation: str):
        return self.runs_by_tolid.get(object_object.id, self.runs)


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

    def test_build_context_filters_assembly_reads_to_selected_assembly_run_accessions(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_KEEP",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "REVIO",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_KEEP",
                    "library_construction_protocol": "PROTO_KEEP",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_DROP",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "REVIO",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_DROP",
                    "library_construction_protocol": "PROTO_DROP",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_RNA",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "NovaSeq",
                    "base_count": 2000,
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "RNA-Seq",
                    "library_layout": "PAIRED",
                    "library_name": "",
                    "library_construction_protocol": "RNA PolyA",
                },
            ]
        )
        assembly_selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(
                accession="GCA_1.1",
                assembly_name="ixFooBar1.1",
                role="primary",
            ),
        )
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df, {"ERR_KEEP"}),
            biosample_tolid_getter=lambda biosamples: {"SAMEA1": "ixFooBar1"},
            sequencing_source="public",
        )

        summary = service.build_context(["PRJEB1"], "ixFooBar1", assembly_selection=assembly_selection)
        context = summary.to_context_dict()

        self.assertEqual(
            [run.read_accession for run in summary.run_group("PacBio").runs],
            ["ERR_KEEP"],
        )
        self.assertEqual(
            [run.read_accession for run in summary.run_group("RNA").runs],
            ["ERR_RNA"],
        )
        self.assertEqual(summary.pacbio_library_name(), "LIB_KEEP")
        self.assertTrue(context["sequencing_assembly_run_accession_filter"])
        self.assertEqual(context["sequencing_assembly_run_accessions"], "ERR_KEEP")
        self.assertEqual(context["sequencing_assembly_excluded_runs"], "ERR_DROP")

    def test_build_context_drops_public_row_when_portal_marks_run_as_wrong_tolid(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_GOOD",
                    "sample_accession": "SAMEA_TARGET",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "Revio",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_GOOD",
                    "library_construction_protocol": "PacBio - HiFi",
                    "submitted_ftp": "ftp://example/m84001_240101_120000_s1.hifi_reads.bc2001.bam",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_BAD",
                    "sample_accession": "SAMEA_TARGET",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1000,
                    "instrument_model": "Sequel IIe",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_BAD",
                    "library_construction_protocol": "PacBio - HiFi",
                    "submitted_ftp": "ftp://example/m64016e_230423_044942.ccs.bc2038--bc2038.bam",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
            ]
        )
        portal_runs = [
            _PortalObject(
                "m84001_240101_120000_s1#2001",
                {
                    "tolqc_reporting_category": "pacbio",
                    "tolqc_reads": 1000,
                    "tolqc_bases": 2000,
                    "mlwh_biosample_accession": "SAMEA_TARGET",
                    "mlwh_irods_file": "m84001_240101_120000_s1.hifi_reads.bc2001.bam",
                    "mlwh_library_id": "LIB_GOOD",
                    "mlwh_pac_bio_library_tube_name": "LIB_GOOD",
                    "mlwh_run_id": "m84001_240101_120000_s1",
                },
            ),
            _PortalObject(
                "m64016e_230423_044942#2038",
                {
                    "tolqc_reporting_category": "pacbio",
                    "tolqc_reads": 1000,
                    "tolqc_bases": 2000,
                    "mlwh_biosample_accession": "SAMEA_OTHER",
                    "mlwh_biospecimen_accession": "SAMEA_OTHER_SPECIMEN",
                    "mlwh_library_id": "LIB_BAD",
                    "mlwh_pac_bio_library_tube_name": "LIB_BAD",
                    "mlwh_run_id": "m64016e_230423_044942",
                    "mlwh_tag1_id": "bc2038",
                },
            ),
        ]
        portal_service = PortalSequencingService(datasource_factory=lambda: _PortalDatasource(portal_runs))
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            portal_service=portal_service,
            biosample_tolid_getter=lambda biosamples: {
                "SAMEA_TARGET": "ixFooBar1",
                "SAMEA_OTHER": "ixOtherBar1",
                "SAMEA_OTHER_SPECIMEN": "ixOtherBar1",
            },
            sequencing_source="public-with-portal",
        )

        summary = service.build_context(["PRJEB1"], "ixFooBar1")
        context = summary.to_context_dict()

        self.assertEqual(context["pacbio_run_accessions"], "ERR_GOOD")
        self.assertEqual(context["sequencing_portal_excluded_runs"], "m64016e_230423_044942#2038")
        self.assertEqual(context["sequencing_portal_dropped_public_runs"], "ERR_BAD")
        self.assertEqual(summary.pacbio_library_name(), "LIB_GOOD")
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_library_name"], "LIB_GOOD")

    def test_build_context_excludes_failed_qc_runs_before_methods_and_totals(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_PASS",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 2_000,
                    "instrument_model": "Revio",
                    "base_count": 4_000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_PASS",
                    "library_construction_protocol": "PacBio - HiFi (ULI)",
                    "submitted_ftp": "ftp://example/m84098_240821_121240_s4.hifi_reads.bc2039.bam",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_FAIL",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 100,
                    "submitted_bytes": 100,
                    "read_count": 1_000,
                    "instrument_model": "Sequel IIe",
                    "base_count": 2_000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB_FAIL",
                    "library_construction_protocol": "PacBio - HiFi",
                    "submitted_ftp": "ftp://example/m64097e_221010_045249.ccs.bc1008.bam",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
            ]
        )
        portal_runs = [
            _PortalObject(
                "m84098_240821_121240_s4#2039",
                {
                    "tolqc_reporting_category": "pacbio",
                    "tolqc_reads": 2_000,
                    "tolqc_bases": 4_000,
                    "tolqc_manual_qc": "pass",
                    "mlwh_lims_qc": "pass",
                    "mlwh_biosample_accession": "SAMEA1",
                    "mlwh_irods_file": "m84098_240821_121240_s4.hifi_reads.bc2039.bam",
                    "mlwh_library_id": "LIB_PASS",
                    "mlwh_pac_bio_library_tube_name": "LIB_PASS",
                    "mlwh_run_id": "m84098_240821_121240_s4",
                    "mlwh_tag1_id": "bc2039",
                },
            ),
            _PortalObject(
                "m64097e_221010_045249#1008",
                {
                    "tolqc_reporting_category": "pacbio",
                    "tolqc_reads": 1_000,
                    "tolqc_bases": 2_000,
                    "mlwh_lims_qc": "fail",
                    "mlwh_qc_seq_state": "Failed",
                    "mlwh_biosample_accession": "SAMEA1",
                    "mlwh_irods_file": "m64097e_221010_045249.ccs.bc1008.bam",
                    "mlwh_library_id": "LIB_FAIL",
                    "mlwh_pac_bio_library_tube_name": "LIB_FAIL",
                    "mlwh_run_id": "m64097e_221010_045249",
                    "mlwh_tag1_id": "bc1008",
                },
            ),
        ]
        portal_service = PortalSequencingService(datasource_factory=lambda: _PortalDatasource(portal_runs))
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            portal_service=portal_service,
            biosample_tolid_getter=lambda biosamples: {"SAMEA1": "idTetArro1"},
            sequencing_source="public-with-portal",
        )

        summary = service.build_context(["PRJEB1"], "idTetArro1")
        context = summary.to_context_dict()

        self.assertEqual(context["pacbio_run_accessions"], "ERR_PASS")
        self.assertEqual(context["pacbio_protocols"], ["PacBio - HiFi (ULI)"])
        self.assertEqual(context["pacbio_reads_millions"], "0.00")
        self.assertEqual(context["pacbio_total_reads"], "2\u202f000.00")
        self.assertEqual(context["sequencing_qc_excluded_runs"], "ERR_FAIL")
        self.assertEqual(
            context["sequencing_qc_excluded_portal_runs"],
            "m64097e_221010_045249#1008",
        )
        self.assertEqual(summary.pacbio_library_name(), "LIB_PASS")
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_library_name"], "LIB_PASS")
        self.assertEqual(
            [run["read_accession"] for run in context["seq_data"]["PacBio"]],
            ["ERR_PASS"],
        )
        self.assertEqual(context["pacbio_multiplexing"], "barcode bc2039")
        self.assertNotIn("LIB_FAIL", str(context["technology_data"]["pacbio"]))

    def test_build_context_enriches_rna_from_related_sample_tolid_portal_run(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_DNA",
                    "sample_accession": "SAMEA_DNA",
                    "fastq_bytes": 0,
                    "submitted_bytes": 0,
                    "read_count": 1000,
                    "instrument_model": "Revio",
                    "base_count": 2000,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_layout": "SINGLE",
                    "library_name": "LIB_DNA",
                    "library_construction_protocol": "PacBio - HiFi",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR_RNA",
                    "sample_accession": "SAMEA_RNA",
                    "fastq_bytes": 0,
                    "submitted_bytes": 0,
                    "read_count": 55_356_992,
                    "instrument_model": "Illumina NovaSeq 6000",
                    "base_count": 8_358_905_792,
                    "instrument_platform": "ILLUMINA",
                    "library_strategy": "RNA-Seq",
                    "library_layout": "PAIRED",
                    "library_name": "",
                    "library_construction_protocol": "RNA PolyA",
                    "run_alias": "SC_RUN_48017_1#78",
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                },
            ]
        )
        rna_run = _PortalObject(
            "48017_1#78",
            {
                "tolqc_reporting_category": "rnaseq",
                "tolqc_reads": 55_356_992,
                "tolqc_bases": 8_358_905_792,
                "mlwh_biosample_accession": "SAMEA_RNA",
                "mlwh_biospecimen_accession": "SAMEA_SPECIMEN",
                "mlwh_irods_file": "48017_1#78.cram",
                "mlwh_library_id": "SQPP-7472-W:F10",
                "mlwh_pipeline_id_lims": "RNA PolyA",
                "mlwh_run_id": "48017_1",
                "mlwh_tag_index": "78",
            },
            to_one_relationships={
                "benchling_sample": _PortalObject("63763"),
                "benchling_extraction": _PortalObject("bfi_Z8oUWKtu"),
                "mlwh_sequencing_request": _PortalObject("DTOLRNA13949196"),
            },
        )
        portal_service = PortalSequencingService(
            datasource_factory=lambda: _PortalDatasource(
                runs_by_tolid={"idTetArro1": [], "idTetArro2": [rna_run]},
                objects_by_type={
                    "sample": {
                        "63763": _PortalObject(
                            "63763",
                            {
                                "benchling_organism_part": "HEAD, THORAX",
                                "benchling_size_of_tissue_in_tube": "M",
                                "benchling_tissue_fluidx_id": "FD33650455",
                            },
                        )
                    },
                    "sequencing_request": {
                        "DTOLRNA13949196": _PortalObject(
                            "DTOLRNA13949196",
                            to_one_relationships={
                                "benchling_tissue_prep": _PortalObject("bfi_YDfmy058"),
                                "benchling_extraction": _PortalObject("bfi_Z8oUWKtu"),
                            },
                        )
                    },
                    "tissue_prep": {
                        "bfi_YDfmy058": _PortalObject(
                            "bfi_YDfmy058",
                            {
                                "benchling_tissue_prep_name": "TissuePrep_idTetArro2_15015",
                                "benchling_sampleprep_date": "2023-08-08",
                                "benchling_tissue_prep_type": "Whole Dry Frozen Tissue",
                                "benchling_tissue_prep_fluidx_id": "FS71949939",
                                "benchling_weight_mg": 0.0,
                                "benchling_sciops_protocol_required": "Metazoa",
                            },
                        )
                    },
                    "extraction": {
                        "bfi_Z8oUWKtu": _PortalObject(
                            "bfi_Z8oUWKtu",
                            {
                                "benchling_extraction_name": "RNAExt_idTetArro2_1730",
                                "benchling_extraction_type": "rna",
                                "benchling_completion_date": "2023-08-11",
                                "benchling_volume_ul": 45.0,
                                "benchling_rna_yield": 1503.0,
                                "benchling_rna_qc_passfail": "Yes",
                            },
                        )
                    },
                },
            )
        )
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            portal_service=portal_service,
            biosample_tolid_getter=lambda biosamples: {
                "SAMEA_DNA": "idTetArro1",
                "SAMEA_RNA": "idTetArro2",
                "SAMEA_SPECIMEN": "idTetArro2",
            },
            sequencing_source="public-with-portal",
            illumina_count_unit="read_pairs",
        )

        summary = service.build_context(["PRJEB1"], "idTetArro1")
        context = summary.to_context_dict()

        self.assertEqual(context["rna_run_accessions"], "ERR_RNA")
        self.assertEqual(context["rna_reads_millions"], "27.68")
        self.assertEqual(context["sequencing_portal_matched_runs"], "48017_1#78")
        self.assertEqual(context["rna_mlwh_library_id"], "SQPP-7472-W:F10")
        self.assertEqual(context["rna_portal_sample_uid"], "63763")
        self.assertEqual(context["rna_portal_sample_organism_part"], "HEAD, THORAX")
        self.assertEqual(context["rna_portal_tissue_prep_uid"], "bfi_YDfmy058")
        self.assertEqual(context["rna_portal_tissue_prep_name"], "TissuePrep_idTetArro2_15015")
        self.assertEqual(context["rna_portal_tissue_prep_type"], "Whole Dry Frozen Tissue")
        self.assertEqual(context["rna_portal_tissue_prep_sciops_protocol_required"], "Metazoa")
        self.assertEqual(context["rna_portal_extraction_uid"], "bfi_Z8oUWKtu")
        self.assertEqual(context["rna_portal_extraction_name"], "RNAExt_idTetArro2_1730")
        self.assertEqual(context["rna_portal_extraction_volume_ul"], "45")
        self.assertEqual(context["rna_portal_rna_yield"], "1503")
        self.assertEqual(context["rna_portal_rna_qc_passfail"], "Yes")

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

    def test_build_context_exposes_pacbio_plex_count_from_portal(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB104567",
                    "run_accession": "ERR15996643",
                    "sample_accession": "SAMEA118260618",
                    "fastq_bytes": 0,
                    "submitted_bytes": 26_424_128_708,
                    "read_count": 7_241_360,
                    "instrument_model": "Revio",
                    "base_count": 56_049_164_578,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_layout": "SINGLE",
                    "library_name": "PSYCHE15752215",
                    "library_construction_protocol": "PacBio - HiFi",
                    "submitted_ftp": (
                        "ftp.sra.ebi.ac.uk/vol1/run/ERR159/ERR15996643/"
                        "m84047_250808_174518_s3.hifi_reads.bc2020.bam"
                    ),
                    "metadata_source": "ena",
                    "read_count_basis": "reads",
                }
            ]
        )
        portal_runs = [
            _PortalObject(
                "m84047_250808_174518_s3#2020",
                {
                    "tolqc_reporting_category": "pacbio",
                    "tolqc_reads": 7_241_360,
                    "tolqc_bases": 56_049_164_578,
                    "mlwh_biosample_accession": "SAMEA118260618",
                    "mlwh_irods_file": "m84047_250808_174518_s3.hifi_reads.bc2020.bam",
                    "mlwh_run_id": "m84047_250808_174518_s3",
                    "mlwh_tag1_id": "bc2020",
                    "mlwh_plex_count": 2,
                },
            ),
        ]
        portal_service = PortalSequencingService(datasource_factory=lambda: _PortalDatasource(portal_runs))
        service = SequencingService(
            fetch_service=StubSequencingFetchService(runinfo_df),
            portal_service=portal_service,
            biosample_tolid_getter=lambda biosamples: {"SAMEA118260618": "ilBupPini2"},
            sequencing_source="public-with-portal",
        )

        summary = service.build_context(["PRJEB104567"], "ilBupPini2")
        context = summary.to_context_dict()

        self.assertEqual(context["pacbio_plex_count"], "2")
        self.assertEqual(context["pacbio_plex_level"], "2-plex")
        self.assertEqual(context["pacbio_multiplex_identifiers"], "bc2020")
        self.assertEqual(context["technology_data"]["pacbio"]["pacbio_plex_level"], "2-plex")
        self.assertEqual(context["seq_data"]["PacBio"][0]["mlwh_plex_count"], "2")

    def test_portal_enrichment_allows_blank_mlwh_fields_in_numeric_source_columns(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR15996643",
                    "sample_accession": "SAMEA118260618",
                    "fastq_bytes": 0,
                    "submitted_bytes": 26_424_128_708,
                    "read_count": 7_241_360,
                    "instrument_model": "Revio",
                    "base_count": 56_049_164_578,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_layout": "SINGLE",
                    "library_name": "PSYCHE15752215",
                    "submitted_ftp": (
                        "ftp.sra.ebi.ac.uk/vol1/run/ERR159/ERR15996643/"
                        "m84047_250808_174518_s3.hifi_reads.bc2020.bam"
                    ),
                    "mlwh_tag_index": float("nan"),
                }
            ]
        )
        portal_rows = [
            {
                "portal_run_id": "m84047_250808_174518_s3#2020",
                "tolqc_reporting_category": "pacbio",
                "tolqc_reads": 7_241_360,
                "tolqc_bases": 56_049_164_578,
                "mlwh_biosample_accession": "SAMEA118260618",
                "mlwh_irods_file": "m84047_250808_174518_s3.hifi_reads.bc2020.bam",
                "mlwh_library_id": "PSYCHE15752215",
            }
        ]
        portal_service = PortalSequencingService()

        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            result = portal_service.enrich_dataframe(
                runinfo_df,
                tolid="ilBupPini2",
                portal_rows=portal_rows,
                biosample_tolid_map={"SAMEA118260618": "ilBupPini2"},
                mode="public-with-portal",
            )

        self.assertEqual(result.dataframe.loc[0, "mlwh_tag_index"], "")
        self.assertEqual(result.matched_run_ids, ["m84047_250808_174518_s3#2020"])

    def test_portal_enrichment_creates_missing_mlwh_text_columns_before_assignment(self) -> None:
        runinfo_df = pd.DataFrame(
            [
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR1",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 0,
                    "submitted_bytes": 0,
                    "read_count": 10,
                    "instrument_model": "Revio",
                    "base_count": 100,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB1",
                    "submitted_ftp": "m84047_250808_174518_s3.hifi_reads.bc2020.bam",
                },
                {
                    "study_accession": "PRJEB1",
                    "run_accession": "ERR2",
                    "sample_accession": "SAMEA1",
                    "fastq_bytes": 0,
                    "submitted_bytes": 0,
                    "read_count": 20,
                    "instrument_model": "Revio",
                    "base_count": 200,
                    "instrument_platform": "PACBIO_SMRT",
                    "library_strategy": "WGS",
                    "library_name": "LIB1",
                    "submitted_ftp": "m84047_250808_174518_s3.hifi_reads.bc2021.bam",
                },
            ]
        )
        portal_rows = [
            {
                "portal_run_id": "m84047_250808_174518_s3#2020",
                "tolqc_reporting_category": "pacbio",
                "tolqc_reads": 10,
                "tolqc_bases": 100,
                "mlwh_biosample_accession": "SAMEA1",
                "mlwh_irods_file": "m84047_250808_174518_s3.hifi_reads.bc2020.bam",
                "mlwh_library_id": "LIB1",
                "mlwh_tag_index": 2020,
            },
            {
                "portal_run_id": "m84047_250808_174518_s3#2021",
                "tolqc_reporting_category": "pacbio",
                "tolqc_reads": 20,
                "tolqc_bases": 200,
                "mlwh_biosample_accession": "SAMEA1",
                "mlwh_irods_file": "m84047_250808_174518_s3.hifi_reads.bc2021.bam",
                "mlwh_library_id": "LIB1",
            },
        ]
        portal_service = PortalSequencingService()

        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            result = portal_service.enrich_dataframe(
                runinfo_df,
                tolid="ilBupPini2",
                portal_rows=portal_rows,
                biosample_tolid_map={"SAMEA1": "ilBupPini2"},
                mode="public-with-portal",
            )

        self.assertEqual(result.dataframe["mlwh_tag_index"].dtype, "object")
        self.assertEqual(result.dataframe.loc[0, "mlwh_tag_index"], 2020)
        self.assertEqual(result.dataframe.loc[1, "mlwh_tag_index"], "")

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
