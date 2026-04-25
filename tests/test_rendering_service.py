from __future__ import annotations

from contextlib import chdir
import tempfile
import unittest
from pathlib import Path

from data_note.profiles import AsgProfile, PsycheProfile
from data_note.services.rendering_service import RenderingService


class RenderingServiceTests(unittest.TestCase):
    def test_resolve_btk_accession_prefers_primary_then_hap1(self) -> None:
        self.assertEqual(
            RenderingService._resolve_btk_accession(
                {"prim_accession": "GCA_1.1", "hap1_accession": "GCA_h1"}
            ),
            "GCA_1.1",
        )
        self.assertEqual(
            RenderingService._resolve_btk_accession({"hap1_accession": "GCA_h1"}),
            "GCA_h1",
        )
        self.assertIsNone(RenderingService._resolve_btk_accession({}))

    def test_populate_images_uses_profile_figure_plan_for_psyche(self) -> None:
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

            service = RenderingService(
                gscope_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(output_stem or "Fig_2_Gscope"),
                pretext_labeler=lambda tolid, context, output_dir, output_stem=None: make_triple(output_stem or "Fig_3_Pretext"),
                merian_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(output_stem or "Fig_3_Merian"),
                merqury_image_copier=lambda tolid, output_dir, output_stem=None: make_triple(output_stem or "Fig_4_Merqury"),
                btk_image_processor=lambda accession, output_dir, output_names=None: [
                    make_triple((output_names or {}).get("snail", "Fig_5_Snail.png").removesuffix(".png")),
                    make_triple((output_names or {}).get("blob", "Fig_6_Blob.png").removesuffix(".png")),
                ],
            )

            context = {"prim_accession": "GCA_1.1"}
            service._populate_images(PsycheProfile(), "ixExample1", tmpdir, context)

            self.assertEqual(context["Fig_4_Merian"], "![Merian elements](./Fig_4_Merian.gif)")
            self.assertEqual(context["Fig_5_Merqury"], "![Merqury spectra](./Fig_5_Merqury.gif)")
            self.assertEqual(context["Fig_6_Snail"], "![Fig 6 Snail](./Fig_6_Snail.gif)")
            self.assertEqual(context["Fig_7_Blob"], "![Fig 7 Blob](./Fig_7_Blob.gif)")

            self.assertTrue((tmp_path / "Fig_4_Merian.gif").exists())
            self.assertTrue((tmp_path / "Fig_5_Merqury.gif").exists())
            self.assertTrue((tmp_path / "Fig_6_Snail.gif").exists())
            self.assertTrue((tmp_path / "Fig_7_Blob.gif").exists())
            self.assertFalse((tmp_path / "Fig_3_Merian.gif").exists())
            self.assertFalse((tmp_path / "Fig_4_Merqury.gif").exists())
            self.assertFalse((tmp_path / "Fig_5_Snail.gif").exists())
            self.assertFalse((tmp_path / "Fig_6_Blob.gif").exists())

    def test_ensure_tables_preserves_profile_specific_table_keys(self) -> None:
        context = {
            "tables": {
                "table6": {
                    "caption": "Software table",
                    "native_headers": ["**Software**"],
                }
            }
        }

        RenderingService._ensure_tables(context)

        self.assertIn("table6", context["tables"])
        self.assertNotIn("table5", context["tables"])
        self.assertEqual(context["tables"]["table6"]["label"], "tbl:table6")
        self.assertEqual(context["tables"]["table6"]["rows"], [])
        self.assertEqual(context["tables"]["table6"]["native_headers"], ["**Software**"])

    def test_unknown_profile_figures_are_ignored_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context = {"prim_accession": "GCA_1.1"}
            service = RenderingService(
                gscope_image_copier=lambda tolid, output_dir, output_stem=None: None,
                pretext_labeler=lambda tolid, context, output_dir, output_stem=None: None,
                merian_image_copier=lambda tolid, output_dir, output_stem=None: None,
                merqury_image_copier=lambda tolid, output_dir, output_stem=None: None,
                btk_image_processor=lambda accession, output_dir, output_names=None: [],
            )

            service._populate_images(AsgProfile(), "ixExample1", tmpdir, context)

            self.assertNotIn("Fig_7_Metagenome_blob", context)
            self.assertNotIn("Fig_8_Metagenome_tree", context)

    def test_write_note_does_not_create_yaml_in_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            template_path = tmp_path / "template.md"
            template_path.write_text("# {{ species }}\n")

            service = RenderingService(
                gscope_image_copier=lambda tolid, output_dir, output_stem=None: None,
                pretext_labeler=lambda tolid, context, output_dir, output_stem=None: None,
                merian_image_copier=lambda tolid, output_dir, output_stem=None: None,
                merqury_image_copier=lambda tolid, output_dir, output_stem=None: None,
                btk_image_processor=lambda accession, output_dir, output_names=None: [],
            )

            context = {
                "species": "Example species",
                "tolid": "ixExample1",
                "jira": "RC-1000",
            }

            with chdir(tmpdir):
                output_dir = Path(service.write_note(str(template_path), context, AsgProfile()))

            self.assertEqual([path.name for path in output_dir.iterdir()], ["ixExample1.md"])


if __name__ == "__main__":
    unittest.main()
