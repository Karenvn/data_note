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


if __name__ == "__main__":
    unittest.main()
