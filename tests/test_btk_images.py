from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from data_note.btk_images import download_btk_images


class BtkImageTests(unittest.TestCase):
    def test_download_btk_images_falls_back_to_viewer_for_blob_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            calls = []

            def fake_run(command, **kwargs):
                out_path = Path(command[command.index("-o") + 1])
                out_path.write_text("Not Found")
                return SimpleNamespace(stderr="")

            def fake_viewer_download(accession, view, download_dir, output_name=None, **kwargs):
                calls.append((accession, view, output_name))
                Path(download_dir, output_name).write_bytes(b"png")
                return True

            with patch("data_note.btk_images.subprocess.run", side_effect=fake_run), patch(
                "data_note.btk_images.download_btk_view_from_viewer",
                side_effect=fake_viewer_download,
            ):
                downloaded = download_btk_images(
                    "GCA_963669245.1",
                    tmpdir,
                    output_names={"blob": "Fig_6_Blob.png"},
                )

            self.assertEqual(downloaded, ["Fig_6_Blob.png"])
            self.assertEqual(calls, [("GCA_963669245.1", "blob", "Fig_6_Blob.png")])
            self.assertEqual(Path(tmpdir, "Fig_6_Blob.png").read_bytes(), b"png")

    def test_download_btk_images_uses_api_blob_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:

            def fake_run(command, **kwargs):
                out_path = Path(command[command.index("-o") + 1])
                out_path.write_bytes(b"\x89PNG\r\n")
                return SimpleNamespace(stderr="")

            with patch("data_note.btk_images.subprocess.run", side_effect=fake_run), patch(
                "data_note.btk_images.download_btk_view_from_viewer",
                return_value=False,
            ) as viewer_download:
                downloaded = download_btk_images(
                    "GCA_964058795.1",
                    tmpdir,
                    output_names={"blob": "Fig_6_Blob.png"},
                )

            self.assertEqual(downloaded, ["Fig_6_Blob.png"])
            viewer_download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
