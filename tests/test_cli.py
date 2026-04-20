from __future__ import annotations

import unittest

from data_note.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_parser_defaults(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.bioproject_file, "bioprojects.txt")
        self.assertEqual(args.template_file, "template.md")
        self.assertEqual(args.error_file, "error_log.txt")
        self.assertIsNone(args.profile)

    def test_parser_custom_arguments(self) -> None:
        args = build_parser().parse_args(
            [
                "--template_file",
                "tests/fixtures/template.md",
                "--error-file",
                "tmp-errors.txt",
                "--profile",
                "psyche",
                "tests/fixtures/bioprojects.txt",
            ]
        )
        self.assertEqual(args.template_file, "tests/fixtures/template.md")
        self.assertEqual(args.error_file, "tmp-errors.txt")
        self.assertEqual(args.profile, "psyche")
        self.assertEqual(args.bioproject_file, "tests/fixtures/bioprojects.txt")


if __name__ == "__main__":
    unittest.main()
