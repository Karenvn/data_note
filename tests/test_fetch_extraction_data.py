from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from data_note.fetch_extraction_data import (
    _extract_extraction_attrs,
    _resolve_lr_sample_prep_tsv,
    fallback_fetch_from_lr_sample_prep,
    fetch_barcoding_info,
    get_sequencing_and_extraction_metadata,
)


class ExtractionDataFallbackTests(unittest.TestCase):
    def test_get_metadata_maps_sequencing_request_wet_lab_fields(self) -> None:
        seq_request = SimpleNamespace(
            id="DTOL1",
            attributes={
                "benchling_completion_date": "2026-01-05",
                "benchling_sequencing_platform": "pacbio",
                "benchling_submission_sample_id": "SUB1",
                "benchling_submission_sample_name": "SubSam_example",
                "benchling_spri_type": "Apex",
                "benchling_bead_type": "Ampure PB",
                "benchling_post_spri_concentration_ngul": 33.0,
                "benchling_nanodrop_concentration_ngul": 28.9,
                "benchling_nanodrop_260280": 2.34,
                "benchling_nanodrop_260230": 1.82,
                "benchling_sheared_femto_fragment_size_bp": 17797.0,
            },
            to_one_relationships={},
        )

        with patch("data_note.fetch_extraction_data._portal_datasource", return_value=object()), patch(
            "data_note.fetch_extraction_data._get_extraction_by_uid",
            return_value=None,
        ), patch(
            "data_note.fetch_extraction_data._get_sequencing_request",
            return_value=seq_request,
        ), patch(
            "data_note.fetch_extraction_data._get_extraction_from_sequencing_request",
            return_value=None,
        ), patch(
            "data_note.fetch_extraction_data._get_extraction_by_tolid",
            return_value=None,
        ):
            seq_attrs, extraction_attrs = get_sequencing_and_extraction_metadata("DTOL1")

        self.assertEqual(extraction_attrs, {})
        self.assertEqual(seq_attrs["spri_type"], "Apex")
        self.assertEqual(seq_attrs["bead_type"], "Ampure PB")
        self.assertEqual(seq_attrs["qubit_ngul"], 33.0)
        self.assertEqual(seq_attrs["nanodrop_concentration_ngul"], 28.9)
        self.assertEqual(seq_attrs["ratio_260_280"], 2.34)
        self.assertEqual(seq_attrs["ratio_260_230"], 1.82)
        self.assertEqual(seq_attrs["fragment_size_kb"], "17.8")

    def test_extract_extraction_attrs_prefers_direct_tissue_prep_weight_for_dna(self) -> None:
        extraction = SimpleNamespace(
            id="bfi_ext",
            attributes={},
            to_one_relationships={
                "benchling_tissue_prep": SimpleNamespace(
                    id="bfi_tp",
                    attributes={"benchling_weight_mg": 0.0},
                )
            },
        )
        direct_tissue_prep = SimpleNamespace(
            id="bfi_tp",
            attributes={
                "benchling_weight_mg": 0.0,
                "benchling_weight_of_prep_for_dna": 51.0,
                "benchling_disruption_method": "Powermash",
            },
        )

        class DummyFilter:
            def __init__(self) -> None:
                self.and_ = None

        class FakeDataSource:
            def get_list(self, object_name, object_filters=None):
                self.object_name = object_name
                self.object_filters = object_filters
                return [direct_tissue_prep]

        ds = FakeDataSource()
        with patch("data_note.fetch_extraction_data.DataSourceFilter", DummyFilter):
            result = _extract_extraction_attrs(extraction, ds=ds)

        self.assertEqual(ds.object_name, "tissue_prep")
        self.assertEqual(
            ds.object_filters.and_,
            {"uid": {"eq": {"value": "bfi_tp", "negate": False}}},
        )
        self.assertEqual(result["tissue_weight_mg"], 51.0)
        self.assertEqual(result["tissue_weight_mg_source"], "benchling_weight_of_prep_for_dna")
        self.assertEqual(result["disruption_method"], "Powermash")

    def test_extract_extraction_attrs_keeps_container_qc_separate_from_final_dna_yield(self) -> None:
        extraction = SimpleNamespace(
            id="bfi_ext",
            attributes={},
            to_one_relationships={},
            to_many_relationships={
                "benchling_extraction_containers": [
                    SimpleNamespace(
                        id="con_other",
                        attributes={
                            "benchling_yield_ng": 100.0,
                            "benchling_volume_ul": 5.0,
                        },
                    ),
                    SimpleNamespace(
                        id="con_selected",
                        attributes={
                            "benchling_yield_ng": 3690.0,
                            "benchling_volume_ul": 20.0,
                            "benchling_qubit_concentration_ngul": 41.0,
                            "benchling_nanodrop_concentration_ngul": 90.2,
                            "benchling_dna_260_280_ratio": 1.86,
                            "benchling_dna_260_230_ratio": 1.76,
                        },
                    ),
                ]
            },
        )

        result = _extract_extraction_attrs(extraction, extraction_container_id="con_selected")

        self.assertEqual(result["extraction_container_uid"], "con_selected")
        self.assertEqual(result["extraction_container_yield_ng"], "3\u202f690.00")
        self.assertEqual(result["extraction_container_volume_ul"], 20.0)
        self.assertEqual(result["extraction_container_qubit_ngul"], 41.0)
        self.assertEqual(result["extraction_container_nanodrop_concentration_ngul"], 90.2)
        self.assertEqual(result["extraction_container_ratio_260_280"], 1.86)
        self.assertEqual(result["extraction_container_ratio_260_230"], 1.76)
        self.assertEqual(result["dna_yield_ng"], "")
        self.assertIsNone(result["volume_ul"])

    def test_get_metadata_uses_sequencing_request_extraction_container_identity(self) -> None:
        seq_request = SimpleNamespace(
            id="DTOL1",
            attributes={
                "uid": "DTOL1",
                "benchling_post_spri_concentration_ngul": 26.6,
            },
            to_one_relationships={
                "benchling_extraction_container": SimpleNamespace(
                    id="con_selected",
                    attributes={"benchling_volume_ul": 99.0},
                )
            },
        )
        extraction = SimpleNamespace(
            id="bfi_ext",
            attributes={},
            to_one_relationships={},
            to_many_relationships={
                "benchling_extraction_containers": [
                    SimpleNamespace(id="con_other", attributes={"benchling_yield_ng": 100.0}),
                    SimpleNamespace(
                        id="con_selected",
                        attributes={
                            "benchling_yield_ng": 3690.0,
                            "benchling_volume_ul": 20.0,
                        },
                    ),
                ]
            },
        )

        with patch("data_note.fetch_extraction_data._portal_datasource", return_value=object()), patch(
            "data_note.fetch_extraction_data._get_extraction_by_uid",
            return_value=None,
        ), patch(
            "data_note.fetch_extraction_data._get_sequencing_request",
            return_value=seq_request,
        ), patch(
            "data_note.fetch_extraction_data._get_extraction_from_sequencing_request",
            return_value=extraction,
        ), patch(
            "data_note.fetch_extraction_data._get_extraction_by_tolid",
            return_value=None,
        ):
            seq_attrs, extraction_attrs = get_sequencing_and_extraction_metadata("DTOL1")

        self.assertEqual(seq_attrs["sanger_sample_id"], "DTOL1")
        self.assertEqual(seq_attrs["qubit_ngul"], 26.6)
        self.assertEqual(extraction_attrs["extraction_container_uid"], "con_selected")
        self.assertEqual(extraction_attrs["extraction_container_yield_ng"], "3\u202f690.00")
        self.assertEqual(extraction_attrs["extraction_container_volume_ul"], 20.0)

    def test_resolve_lr_sample_prep_tsv_prefers_gn_assets_default(self) -> None:
        with TemporaryDirectory() as tmpdir:
            assets_root = Path(tmpdir)
            tsv_path = assets_root / "LR_sample_prep.tsv"
            tsv_path.write_text("Sanger sample ID\tTissue Mass (mg)\nLIB1\t7.8\n")

            with patch.dict(
                os.environ,
                {
                    "DATA_NOTE_GN_ASSETS": str(assets_root),
                },
                clear=False,
            ):
                resolved = _resolve_lr_sample_prep_tsv()

        self.assertEqual(resolved, tsv_path)

    def test_resolve_lr_sample_prep_tsv_falls_back_to_legacy_template_when_configured_path_missing(self) -> None:
        with TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            legacy_dir = home / "genome_note_templates"
            legacy_dir.mkdir()
            legacy_tsv = legacy_dir / "LR_sample_prep.tsv"
            legacy_tsv.write_text("Sanger sample ID\tTissue Mass (mg)\nLIB1\t7.8\n")

            with patch("data_note.fetch_extraction_data.Path.home", return_value=home):
                with patch.dict(
                    os.environ,
                    {
                        "DATA_NOTE_LR_SAMPLE_PREP_TSV": str(home / "gn_assets" / "LR_sample_prep.tsv"),
                    },
                    clear=False,
                ):
                    resolved = _resolve_lr_sample_prep_tsv()

        self.assertEqual(resolved, legacy_tsv)

    def test_fallback_fetch_from_lr_sample_prep_extracts_tissue_mass_and_protocol_fields(self) -> None:
        tsv_content = (
            "Sanger sample ID\tExtraction Protocol/Kit version\tCrush Method\tTissue Mass (mg)\t"
            "Tissue Type\tLysis \tSPRI Type \tSHEAR Date started\tMR Machine ID\tMR speed\t"
            "Vol Input SPRI (uL)\tPost-Shear SPRI Volume\tQubit Quant (ng/ul) [ESP2]\t"
            "Final Elution Volume (ul)\tTotal DNA ng [ESP2]\tND 260/280 [ESP2]\t"
            "ND 260/230 [ESP2]\tND Quant (ng/uL) [ESP2]\tFemto Fragment Size [ESP2]\t"
            "GQN 10kb Threshold [ESP2]\tEXT Date Started\tDate Complete\n"
            "LIB1\tPlant MagAttract 48xrn v4\tCryoprep\t84\tPlant\t1h@55C\t1x ProNex (manual)\t"
            "17/05/2024\tBritney Shears\t31\t120\t40\t49.2\t47\t2312.4\t1.92\t1.82\t"
            "52.46\t10278\t4.8\t12/04/2024\t08/07/2024\n"
        )

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "LR_sample_prep.tsv"
            path.write_text(tsv_content)

            result = fallback_fetch_from_lr_sample_prep("LIB1", str(path))

        self.assertEqual(result["extraction_protocol"], "Plant MagAttract 48xrn v4")
        self.assertEqual(result["disruption_method"], "Cryoprep")
        self.assertEqual(result["tissue_weight_mg"], 84)
        self.assertEqual(result["tissue_type"], "Plant")
        self.assertEqual(result["lysis"], "1h@55C")
        self.assertEqual(result["spri_type"], "1x ProNex (manual)")
        self.assertEqual(result["shearing_date"], "17/05/2024")
        self.assertEqual(result["mr_machine_id"], "Britney Shears")
        self.assertEqual(result["mr_speed"], 31)
        self.assertEqual(result["spri_input_volume_ul"], 120)
        self.assertEqual(result["post_shear_spri_volume_ul"], 40)
        self.assertEqual(result["dna_yield_ng"], "2\u202f312.40")
        self.assertEqual(result["fragment_size_kb"], "10.3")
        self.assertEqual(result["gqn"], 4.8)
        self.assertEqual(result["date_complete"], "08/07/2024")

    def test_fallback_fetch_from_lr_sample_prep_can_match_by_tolid(self) -> None:
        tsv_content = (
            "Sanger sample ID\tToL ID \tExtraction Protocol/Kit version\tCrush Method\tTissue Mass (mg)\tSPRI Type \n"
            "DTOL13262041\tfCheLab1\tMagAttract Standard 48xrn\tPowermash\t23.4\t1x ProNex (manual)\n"
        )

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "LR_sample_prep.tsv"
            path.write_text(tsv_content)

            result = fallback_fetch_from_lr_sample_prep("fCheLab1", str(path))

        self.assertEqual(result["extraction_protocol"], "MagAttract Standard 48xrn")
        self.assertEqual(result["disruption_method"], "Powermash")
        self.assertEqual(result["sanger_sample_id"], "DTOL13262041")
        self.assertEqual(float(result["tissue_weight_mg"]), 23.4)
        self.assertEqual(result["spri_type"], "1x ProNex (manual)")


