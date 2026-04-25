from __future__ import annotations

from pathlib import Path
import tempfile
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
                    "PRJEB12345",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(fake_config.assembly_accession, "GCA_123456789.1")
        self.assertEqual(fake_config.alternate_assembly_accession, "GCA_123456790.1")
        self.assertIsNone(fake_config.hap1_assembly_accession)
        self.assertIsNone(fake_config.hap2_assembly_accession)
        fake_pipeline.run.assert_called_once_with(
            bioproject_input="PRJEB12345",
            template_file="template.md",
            error_file="error_log.txt",
        )

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

    def test_main_rejects_assembly_override_for_bioproject_list_input(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("PRJEB12345\nPRJEB67890\n")
            bioproject_file = handle.name
        try:
            with self.assertRaises(SystemExit):
                main(
                    [
                        "--assembly",
                        "GCA_123456789.1",
                        bioproject_file,
                    ]
                )
        finally:
            Path(bioproject_file).unlink()


if __name__ == "__main__":
    unittest.main()
