from __future__ import annotations

import csv
import json
import logging
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)

VERSION_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*_version$")

SOFTWARE_VERSION_ALIASES = {
    "blast": "blast_version",
    "blobtk": "blobtk_version",
    "blobtoolkit": "blobtoolkit_version",
    "busco": "busco_version",
    "bwa mem2": "bwa_mem2_version",
    "bwa-mem2": "bwa_mem2_version",
    "bwamem2": "bwa_mem2_version",
    "diamond": "diamond_version",
    "fasta windows": "fasta_windows_version",
    "fasta_windows": "fasta_windows_version",
    "fastk": "fastk_version",
    "genomescope": "genomescope_version",
    "genomescope2": "genomescope_version",
    "genomescope2.0": "genomescope_version",
    "gfastats": "gfastats_version",
    "hifiasm": "hifiasm_version",
    "higlass": "higlass_version",
    "lep busco painter": "lep_busco_painter_version",
    "lep_busco_painter": "lep_busco_painter_version",
    "merian busco painter": "merian_busco_painter_version",
    "merian-busco-painter": "merian_busco_painter_version",
    "merian_busco_painter": "merian_busco_painter_version",
    "merqury fk": "merquryfk_version",
    "merqury.fk": "merquryfk_version",
    "merquryfk": "merquryfk_version",
    "minimap2": "minimap2_version",
    "mitohifi": "mitohifi_version",
    "multiqc": "multiqc_version",
    "nextflow": "nextflow_version",
    "oatk": "oatk_version",
    "pretext graph": "pretextgraph_version",
    "pretextgraph": "pretextgraph_version",
    "pretext snapshot": "pretextsnapshot_version",
    "pretextsnapshot": "pretextsnapshot_version",
    "pretext view": "pretextview_version",
    "pretextview": "pretextview_version",
    "purge dups": "purge_dups_version",
    "purge_dups": "purge_dups_version",
    "samtools": "samtools_version",
    "sanger-tol/ascc": "ascc_version",
    "ascc": "ascc_version",
    "sanger-tol/blobtoolkit": "btk_pipeline_version",
    "sanger tol blobtoolkit": "btk_pipeline_version",
    "sanger-tol/curationpretext": "curationpretext_version",
    "curationpretext": "curationpretext_version",
    "seqtk": "seqtk_version",
    "singularity": "singularity_version",
    "sylabs/singularity": "singularity_version",
    "treeval": "treeval_version",
    "sanger-tol/treeval": "treeval_version",
    "sanger tol treeval": "treeval_version",
    "yahs": "yahs_version",
}


def software_versions_dir(assets_root: str | Path | None = None) -> Path:
    configured = os.getenv("DATA_NOTE_SOFTWARE_VERSIONS_DIR")
    if configured:
        return Path(configured).expanduser()

    root = Path(
        assets_root
        or os.getenv(
            "DATA_NOTE_GN_ASSETS",
            os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "gn_assets")),
        )
    ).expanduser()
    return root / "software_versions"


def read_local_software_versions(tolid: str | None, assets_root: str | Path | None = None) -> dict[str, str]:
    if not tolid:
        return {}

    for candidate in _candidate_files(tolid, software_versions_dir(assets_root)):
        if not candidate.exists():
            continue
        try:
            return parse_software_versions_file(candidate)
        except Exception as exc:
            logger.warning("Failed to parse software versions from %s: %s", candidate, exc)
            return {}
    return {}


