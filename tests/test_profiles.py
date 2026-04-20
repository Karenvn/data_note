from __future__ import annotations

import unittest
from unittest.mock import patch

from data_note.profiles import DarwinProfile, PsycheProfile, get_profile
from data_note.profiles.base import TableSpec


class ProfileTests(unittest.TestCase):
    def test_get_profile_defaults_to_darwin(self) -> None:
        profile = get_profile()
        self.assertIsInstance(profile, DarwinProfile)

    def test_get_profile_resolves_psyche(self) -> None:
        profile = get_profile("psyche")
        self.assertIsInstance(profile, PsycheProfile)

    def test_get_profile_rejects_unknown_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown data_note profile"):
            get_profile("unknown")

    def test_darwin_profile_declares_darwin_table_order(self) -> None:
        profile = DarwinProfile()
        self.assertEqual(
            tuple(spec.key for spec in profile.table_specs()),
            ("table1", "table2", "table3", "table4", "table5"),
        )
        self.assertTrue(all(spec.builder.__module__ == "data_note.tables.darwin" for spec in profile.table_specs()))

    def test_psyche_profile_has_separate_table_module(self) -> None:
        profile = PsycheProfile()
        self.assertEqual(
            tuple(spec.key for spec in profile.table_specs()),
            ("table1", "table2", "table3", "table4", "table5"),
        )
        self.assertTrue(all(spec.builder.__module__ == "data_note.tables.psyche" for spec in profile.table_specs()))

    def test_profile_build_tables_uses_table_specs(self) -> None:
        profile = DarwinProfile()
        context = {"species": "Example species"}

        with patch.object(
            DarwinProfile,
            "table_specs",
            return_value=(TableSpec("table1", lambda ctx: {"rows": [ctx["species"]] }),),
        ):
            result = profile.build_tables(context)

        self.assertEqual(result["tables"], {"table1": {"rows": ["Example species"]}})


if __name__ == "__main__":
    unittest.main()
