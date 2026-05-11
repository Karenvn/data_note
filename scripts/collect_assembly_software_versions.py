#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_note.software_versions import normalise_software_versions, parse_software_versions_file  # noqa: E402


VERSION_SUFFIXES = {".yml", ".yaml", ".json", ".tsv", ".csv"}
REPORT_NAMES = {
    ".nextflow.log",
    "nextflow.log",
    "pipeline_report.txt",
    "pipeline_report.html",
    "params.json",
}
SKIP_DIRS = {
    ".git",
    ".nextflow",
    "work",
    "tmp",
    "temp",
    "__pycache__",
}

TREEVAL_VERSION_PATTERNS = (
    re.compile(
        r"sanger[-/]tol[/\s]+treeval[^\n\r]*(?:version|revision|release|v)"
        r"[:\s=-]*v?(\d+(?:\.\d+)+(?:[-._A-Za-z0-9]+)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btreeval[^\n\r]*(?:version|revision|release|v)"
        r"[:\s=-]*v?(\d+(?:\.\d+)+(?:[-._A-Za-z0-9]+)?)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:^|\s)(?:-r|--revision)\s+v?(\d+(?:\.\d+)+(?:[-._A-Za-z0-9]+)?)"),
)
NEXTFLOW_VERSION_PATTERNS = (
    re.compile(r"N\s*E\s*X\s*T\s*F\s*L\s*O\s*W\s*~\s*version\s+v?(\d+(?:\.\d+)+(?:[-._A-Za-z0-9]+)?)", re.IGNORECASE),
    re.compile(r"\bnextflow\b[^\n\r]*(?:version|~)\s*v?(\d+(?:\.\d+)+(?:[-._A-Za-z0-9]+)?)", re.IGNORECASE),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect software versions for one assembly from TreeVal/Nextflow output "
            "and write a normalised gn_assets software_versions file."
        )
    )
    parser.add_argument("tolid", help="Assembly ToLID, used for output naming and server-folder filtering.")
    parser.add_argument(
        "--run-dir",
        action="append",
        default=[],
        help="A specific TreeVal result/run directory to inspect. Can be used more than once.",
    )
    parser.add_argument(
        "--work-root",
        action="append",
        default=[],
        help="Assembly work root to trawl when the exact run directory is not known. Can be used more than once.",
    )
    parser.add_argument(
        "--outdir",
        default=os.getenv(
            "DATA_NOTE_SOFTWARE_VERSIONS_DIR",
            str(Path.home() / "gn_assets" / "software_versions"),
        ),
        help="Directory for the normalised output file.",
    )
    parser.add_argument("--output", help="Exact output path. Defaults to OUTDIR/<tolid>.yml.")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=8,
        help="Maximum directory depth when walking --work-root. Default: 8.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print versions without writing the output file.")
    parser.add_argument("--verbose", action="store_true", help="Print source files considered to stderr.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dirs = [Path(value).expanduser() for value in args.run_dir]
    work_roots = [Path(value).expanduser() for value in args.work_root]
    if not run_dirs and not work_roots:
        raise SystemExit("Provide at least one --run-dir or --work-root.")

    version_files = list(find_version_files(args.tolid, run_dirs, work_roots, max_depth=args.max_depth))
    report_files = list(find_report_files(run_dirs, version_files))

    source_mappings: list[dict[str, Any]] = []
    for version_file in version_files:
        try:
            source_mappings.append(parse_software_versions_file(version_file))
        except Exception as exc:
            print(f"warning: failed to parse {version_file}: {exc}", file=sys.stderr)

    for report_file in report_files:
        source_mappings.append(extract_versions_from_report(report_file))

    versions = normalise_software_versions(source_mappings)
    if not versions:
        print(f"No software versions found for {args.tolid}.", file=sys.stderr)
        return 1

    if args.verbose:
        for path in [*version_files, *report_files]:
            print(f"source: {path}", file=sys.stderr)

    output_path = Path(args.output).expanduser() if args.output else Path(args.outdir).expanduser() / f"{args.tolid}.yml"
    if args.dry_run:
        print(yaml.safe_dump(versions, sort_keys=True), end="")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(versions, sort_keys=True))
    print(f"Wrote {len(versions)} software version fields to {output_path}")
    return 0


def find_version_files(
    tolid: str,
    run_dirs: Iterable[Path],
    work_roots: Iterable[Path],
    *,
    max_depth: int,
) -> Iterable[Path]:
    seen: set[Path] = set()

    def emit(path: Path) -> Iterable[Path]:
        resolved = path.resolve()
        if resolved not in seen and path.exists() and path.is_file():
            seen.add(resolved)
            yield path

    for run_dir in run_dirs:
        for path in _known_version_paths(run_dir):
            yield from emit(path)
        for path in _walk_files(run_dir, _is_version_file, max_depth=max_depth):
            yield from emit(path)

    tolid_lower = tolid.lower()
    for work_root in work_roots:
        for path in _walk_files(work_root, _is_version_file, max_depth=max_depth):
            if tolid_lower in str(path).lower():
                yield from emit(path)


def find_report_files(run_dirs: Iterable[Path], version_files: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    candidate_dirs: list[Path] = []

    for run_dir in run_dirs:
        candidate_dirs.extend([run_dir, run_dir / "pipeline_info", run_dir / "treeval_info"])
    for version_file in version_files:
        candidate_dirs.extend([version_file.parent, version_file.parent.parent])

    for directory in candidate_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            if path.name in REPORT_NAMES or path.name.startswith("TreeVal_Runs"):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield path


def extract_versions_from_report(path: Path) -> dict[str, str]:
    if path.suffix.lower() == ".json":
        return _extract_versions_from_json(path)

    try:
        text = path.read_text(errors="replace")
    except OSError:
        return {}

    found: dict[str, str] = {}
    for pattern in TREEVAL_VERSION_PATTERNS:
        match = pattern.search(text)
        if match:
            found["treeval_version"] = match.group(1)
            break
    for pattern in NEXTFLOW_VERSION_PATTERNS:
        match = pattern.search(text)
        if match:
            found["nextflow_version"] = match.group(1)
            break
    return found


def _extract_versions_from_json(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}

    found: dict[str, str] = {}
    for key in ("treeval_version", "nextflow_version"):
        value = data.get(key)
        if value:
            found[key] = str(value)
    revision = data.get("revision") or data.get("pipeline_revision")
    if revision and "treeval_version" not in found:
        found["treeval_version"] = str(revision)
    return found


def _known_version_paths(run_dir: Path) -> tuple[Path, ...]:
    return (
        run_dir / "pipeline_info" / "treeval_software_versions.yml",
        run_dir / "pipeline_info" / "software_versions.yml",
        run_dir / "treeval_info" / "treeval_software_versions.yml",
        run_dir / "treeval_info" / "software_versions.yml",
    )


def _walk_files(root: Path, predicate: Callable[[Path], bool], *, max_depth: int) -> Iterable[Path]:
    root = root.expanduser()
    if not root.exists():
        return

    root_depth = len(root.resolve().parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.resolve().parts) - root_depth
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".")]

        for filename in files:
            path = current_path / filename
            if predicate(path):
                yield path


def _is_version_file(path: Path) -> bool:
    name = path.name.lower()
    if path.suffix.lower() not in VERSION_SUFFIXES:
        return False
    if "version" in name and ("software" in name or name in {"versions.yml", "versions.yaml"}):
        return True
    return name in {"treeval_software_versions.yml", "treeval_software_versions.yaml"}


if __name__ == "__main__":
    raise SystemExit(main())
