from __future__ import annotations

import re


SEX_CHROMOSOME_LABELS = frozenset({"X", "X1", "X2", "Y", "W", "Z", "Z1", "Z2"})


def na(value):
    r"""
    Return a printable value for Table 2.
    Empty strings, None, or the integer 0 become r'\-';
    everything else is converted to str unchanged.
    """
    if value in (None, "", 0, "0"):
        return r"\-"
    return str(value)


def safe_str(value):
    """Convert value to string, avoiding NoneType."""
    return str(value) if value is not None else ""


def flatten_cell(value, digits=2):
    """Flatten table cell to safe string format."""
    if value is None:
        return ""
    if isinstance(value, list):
        # Join with U+202F (narrow no-break space + regular comma)
        return "\u202f, ".join(flatten_cell(v, digits=digits) for v in value)
    if isinstance(value, (int, float)):
        try:
            if isinstance(value, int) or float(value).is_integer():
                return f"{int(value):,}".replace(",", "\u202f")
            else:
                return f"{float(value):,.{digits}f}".replace(",", "\u202f")
        except Exception:
            pass
    return str(value)


def native_cell(value):
    """Escape a value for a native Pandoc pipe-table cell."""
    if value is None:
        return r"\-"
    cell = str(value).replace("\n", " ").replace("|", r"\|").strip()
    return cell if cell else r"\-"


def build_native_table(headers, rows):
    """Build headers/alignment/rows for native Pandoc tables."""
    return {
        "native_headers": [native_cell(h) for h in headers],
        "native_align": [":--"] * len(headers),
        "native_rows": [[native_cell(c) for c in row] for row in rows],
    }


def parse_sex_chromosome_labels(value) -> set[str]:
    """Parse a stored sex-chromosome summary into normalized labels."""
    if not value:
        return set()
    if isinstance(value, (list, tuple, set)):
        labels: set[str] = set()
        for item in value:
            labels.update(parse_sex_chromosome_labels(item))
        return labels

    text = str(value).strip()
    if not text:
        return set()

    parts = re.split(r",|;|\band\b", text, flags=re.IGNORECASE)
    return {
        part.strip().upper()
        for part in parts
        if part.strip().upper() in SEX_CHROMOSOME_LABELS
    }


def filter_primary_chromosome_rows(rows, allowed_sex_labels: set[str]):
    """Drop sex-chromosome rows that are not reported for this assembly."""
    filtered = []
    for row in rows:
        molecule = str(row.get("molecule", "")).strip().upper()
        if molecule in SEX_CHROMOSOME_LABELS and molecule not in allowed_sex_labels:
            continue
        filtered.append(row)
    return filtered


def filter_combined_haplotype_rows(
    rows,
    hap1_allowed_sex_labels: set[str],
    hap2_allowed_sex_labels: set[str],
):
    """Blank out absent sex-chromosome entries and drop rows that become empty."""
    filtered = []
    for row in rows:
        updated = dict(row)

        hap1_molecule = str(updated.get("hap1_molecule", "")).strip().upper()
        if hap1_molecule in SEX_CHROMOSOME_LABELS and hap1_molecule not in hap1_allowed_sex_labels:
            for key in ("hap1_INSDC", "hap1_molecule", "hap1_length", "hap1_GC"):
                updated[key] = ""

        hap2_molecule = str(updated.get("hap2_molecule", "")).strip().upper()
        if hap2_molecule in SEX_CHROMOSOME_LABELS and hap2_molecule not in hap2_allowed_sex_labels:
            for key in ("hap2_INSDC", "hap2_molecule", "hap2_length", "hap2_GC"):
                updated[key] = ""

        if updated.get("hap1_molecule") or updated.get("hap2_molecule"):
            filtered.append(updated)

    return filtered


def coerce_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def infer_haploid_note(context) -> bool:
    if str(context.get("assemblies_type") or "").strip() != "prim_alt":
        return False
    if "has_alternate_assembly" in context:
        no_alternate_assembly = not coerce_bool(context.get("has_alternate_assembly"))
    else:
        no_alternate_assembly = not bool(context.get("alt_accession") or context.get("alt_assembly_name"))
    if not no_alternate_assembly:
        return False

    if str(context.get("group_name_ncbi") or "").strip().lower() == "mosses":
        return True

    order_name = str(context.get("order") or "").strip().lower()
    observed_sex = str(context.get("observed_sex") or "").strip().lower()
    return order_name == "hymenoptera" and observed_sex in {"male", "m"}


def is_haploid_note(context) -> bool:
    if "is_haploid" in context:
        return coerce_bool(context.get("is_haploid"))
    if "render_as_haploid" in context:
        return coerce_bool(context.get("render_as_haploid"))
    return infer_haploid_note(context)


def has_alternate_assembly(context) -> bool:
    if is_haploid_note(context):
        return False
    if "has_alternate_assembly" in context:
        return coerce_bool(context.get("has_alternate_assembly"))
    return bool(context.get("alt_accession"))


def resolve_single_assembly_label(context) -> str:
    custom = context.get("single_assembly_label")
    if custom:
        return str(custom)
    return "Haploid assembly" if is_haploid_note(context) else "Primary assembly"


def resolve_single_assembly_phrase(context) -> str:
    custom = context.get("single_assembly_phrase")
    if custom:
        return str(custom)
    return "haploid genome assembly" if is_haploid_note(context) else "primary genome assembly"


def resolve_single_assembly_metric_label(context) -> str:
    custom = context.get("single_assembly_metric_label")
    if custom:
        return str(custom)
    return "haploid assembly" if is_haploid_note(context) else "primary"


def resolve_single_assembly_metric_prefix(context) -> str:
    custom = context.get("single_assembly_metric_prefix")
    if custom:
        return str(custom)
    return "Haploid assembly" if is_haploid_note(context) else "Primary"
