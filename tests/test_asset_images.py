from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from data_note.asset_images import copy_merian_image


class AssetImageTests(unittest.TestCase):
    def test_copy_merian_image_accepts_merians_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "merians" / "ixExample1"
            source_dir.mkdir(parents=True)
            Image.new("RGB", (8, 8), "white").save(source_dir / "plot.png")

            output_dir = root / "out"
            with patch("data_note.asset_images.GN_ASSETS_ROOT", str(root)):
                result = copy_merian_image("ixExample1", output_dir, output_stem="Fig_4_Merian")

            self.assertIsNotNone(result)
            assert result is not None
            png_path, tif_path, gif_path = result
            self.assertEqual(png_path.name, "Fig_4_Merian.png")
            self.assertTrue(png_path.exists())
            self.assertTrue(tif_path.exists())
            self.assertTrue(gif_path.exists())

    def test_copy_merian_image_generates_plot_from_busco_when_png_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            busco_dir = root / "busco" / "ilExample1"
            busco_dir.mkdir(parents=True)
            (root / "Merian_elements_full_table.tsv").write_text(
                "\n".join(f"{index}at7088\tComplete\tM8\t0\t1" for index in range(5)) + "\n"
            )
            (busco_dir / "full_table.tsv").write_text(
                "# Busco id\tStatus\tSequence\tGene Start\tGene End\n"
                + "\n".join(
                    f"{index}at7088\tComplete\tOZ000001.1\t{1000 + index * 100}\t{1050 + index * 100}"
                    for index in range(5)
                )
                + "\n"
            )
            context = {
                "chromosome_data": [
                    {"INSDC": "OZ000001.1", "molecule": "1", "length": "1.5", "GC": "38.5"}
                ]
            }

            output_dir = root / "out"
            with patch("data_note.asset_images.GN_ASSETS_ROOT", str(root)):
                result = copy_merian_image("ilExample1", output_dir, output_stem="Fig_4_Merian", context=context)

            self.assertIsNotNone(result)
            assert result is not None
            png_path, tif_path, gif_path = result
            self.assertTrue(png_path.exists())
            self.assertGreater(png_path.stat().st_size, 0)
            self.assertTrue(tif_path.exists())
            self.assertTrue(gif_path.exists())


if __name__ == "__main__":
    unittest.main()