class BarcodingInfoTests(unittest.TestCase):
    def test_fetch_barcoding_info_prefers_latest_completed_sample_when_multiple_match_tolid(self) -> None:
        older_sample = SimpleNamespace(
            attributes={
                "benchling_completion_date": "2024-01-01",
                "sts_tremoved": "Y",
                "sts_barcode_hub": "NATURAL HISTORY MUSEUM",
                "sts_eln_id": "old-eln",
                "benchling_sample_set_id": "OLD_SET",
            }
        )
        newer_sample = SimpleNamespace(
            attributes={
                "benchling_completion_date": "2025-01-01",
                "sts_tremoved": "N",
                "sts_barcode_hub": "NOT_COLLECTED",
                "sts_eln_id": "new-eln",
                "benchling_sample_set_id": "NEW_SET",
            }
        )

        class DummyFilter:
            def __init__(self) -> None:
                self.and_ = None

        class FakeDataSource:
            def get_list(self, object_name, object_filters=None):
                self.object_name = object_name
                self.object_filters = object_filters
                return [older_sample, newer_sample]

        ds = FakeDataSource()
        with patch("data_note.fetch_extraction_data._portal_datasource", return_value=ds), patch(
            "data_note.fetch_extraction_data.DataSourceFilter",
            DummyFilter,
        ):
            result = fetch_barcoding_info("icExample1")

        self.assertEqual(ds.object_name, "sample")
        self.assertEqual(
            ds.object_filters.and_,
            {"benchling_tolid.id": {"eq": {"value": "icExample1", "negate": False}}},
        )
        self.assertEqual(result["sts_tremoved"], "N")
        self.assertEqual(result["barcode_hub"], "NOT_COLLECTED")
        self.assertEqual(result["eln_id"], "new-eln")
        self.assertEqual(result["sample_set_id"], "NEW_SET")


if __name__ == "__main__":
    unittest.main()
