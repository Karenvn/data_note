from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from data_note.cli import main


class CliTests(unittest.TestCase):
    def test_main_passes_primary_and_alternate_assembly_flags_into_config(self) -> None:
        fake_config = Mock()
        fake_config.profile_name = "darwin"
        fake_pipeline = Mock()
        fake_pipeline.run.return_value = 0

        with (
            patch("data_note.cli.load_config", return_value=fake_config),
            patch("data_note.cli.DataNotePipeline", return_value=fake_pipeline),
        ):
            result = main(
                [
                    "--assembly",
                    "GCA_123456789.1",
                    "--alt-assembly",
                    "GCA_123456790.1",
                    "bioprojects.txt",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(fake_config.assembly_accession, "GCA_123456789.1")
        self.assertEqual(fake_config.alternate_assembly_accession, "GCA_123456790.1")
        self.assertIsNone(fake_config.hap1_assembly_accession)
        self.assertIsNone(fake_config.hap2_assembly_accession)

    def test_main_rejects_mixed_primary_and_haplotype_flags(self) -> None:
        with self.assertRaises(SystemExit):
            main(
                [
                    "--assembly",
                    "GCA_123456789.1",
                    "--hap1-assembly",
                    "GCA_123456790.1",
                    "bioprojects.txt",
                ]
            )

    def test_main_rejects_hap2_without_hap1(self) -> None:
        with self.assertRaises(SystemExit):
            main(
                [
                    "--hap2-assembly",
                    "GCA_123456790.1",
                    "bioprojects.txt",
                ]
            )


if __name__ == "__main__":
    unittest.main()
