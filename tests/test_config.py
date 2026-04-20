from __future__ import annotations

import getpass
import unittest
from pathlib import Path

from data_note.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_use_gn_assets_root(self) -> None:
        config = load_config({})
        self.assertEqual(config.server_data_root, Path.home() / "gn_assets")
        self.assertEqual(config.profile_name, "darwin")

    def test_new_assets_env_var_takes_precedence(self) -> None:
        config = load_config(
            {
                "DATA_NOTE_GN_ASSETS": "~/preferred-assets",
                "DATA_NOTE_SERVER_DATA": "~/legacy-assets",
            }
        )
        self.assertEqual(config.server_data_root, Path.home() / "preferred-assets")

    def test_legacy_assets_env_var_still_works(self) -> None:
        config = load_config({"DATA_NOTE_SERVER_DATA": "~/legacy-assets"})
        self.assertEqual(config.server_data_root, Path.home() / "legacy-assets")

    def test_yaml_ssh_defaults_restore_local_workflow(self) -> None:
        config = load_config({})
        self.assertEqual(config.yaml_ssh_user, getpass.getuser())
        self.assertEqual(config.yaml_ssh_host, "tol22")

    def test_author_db_defaults_to_local_sqlite(self) -> None:
        config = load_config({})
        self.assertEqual(config.author_db_path, Path.home() / "gn_assets" / "author_db.sqlite3")

    def test_profile_env_override(self) -> None:
        config = load_config({"DATA_NOTE_PROFILE": "psyche"})
        self.assertEqual(config.profile_name, "psyche")


if __name__ == "__main__":
    unittest.main()
