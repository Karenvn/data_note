from __future__ import annotations

import argparse

from .config import load_config
from .io_utils import read_bioprojects_input
from .models import AssemblySelectionInput
from .pipeline import DataNotePipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate genome notes for a list of BioProject IDs.")
    parser.add_argument(
        "bioproject_input",
        nargs="?",
        default="bioprojects.txt",
        help="Path to a file containing BioProjects, or a single BioProject accession.",
    )
    parser.add_argument("--template_file", default="template.md", help="Path to the Markdown template file.")
    parser.add_argument("--error-file", default="error_log.txt", help="Path to the error log file.")
    parser.add_argument(
        "--profile",
        help="Programme profile to use for note layout and tables. Defaults to DATA_NOTE_PROFILE or darwin.",
    )
    parser.add_argument(
        "--assembly",
        help="Preferred primary or haplotype 1 assembly accession for a single BioProject input. The matching alternate or haplotype 2 is inferred when possible.",
    )
    parser.add_argument(
        "--alt-assembly",
        help="Explicit alternate haplotype accession to pair with --assembly for a single BioProject input.",
    )
    parser.add_argument(
        "--hap1-assembly",
        help="Explicit haplotype 1 accession for a single BioProject input. Use this to force haplotype assembly selection.",
    )
    parser.add_argument(
        "--hap2-assembly",
        help="Explicit haplotype 2 accession to pair with --hap1-assembly for a single BioProject input.",
    )
    parser.add_argument(
        "--include-gbif-distribution",
        action="store_true",
        help="Fetch and render an additional GBIF distribution summary. Disabled by default because it adds extra API calls.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    if args.profile:
        config.profile_name = args.profile.strip().lower()
    if args.include_gbif_distribution:
        config.include_gbif_distribution = True
    selection_input = AssemblySelectionInput(
        assembly_accession=args.assembly,
        alternate_accession=args.alt_assembly,
        hap1_accession=args.hap1_assembly,
        hap2_accession=args.hap2_assembly,
    )
    if selection_input.has_any():
        try:
            selection_input.validate()
            if len(read_bioprojects_input(args.bioproject_input)) != 1:
                raise ValueError(
                    "Assembly selection overrides require exactly one BioProject input, not a list"
                )
        except ValueError as exc:
            parser.error(str(exc))
        except FileNotFoundError as exc:
            parser.error(str(exc))
        config.assembly_accession = selection_input.assembly_accession
        config.alternate_assembly_accession = selection_input.alternate_accession
        config.hap1_assembly_accession = selection_input.hap1_accession
        config.hap2_assembly_accession = selection_input.hap2_accession
    pipeline = DataNotePipeline(config)
    return pipeline.run(
        bioproject_input=args.bioproject_input,
        template_file=args.template_file,
        error_file=args.error_file,
    )
