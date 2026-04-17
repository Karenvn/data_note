from __future__ import annotations

import argparse

from .config import load_config
from .pipeline import DataNotePipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate genome notes for a list of BioProject IDs.")
    parser.add_argument(
        "bioproject_file",
        nargs="?",
        default="bioprojects.txt",
        help="Path to the file containing the list of BioProjects.",
    )
    parser.add_argument("--template_file", default="template.md", help="Path to the Markdown template file.")
    parser.add_argument("--error-file", default="error_log.txt", help="Path to the error log file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = DataNotePipeline(load_config())
    return pipeline.run(
        bioproject_file=args.bioproject_file,
        template_file=args.template_file,
        error_file=args.error_file,
    )
