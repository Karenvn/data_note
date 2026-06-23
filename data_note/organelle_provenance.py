from __future__ import annotations

import csv
import json
import logging
import os
import re
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

REFERENCE_FIELD_SUFFIXES = {
    value.removeprefix("mitohifi_reference_") for value in MITOHIFI_REFERENCE_FIELDS.values()
}
REFERENCE_FIELD_SUFFIXES.add("organelle_label")

REFERENCE_PREFIX_ALIASES = {
    "mito_reference_": "mito_reference_",
    "mitochondrial_reference_": "mito_reference_",
    "oatk_mito_reference_": "mito_reference_",
    "plastid_reference_": "plastid_reference_",
    "pltd_reference_": "plastid_reference_",
    "oatk_pltd_reference_": "plastid_reference_",
}

NESTED_REFERENCE_PREFIXES = {
    "mito_reference": "mito_reference",
    "mitochondrial_reference": "mito_reference",
    "oatk_mito_reference": "mito_reference",
    "plastid_reference": "plastid_reference",
    "pltd_reference": "plastid_reference",
    "oatk_pltd_reference": "plastid_reference",
}

MARKER_SEPARATOR_RE = r"(^|[/._\-\s]){}($|[/._\-\s])"


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

        for raw_reference_key, prefix in NESTED_REFERENCE_PREFIXES.items():
            reference = data.get(raw_reference_key)
            if isinstance(reference, Mapping):
                for raw_key, raw_value in reference.items():
                    alias = _reference_field_key(prefix, raw_key)
                    if alias:
                        add(alias, raw_value)

        for raw_key, raw_value in data.items():
            key_text = str(raw_key)
            if key_text in {"mitohifi_reference", *NESTED_REFERENCE_PREFIXES} and isinstance(raw_value, Mapping):
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

    _derive_organelle_reference_from_legacy_fields(context)
    for prefix in ("mito_reference", "plastid_reference"):
        _ensure_reference_text(context, prefix)
        _ensure_reference_organelle_label(context, prefix)

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
    if reference_key := _canonical_reference_key(key):
        return reference_key
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


def _reference_field_key(prefix: str, raw_key: Any) -> str | None:
    if raw_key is None:
        return None
    key = str(raw_key).strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None

    legacy_key = MITOHIFI_REFERENCE_FIELDS.get(key)
    if legacy_key:
        suffix = legacy_key.removeprefix("mitohifi_reference_")
    else:
        suffix = key

    if suffix not in REFERENCE_FIELD_SUFFIXES:
        return None
    return f"{prefix}_{suffix}"


def _canonical_reference_key(key: str) -> str | None:
    for raw_prefix, canonical_prefix in REFERENCE_PREFIX_ALIASES.items():
        if not key.startswith(raw_prefix):
            continue
        suffix = key.removeprefix(raw_prefix)
        if suffix in REFERENCE_FIELD_SUFFIXES:
            return f"{canonical_prefix}{suffix}"
    return None


def _derive_organelle_reference_from_legacy_fields(context: dict[str, str]) -> None:
    kind = _infer_reference_kind(context, "mitohifi_reference")
    if not kind:
        return

    prefix = "mito_reference" if kind == "mito" else "plastid_reference"
    for suffix in REFERENCE_FIELD_SUFFIXES:
        if suffix == "organelle_label":
            continue
        source_key = f"mitohifi_reference_{suffix}"
        target_key = f"{prefix}_{suffix}"
        if source_key in context:
            context.setdefault(target_key, context[source_key])


def _ensure_reference_text(context: dict[str, str], prefix: str) -> None:
    text_key = f"{prefix}_text"
    if context.get(text_key):
        return
    organism = context.get(f"{prefix}_organism")
    accession = context.get(f"{prefix}_accession")
    if organism and accession:
        context[text_key] = f"{organism} ({accession})"
    elif accession:
        context[text_key] = accession


def _ensure_reference_organelle_label(context: dict[str, str], prefix: str) -> None:
    label_key = f"{prefix}_organelle_label"
    if context.get(label_key):
        return
    if not any(key.startswith(f"{prefix}_") for key in context):
        return
    if prefix == "mito_reference":
        context[label_key] = "mitochondrial genome"
    elif prefix == "plastid_reference":
        description = _reference_description(context, prefix)
        context[label_key] = "chloroplast genome" if "chloroplast" in description else "plastid genome"


def _infer_reference_kind(context: dict[str, str], prefix: str) -> str | None:
    description = _reference_description(context, prefix)
    if _has_plastid_marker(description):
        return "plastid"
    if _has_mito_marker(description):
        return "mito"

    path_text = _reference_path_text(context, prefix)
    if _has_plastid_marker(path_text):
        return "plastid"
    if _has_mito_marker(path_text):
        return "mito"
    return None


def _reference_description(context: dict[str, str], prefix: str) -> str:
    return " ".join(
        context.get(f"{prefix}_{suffix}", "")
        for suffix in ("definition", "source")
    ).lower()


def _reference_path_text(context: dict[str, str], prefix: str) -> str:
    return " ".join(
        context.get(f"{prefix}_{suffix}", "")
        for suffix in ("file", "fasta_file", "source_file")
    ).lower()


def _has_plastid_marker(text: str) -> bool:
    return (
        "chloroplast" in text
        or "plastid" in text
        or re.search(MARKER_SEPARATOR_RE.format("pltd"), text) is not None
    )


def _has_mito_marker(text: str) -> bool:
    return (
        "mitochond" in text
        or "mitogenome" in text
        or re.search(MARKER_SEPARATOR_RE.format("mito"), text) is not None
    )
