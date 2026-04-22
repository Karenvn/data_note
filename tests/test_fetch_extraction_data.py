from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from data_note.fetch_extraction_data import _resolve_lr_sample_prep_tsv, fallback_fetch_from_lr_sample_prep


class ExtractionDataFallbackTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
