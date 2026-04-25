from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from data_note.yaml_utils import fetch_or_copy_yaml


class YamlUtilsTests(unittest.TestCase):
    @patch("data_note.yaml_utils.subprocess.run")
    def test_fetch_or_copy_yaml_refreshes_existing_cache(self, mock_run) -> None:
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
        mock_run.assert_called_once_with(
            ["scp", "-i", ANY, "ssh-user@tol22:/nfs/path/run.yaml", str(local_yaml)],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