def parse_software_versions_file(path: str | Path) -> dict[str, str]:
    version_file = Path(path)
    suffix = version_file.suffix.lower()
    if suffix == ".json":
        data = json.loads(version_file.read_text())
    elif suffix in {".tsv", ".csv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        data = _read_delimited_versions(version_file, delimiter=delimiter)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(version_file.read_text())
    else:
        raise ValueError(f"Unsupported software version file type: {version_file.suffix}")

    return normalise_software_versions(data)


def normalise_software_versions(data: Any) -> dict[str, str]:
    collected: dict[str, list[str]] = {}

    def add(raw_name: Any, raw_version: Any) -> None:
        key = canonical_version_key(raw_name)
        if not key:
            return
        for version in _version_values(raw_version):
            versions = collected.setdefault(key, [])
            if version not in versions:
                versions.append(version)

    def visit(value: Any, parent_key: str | None = None) -> None:
        if isinstance(value, Mapping):
            if _looks_like_software_record(value):
                add(value.get("software") or value.get("name") or value.get("tool") or parent_key, value.get("version"))
                return

            for raw_key, raw_value in value.items():
                key_text = str(raw_key)
                if _is_context_version_key(key_text):
                    add(key_text, raw_value)
                elif isinstance(raw_value, Mapping):
                    visit(raw_value, parent_key=key_text)
                elif isinstance(raw_value, list):
                    if _version_values(raw_value):
                        add(key_text, raw_value)
                    else:
                        visit(raw_value, parent_key=key_text)
                else:
                    add(key_text, raw_value)
            return

        if isinstance(value, list):
            for item in value:
                visit(item, parent_key=parent_key)

    visit(data)

    return {key: "; ".join(sorted(values)) for key, values in sorted(collected.items()) if values}


def canonical_version_key(raw_name: Any) -> str | None:
    if raw_name is None:
        return None
    name = _clean_name(str(raw_name))
    if not name:
        return None
    if _is_context_version_key(name):
        return name
    if name.endswith("_version") and VERSION_KEY_PATTERN.match(name):
        return name

    version_suffix = re.search(r"[\s_-]+version$", name)
    if version_suffix:
        base_name = name[: version_suffix.start()]
        alias = SOFTWARE_VERSION_ALIASES.get(base_name)
        if alias:
            return alias
        normalized_base = re.sub(r"[^a-z0-9]+", "_", base_name).strip("_")
        return f"{normalized_base}_version" if normalized_base else None

    alias = SOFTWARE_VERSION_ALIASES.get(name)
    if alias:
        return alias

    normalized = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    if not normalized:
        return None
    return f"{normalized}_version"


def write_software_versions(path: str | Path, versions: Mapping[str, Any]) -> None:
    version_path = Path(path)
    version_path.parent.mkdir(parents=True, exist_ok=True)
    normalised = normalise_software_versions(versions)
    version_path.write_text(yaml.safe_dump(normalised, sort_keys=True))


def _candidate_files(tolid: str, root: Path) -> tuple[Path, ...]:
    return (
        root / f"{tolid}.yml",
        root / f"{tolid}.yaml",
        root / f"{tolid}.software_versions.yml",
        root / f"{tolid}.software_versions.yaml",
        root / f"{tolid}.json",
        root / f"{tolid}.tsv",
        root / tolid / f"{tolid}.software_versions.yml",
        root / tolid / f"{tolid}.software_versions.yaml",
        root / tolid / "software_versions.yml",
        root / tolid / "software_versions.yaml",
        root / tolid / "treeval_software_versions.yml",
        root / tolid / "treeval_software_versions.yaml",
        root / tolid / "pipeline_info" / "treeval_software_versions.yml",
        root / tolid / "pipeline_info" / "software_versions.yml",
        root / tolid / "treeval_info" / "treeval_software_versions.yml",
        root / tolid / "treeval_info" / "software_versions.yml",
    )


def _read_delimited_versions(path: Path, *, delimiter: str) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        except csv.Error:
            has_header = False
        if has_header:
            return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]

        rows: list[dict[str, str]] = []
        for row in csv.reader(handle, delimiter=delimiter):
            if len(row) >= 2:
                rows.append({"software": row[0], "version": row[1]})
        return rows


def _looks_like_software_record(value: Mapping[Any, Any]) -> bool:
    keys = {str(key).strip().lower() for key in value}
    return "version" in keys and bool(keys.intersection({"software", "name", "tool"}))


def _version_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return []
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        versions: list[str] = []
        for item in value:
            versions.extend(_version_values(item))
        return versions

    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() in {"none", "null", "na", "n/a"}:
        return []
    return [cleaned]


def _is_context_version_key(name: str) -> bool:
    return bool(VERSION_KEY_PATTERN.match(name))


def _clean_name(name: str) -> str:
    text = name.strip()
    text = re.sub(r"\s*\(.*?\)\s*$", "", text)
    text = text.replace("__", "_")
    text = text.lower()
    text = text.replace("sanger/tol", "sanger-tol")
    text = re.sub(r"[\[\]`\"']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
