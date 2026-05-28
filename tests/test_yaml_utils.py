from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from data_note.yaml_utils import fetch_or_copy_yaml


class YamlUtilsTests(unittest.TestCase):
    @patch("data_note.yaml_utils.subprocess.run")
    def test_fetch_or_copy_yaml_reuses_existing_cache(self, mock_run) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_yaml = Path(tmpdir) / "GRIT-1124.yaml"
            local_yaml.write_text("stale")

            result = fetch_or_copy_yaml(
                local_base=tmpdir,
                tolid="GRIT-1124",
                remote_path="/nfs/path/run.yaml",
                ssh_user="ssh-user",
                ssh_host="tol22",
            )

        self.assertEqual(result, local_yaml)
        mock_run.assert_not_called()

    @patch("data_note.yaml_utils.subprocess.run")
    def test_fetch_or_copy_yaml_reuses_cache_from_search_dir(self, mock_run) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            active_cache = Path(tmpdir) / "active" / "yaml_cache"
            existing_cache = Path(tmpdir) / "other" / "yaml_cache"
            existing_yaml = existing_cache / "GRIT-1124.yaml"
            existing_cache.mkdir(parents=True)
            existing_yaml.write_text("pipeline:\n  - hifiasm (version 1.0.0)\n")

            with patch.dict("os.environ", {"YAML_CACHE_SEARCH_DIRS": str(existing_cache)}):
                result = fetch_or_copy_yaml(
                    local_base=str(active_cache),
                    tolid="GRIT-1124",
                    remote_path="/nfs/path/run.yaml",
                    ssh_user="ssh-user",
                    ssh_host="tol22",
                )

            self.assertEqual(result, active_cache / "GRIT-1124.yaml")
            self.assertEqual(result.read_text(), existing_yaml.read_text())
        mock_run.assert_not_called()

    @patch("data_note.yaml_utils.subprocess.run")
    def test_fetch_or_copy_yaml_fetches_missing_cache(self, mock_run) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_yaml = Path(tmpdir) / "GRIT-1124.yaml"

            with patch.dict("os.environ", {"YAML_CACHE_SEARCH_DIRS": os.devnull}):
                result = fetch_or_copy_yaml(
                    local_base=tmpdir,
                    tolid="GRIT-1124",
                    remote_path="/nfs/path/run.yaml",
                    ssh_user="ssh-user",
                    ssh_host="tol22",
                )

        self.assertEqual(result, local_yaml)
        mock_run.assert_called_once_with(
            ["scp", "-i", ANY, "ssh-user@tol22:/nfs/path/run.yaml", str(local_yaml)],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
