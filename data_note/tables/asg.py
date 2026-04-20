from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import build_native_table, flatten_cell, safe_str
from .darwin import (
    make_table1_rows as _make_table1_rows,
    make_table2_rows as _make_table2_rows,
    make_table3_rows as _make_table3_rows,
    make_table4_rows as _make_table4_rows,
    make_table5_rows as _make_table5_rows,
)


def make_table1_rows(context: dict[str, Any]) -> dict[str, Any]:
    return _make_table1_rows(context)


def make_table2_rows(context: dict[str, Any]) -> dict[str, Any]:
    return _make_table2_rows(context)


def make_table3_rows(context: dict[str, Any]) -> dict[str, Any]:
    return _make_table3_rows(context)


def make_table4_rows(context: dict[str, Any]) -> dict[str, Any]:
    return _make_table4_rows(context)


def _coerce_metagenome_row(
    row: Mapping[str, Any] | Sequence[Any],
    keys: Sequence[str],
) -> list[str]:
    if isinstance(row, Mapping):
        return [flatten_cell(row.get(key)) for key in keys]
    return [flatten_cell(value) for value in row]


def make_table5_rows(context: dict[str, Any]) -> dict[str, Any] | None:
    if not context.get("has_metagenome"):
        return None

    prebuilt = context.get("metagenome_table")
    if isinstance(prebuilt, Mapping):
        table = dict(prebuilt)
        table.setdefault("label", "tbl:table5")
        table.setdefault(
            "caption",
            f"Summary of taxa and quality metrics for metagenome bins recovered alongside *{safe_str(context.get('species'))}*",
        )
        table.setdefault("alignment", "")
        table.setdefault("rows", [])
        table.setdefault("native_headers", [])
        table.setdefault("native_align", [])
        table.setdefault("native_rows", [])
        return table

    headers = context.get("metagenome_table_headers")
    raw_rows = context.get("metagenome_table_rows")
    row_keys = context.get("metagenome_table_keys") or headers
    if not isinstance(headers, Sequence) or isinstance(headers, (str, bytes)):
        return None
    if not isinstance(row_keys, Sequence) or isinstance(row_keys, (str, bytes)):
        return None
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)) or not raw_rows:
        return None

    body = [_coerce_metagenome_row(row, row_keys) for row in raw_rows]
    header_cells = [str(header) for header in headers]
    native_table = build_native_table(header_cells, body)

    return {
        "label": "tbl:table5",
        "caption": context.get("metagenome_table_caption")
        or f"Summary of taxa and quality metrics for metagenome bins recovered alongside *{safe_str(context.get('species'))}*",
        "alignment": context.get("metagenome_table_alignment") or ("L" * len(header_cells)),
        "rows": [",".join(header_cells)] + [",".join(row) for row in body],
        **native_table,
    }


def make_table6_rows(context: dict[str, Any]) -> dict[str, Any]:
    table = dict(_make_table5_rows(context))
    table["label"] = "tbl:table6"
    return table
