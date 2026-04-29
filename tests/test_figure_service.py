from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data_note.models import FigureAsset, FigureBundle
from data_note.profiles import PsycheProfile
from data_note.services.figure_service import FigureService


class FigureServiceTests(unittest.TestCase):
    def test_collect_returns_typed_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            def make_triple(stem: str) -> tuple[Path, Path, Path]:
                png = tmp_path / f"{stem}.png"
                tif = tmp_path / f"{stem}.tif"
                gif = tmp_path / f"{stem}.gif"
                png.write_text("png")
                tif.write_text("tif")
                gif.write_text("gif")
                return png, tif, gif

            service = FigureService(
                gscope_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(output_stem or "Fig_2_Gscope"),
                pretext_labeler=lambda tolid, context, output_dir, output_stem=None: make_triple(output_stem or "Fig_3_Pretext"),
                merian_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(output_stem or "Fig_3_Merian"),
                merqury_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(output_stem or "Fig_4_Merqury"),
                btk_image_processor=lambda accession, output_dir, output_names=None: [
                    make_triple((output_names or {}).get("snail", "Fig_5_Snail.png").removesuffix(".png")),
                    make_triple((output_names or {}).get("blob", "Fig_6_Blob.png").removesuffix(".png")),
                ],
            )

            bundle = service.collect(
                PsycheProfile(),
                "ixExample1",
                tmpdir,
                {"prim_accession": "GCA_1.1"},
            )

            self.assertIsInstance(bundle, FigureBundle)
            merian = bundle.get("Fig_4_Merian")
            self.assertIsInstance(merian, FigureAsset)
            assert merian is not None
            self.assertEqual(merian.kind, "merian")
            self.assertEqual(merian.gif_path.name, "Fig_4_Merian.gif")
            self.assertEqual(
                bundle.to_context_dict()["Fig_5_Merqury"],
                "![Merqury spectra](./Fig_5_Merqury.gif)",
            )

    def test_collect_includes_merqury_for_single_assembly_haploid_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            calls = {"merqury": 0}

            def make_triple(stem: str) -> tuple[Path, Path, Path]:
                png = tmp_path / f"{stem}.png"
                tif = tmp_path / f"{stem}.tif"
                gif = tmp_path / f"{stem}.gif"
                png.write_text("png")
                tif.write_text("tif")
                gif.write_text("gif")
                return png, tif, gif

            def merqury_copier(tolid, output_dir, output_stem=None):
                calls["merqury"] += 1
                return make_triple(output_stem or "Fig_4_Merqury")

            service = FigureService(
                gscope_image_copier=lambda tolid, output_dir, output_stem=None: None,
                pretext_labeler=lambda tolid, context, output_dir, output_stem=None: None,
                merian_image_copier=lambda tolid, output_dir, output_stem=None: None,
                merqury_image_copier=merqury_copier,
                btk_image_processor=lambda accession, output_dir, output_names=None: [],
            )

            bundle = service.collect(
                PsycheProfile(),
                "csSphCont2",
                tmpdir,
                {
                    "assemblies_type": "prim_alt",
                    "is_haploid": True,
                    "has_alternate_assembly": False,
                    "prim_accession": "GCA_963920785.2",
                },
            )

            self.assertEqual(calls["merqury"], 1)
            self.assertIn("Fig_5_Merqury", bundle.to_context_dict())


if __name__ == "__main__":
    unittest.main()
