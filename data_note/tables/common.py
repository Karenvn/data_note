from __future__ import annotations


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
