from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import build_native_table, flatten_cell, safe_str, software_version
from .darwin import (
    make_table1_rows as _make_table1_rows,
    make_table2_rows as _make_table2_rows,
    make_table3_rows as _make_table3_rows,
    make_table4_rows as _make_table4_rows,
    make_table5_rows as _make_table5_rows,
)


_METAGENOME_SOFTWARE: dict[str, tuple[str, str, str | None, str]] = {
    "bin3c": (
        "bin3C",
        "bin3c_version",
        "0.3.3",
        "[https://github.com/cerebis/bin3C](https://github.com/cerebis/bin3C)",
    ),
    "checkm": (
        "CheckM",
        "checkm_version",
        "2015-01-16",
        "[https://ecogenomics.github.io/CheckM/](https://ecogenomics.github.io/CheckM/)",
    ),
    "dastool": (
        "DAS Tool",
        "dastool_version",
        "1.1.2",
        "[https://github.com/cmks/DAS_Tool](https://github.com/cmks/DAS_Tool)",
    ),
    "drep": (
        "dRep",
        "drep_version",
        "3.4.0",
        "[https://github.com/MrOlm/drep](https://github.com/MrOlm/drep)",
    ),
    "ete3": ("ete3", "ete3_version", "3.1.3", "[http://etetoolkit.org](http://etetoolkit.org)"),
    "flye": (
        "Flye",
        "flye_version",
        None,
        "[https://github.com/mikolmogorov/Flye](https://github.com/mikolmogorov/Flye)",
    ),
    "gtdbtk": (
        "GTDB-Tk",
        "gtdbtk_version",
        "1.2.1",
        "[https://github.com/Ecogenomics/GTDBTk](https://github.com/Ecogenomics/GTDBTk)",
    ),
    "magscot": (
        "MAGScoT",
        "magscot_version",
        "1.0.0",
        "[https://github.com/ikmb/MAGScoT](https://github.com/ikmb/MAGScoT)",
    ),
    "matplotlib": (
        "matplotlib",
        "matplotlib_version",
        "3.10.3",
        "[https://matplotlib.org/](https://matplotlib.org/)",
    ),
    "maxbin2": (
        "MaxBin",
        "maxbin_version",
        "2.2.7",
        "[https://sourceforge.net/projects/maxbin/](https://sourceforge.net/projects/maxbin/)",
    ),
    "metabat2": (
        "MetaBAT2",
        "metabat2_version",
        "2.15-15-gd6ea400",
        "[https://bitbucket.org/berkeleylab/metabat](https://bitbucket.org/berkeleylab/metabat)",
    ),
    "metamdbg": (
        "MetaMDBG",
        "metamdbg_version",
        "Pre-release",
        "[https://github.com/GaetanBenoitDev/metaMDBG](https://github.com/GaetanBenoitDev/metaMDBG)",
    ),
    "metator": (
        "metaTOR",
        "metator_version",
        "Pre-release",
        "[https://github.com/koszullab/metaTOR](https://github.com/koszullab/metaTOR)",
    ),
    "prokka": (
        "Prokka",
        "prokka_version",
        "1.14.5",
        "[https://github.com/tseemann/prokka](https://github.com/tseemann/prokka)",
    ),
}


def _normalised_tool_names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return [
        item.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        for item in values
        if str(item).strip()
    ]


def _metagenome_tool_keys(context: dict[str, Any]) -> set[str]:
    if not context.get("has_metagenome"):
        return set()

    keys = {"checkm", "ete3", "gtdbtk", "matplotlib", "prokka"}
    assembler_aliases = {
        "metamdbg": "metamdbg",
        "flye": "flye",
    }
    binner_aliases = {
        "bin3c": "bin3c",
        "maxbin": "maxbin2",
        "maxbin2": "maxbin2",
        "metabat": "metabat2",
        "metabat2": "metabat2",
        "metator": "metator",
    }
    refiner_aliases = {
        "dastool": "dastool",
        "magscot": "magscot",
    }

    for assembler in _normalised_tool_names(context.get("assembler")):
        if assembler in assembler_aliases:
            keys.add(assembler_aliases[assembler])
    for binner in _normalised_tool_names(context.get("binners")):
        if binner in binner_aliases:
            keys.add(binner_aliases[binner])
    for refiner in _normalised_tool_names(context.get("refiner")):
        if refiner in refiner_aliases:
            keys.add(refiner_aliases[refiner])
    if context.get("use_drep"):
        keys.add("drep")

    return keys


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


def _version_for_metagenome_tool(
    context: dict[str, Any],
    key: str,
    fallback: str | None,
) -> str | None:
    alternate_keys = {
        "dastool_version": ("das_tool_version",),
        "gtdbtk_version": ("gtdb_tk_version",),
    }
    for candidate in (key, *alternate_keys.get(key, ())):
        value = context.get(candidate)
        if value not in (None, ""):
            return str(value)

    if key == "checkm_version":
        checkm_db = str(context.get("checkm_db") or "").strip()
        if checkm_db:
            prefix = "checkm_db release "
            if checkm_db.lower().startswith(prefix):
                return checkm_db[len(prefix) :].strip()
            return checkm_db

    return software_version(context, key, fallback)


def make_table6_rows(context: dict[str, Any]) -> dict[str, Any]:
    table = dict(_make_table5_rows(context))
    table["label"] = "tbl:table6"

    native_body = [list(row) for row in table.get("native_rows", [])]
    seen = {
        names[0]
        for row in native_body
        if row and (names := _normalised_tool_names(row[0]))
    }

    for tool_key in _metagenome_tool_keys(context):
        name, version_key, fallback, source = _METAGENOME_SOFTWARE[tool_key]
        normalised_name = _normalised_tool_names(name)[0]
        if normalised_name in seen:
            continue
        version = _version_for_metagenome_tool(context, version_key, fallback)
        if version is None:
            continue
        native_body.append([name, version, source])
        seen.add(normalised_name)

    native_body.sort(key=lambda row: row[0].casefold())
    headers = ["**Software**", "**Version**", "**Source**"]
    table["rows"] = [",".join(headers)] + [",".join(row) for row in native_body]
    table.update(build_native_table(headers, native_body))
    return table
