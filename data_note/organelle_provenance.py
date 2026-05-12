from __future__ import annotations

import csv
import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

MITOHIFI_REFERENCE_FIELDS = {
    "accession": "mitohifi_reference_accession",
    "definition": "mitohifi_reference_definition",
    "fasta_file": "mitohifi_reference_fasta_file",
    "file": "mitohifi_reference_file",
    "organism": "mitohifi_reference_organism",
    "selection_taxa": "mitohifi_reference_selection_taxa",
    "source": "mitohifi_reference_source",
    "source_file": "mitohifi_reference_source_file",
    "source_step": "mitohifi_reference_source_step",
    "text": "mitohifi_reference_text",
}


def organelle_provenance_dir(assets_root: str | Path | None = None) -> Path:
    configured = os.getenv("DATA_NOTE_ORGANELLE_PROVENANCE_DIR")
    if configured:
        return Path(configured).expanduser()

    root = Path(
        assets_root
        or os.getenv(
            "DATA_NOTE_GN_ASSETS",
            os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "gn_assets")),
        )
    ).expanduser()
    return root / "organelle_provenance"


def read_local_organelle_provenance(tolid: str | None, assets_root: str | Path | None = None) -> dict[str, str]:
    if not tolid:
        return {}

    for candidate in _candidate_files(tolid, organelle_provenance_dir(assets_root)):
        if not candidate.exists():
            continue
        try:
            return parse_organelle_provenance_file(candidate)
        except Exception as exc:
            logger.warning("Failed to parse organelle provenance from %s: %s", candidate, exc)
            return {}
    return {}


def parse_organelle_provenance_file(path: str | Path) -> dict[str, str]:
    provenance_file = Path(path)
    suffix = provenance_file.suffix.lower()
    if suffix == ".json":
        data = json.loads(provenance_file.read_text())
    elif suffix in {".tsv", ".csv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        data = _read_delimited_provenance(provenance_file, delimiter=delimiter)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(provenance_file.read_text())
    else:
        raise ValueError(f"Unsupported organelle provenance file type: {provenance_file.suffix}")

    return normalise_organelle_provenance(data)


def normalise_organelle_provenance(data: Any) -> dict[str, str]:
    context: dict[str, str] = {}

    def add(raw_key: Any, raw_value: Any) -> None:
        key = _canonical_key(raw_key)
        if not key:
            return
        value = _scalar_text(raw_value)
        if value:
            context[key] = value

    if isinstance(data, Mapping):
        mitohifi_reference = data.get("mitohifi_reference")
        if isinstance(mitohifi_reference, Mapping):
            for raw_key, raw_value in mitohifi_reference.items():
                alias = MITOHIFI_REFERENCE_FIELDS.get(str(raw_key).strip().lower())
                if alias:
                    add(alias, raw_value)

        for raw_key, raw_value in data.items():
            key_text = str(raw_key)
            if key_text == "mitohifi_reference" and isinstance(raw_value, Mapping):
                continue
            add(key_text, raw_value)
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, Mapping):
                continue
            add(
                item.get("field") or item.get("key") or item.get("name"),
                item.get("value"),
            )

    if "mitohifi_reference_text" not in context:
        organism = context.get("mitohifi_reference_organism")
        accession = context.get("mitohifi_reference_accession")
        if organism and accession:
            context["mitohifi_reference_text"] = f"{organism} ({accession})"
        elif accession:
            context["mitohifi_reference_text"] = accession

    return dict(sorted(context.items()))


def _candidate_files(tolid: str, root: Path) -> tuple[Path, ...]:
    return (
        root / f"{tolid}.organelle_provenance.yml",
        root / f"{tolid}.organelle_provenance.yaml",
        root / f"{tolid}.organelle_provenance.json",
        root / f"{tolid}.organelle_provenance.tsv",
        root / f"{tolid}.yml",
        root / f"{tolid}.yaml",
        root / f"{tolid}.json",
        root / tolid / f"{tolid}.organelle_provenance.yml",
        root / tolid / f"{tolid}.organelle_provenance.yaml",
        root / tolid / f"{tolid}.organelle_provenance.json",
        root / tolid / f"{tolid}.organelle_provenance.tsv",
        root / tolid / "organelle_provenance.yml",
        root / tolid / "organelle_provenance.yaml",
        root / tolid / "organelle_provenance.json",
        root / tolid / "organelle_provenance.tsv",
    )


def _read_delimited_provenance(path: Path, *, delimiter: str) -> list[dict[str, str]]:
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
                rows.append({"field": row[0], "value": row[1]})
        return rows


def _canonical_key(raw_key: Any) -> str | None:
    if raw_key is None:
        return None
    key = str(raw_key).strip().lower()
    if not key:
        return None
    key = key.replace("-", "_").replace(" ", "_")
    if key in MITOHIFI_REFERENCE_FIELDS:
        return MITOHIFI_REFERENCE_FIELDS[key]
    if key.startswith("mitohifi_reference_") or key in {
        "mitohifi_version",
        "mitohifi_version_source_file",
        "tolid",
    }:
        return key
    return None


def _scalar_text(raw_value: Any) -> str | None:
    if raw_value is None or isinstance(raw_value, Mapping):
        return None
    if isinstance(raw_value, list):
        values = [text for item in raw_value if (text := _scalar_text(item))]
        return "; ".join(values) if values else None
    value = str(raw_value).strip()
    if not value or value.lower() in {"na", "n/a", "none", "null"}:
        return None
    return value
