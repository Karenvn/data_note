from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


def _assets_root() -> Path:
    return Path(
        os.getenv("DATA_NOTE_GN_ASSETS")
        or os.getenv("DATA_NOTE_SERVER_DATA")
        or Path.home() / "gn_assets"
    ).expanduser()


class _Cols:
    def __init__(self, df: pd.DataFrame) -> None:
        self.by_lower = {str(col).lower(): col for col in df.columns}

    def get(self, *names: str) -> str | None:
        for name in names:
            found = self.by_lower.get(name.lower())
            if found is not None:
                return found
        return None


def _resolve_columns(df: pd.DataFrame) -> dict[str, str | None]:
    cols = _Cols(df)
    return {
        "assembler": cols.get("assembler"),
        "binner": cols.get("binning_program", "binner", "binning"),
        "refiner": cols.get("refining_program", "bin_refinement", "refiner"),
        "bin_id": cols.get("bin_id", "bin", "bin_name"),
        "quality": cols.get("quality", "bin_type"),
        "size": cols.get("size", "length", "span", "length_bp", "total_length"),
        "contigs": cols.get("contigs", "n_contigs", "num_contigs"),
        "circular": cols.get("circular", "is_circular", "circularised", "circularized"),
        "mean_coverage": cols.get("mean_coverage", "coverage", "avg_coverage"),
        "bin_type": cols.get("bin_type", "bin classification", "bintype"),
        "trna_unique": cols.get("unique_trnas", "n_unique_trna", "trna_unique"),
        "rrna_5s": cols.get("rrna_5s", "5s_rrna", "has_5s"),
        "rrna_16s": cols.get("rrna_16s", "16s_rrna", "has_16s"),
        "rrna_23s": cols.get("rrna_23s", "23s_rrna", "has_23s"),
        "completeness": cols.get("completeness", "checkm_completeness"),
        "contamination": cols.get("contamination", "checkm_contamination"),
        "taxonomy": cols.get("ncbi_classification", "classification", "gtdb_taxonomy", "gtdbtk_taxonomy"),
        "gtdb_taxonomy": cols.get("classification", "gtdb_taxonomy", "gtdbtk_taxonomy"),
        "ncbi_taxon": cols.get("ncbi_taxon", "taxon"),
        "taxid": cols.get("taxon_id", "taxid"),
        "drep": cols.get("drep", "drep_cluster"),
        "checkm_version": cols.get("checkm_version"),
        "checkm_db": cols.get("checkm_db", "checkm_database"),
        "gtdbtk_version": cols.get("gtdbtk_version"),
        "gtdb_release": cols.get("gtdb_release", "gtdb_version"),
    }


def _first(df: pd.DataFrame, col: str | None) -> str | None:
    if not col or not df[col].notna().any():
        return None
    return str(df[col].dropna().iloc[0])


def _norm_assembler(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered in {"meta-mdbg", "metamdbg", "meta_mdbg"}:
        return "metamdbg"
    return lowered


def _norm_binner(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    for known in ("metabat2", "maxbin2", "concoct", "vamb", "semibin", "bin3c"):
        if known in lowered:
            return known
    if "magscot" in lowered or "dastool" in lowered:
        return None
    parts = re.split(r"[^a-z0-9+._-]+", lowered)
    return parts[0] if parts and parts[0] else None


def _norm_refiner(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if "magscot" in lowered:
        return "magscot"
    if "dastool" in lowered or "das tool" in lowered:
        return "dastool"
    return lowered


def _extract_rank(taxonomy: Any, rank_prefix: str) -> str | None:
    if taxonomy is None or (isinstance(taxonomy, float) and math.isnan(taxonomy)):
        return None
    match = re.search(rf"{rank_prefix}__([A-Za-z0-9_.\- ]+)", str(taxonomy))
    return match.group(1) if match else None


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def _as_int(value: Any) -> int | None:
    try:
        if pd.isna(value):
            return None
        return int(float(value))
    except Exception:
        return None


def _is_true(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "circular"}
    try:
        return float(value) >= 1.0
    except Exception:
        return False


def _has_rrna_operon(row: pd.Series, cols: dict[str, str | None]) -> bool | None:
    checks: list[bool] = []
    for key in ("rrna_5s", "rrna_16s", "rrna_23s"):
        col = cols[key]
        if not col:
            return None
        checks.append(str(row[col]).strip().upper() == "Y")
    return all(checks)


def _is_fully_circular(row: pd.Series, cols: dict[str, str | None]) -> bool:
    contigs_col = cols["contigs"]
    circular_col = cols["circular"]
    if contigs_col and circular_col:
        contigs = _as_float(row[contigs_col])
        circular = _as_float(row[circular_col])
        return (contigs == 1 and circular == 1) or (contigs > 1 and contigs == circular)
    if circular_col:
        return _is_true(row[circular_col])
    return False


def _is_mag(row: pd.Series, cols: dict[str, str | None]) -> bool:
    bin_type_col = cols.get("bin_type")
    if bin_type_col:
        bin_type = str(row[bin_type_col]).strip().lower()
        if bin_type:
            return "mag" in bin_type

    completeness_col = cols["completeness"]
    contamination_col = cols["contamination"]
    if not completeness_col or not contamination_col:
        return False

    completeness = _as_float(row[completeness_col])
    contamination = _as_float(row[contamination_col])
    if math.isnan(completeness) or math.isnan(contamination) or contamination > 5:
        return False

    rrna_ok = _has_rrna_operon(row, cols)
    if rrna_ok is False:
        return False

    trna_col = cols["trna_unique"]
    if trna_col:
        trnas = _as_int(row[trna_col])
        if trnas is not None and trnas < 18:
            return False

    return completeness >= 90.0 or (completeness >= 50.0 and _is_fully_circular(row, cols))


def _finite_or_none(value: float) -> float | None:
    return round(value, 6) if math.isfinite(value) else None


def _format_number(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        number = float(value)
    except Exception:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.{digits}f}"


def _build_table_rows(df: pd.DataFrame, cols: dict[str, str | None]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        taxon = row[cols["ncbi_taxon"]] if cols["ncbi_taxon"] else ""
        if not taxon and cols["taxonomy"]:
            taxon = _extract_rank(row[cols["taxonomy"]], "s") or _extract_rank(row[cols["taxonomy"]], "g") or ""

        rows.append(
            {
                "NCBI taxon": str(taxon) if not pd.isna(taxon) else "",
                "Taxid": str(row[cols["taxid"]]) if cols["taxid"] and not pd.isna(row[cols["taxid"]]) else "",
                "GTDB taxonomy": (
                    _extract_rank(row[cols["gtdb_taxonomy"]], "c")
                    if cols["gtdb_taxonomy"]
                    else ""
                )
                or "",
                "Quality": str(row[cols["quality"]]) if cols["quality"] and not pd.isna(row[cols["quality"]]) else "",
                "Size (bp)": _format_number(row[cols["size"]], digits=0) if cols["size"] else "",
                "Contigs": _format_number(row[cols["contigs"]], digits=0) if cols["contigs"] else "",
                "Circular": "Yes" if _is_fully_circular(row, cols) else "No",
                "Mean coverage": _format_number(row[cols["mean_coverage"]]) if cols["mean_coverage"] else "",
                "Completeness (%)": _format_number(row[cols["completeness"]]) if cols["completeness"] else "",
                "Contamination (%)": _format_number(row[cols["contamination"]]) if cols["contamination"] else "",
            }
        )
    return rows


@dataclass(slots=True)
class MetagenomeService:
    assets_root: Path | None = None

    def build_context(self, tolid: str | None) -> dict[str, Any]:
        if not tolid:
            return {}

        csv_path = self.find_csv(tolid)
        if not csv_path:
            return {
                "has_metagenome": False,
                "metagenome_context_missing": True,
            }

        df = pd.read_csv(csv_path)
        cols = _resolve_columns(df)
        df["is_MAG"] = df.apply(lambda row: _is_mag(row, cols), axis=1)
        df["is_fully_circular"] = df.apply(lambda row: _is_fully_circular(row, cols), axis=1)

        taxonomy_col = cols["taxonomy"]
        if taxonomy_col:
            df["domain"] = df[taxonomy_col].apply(lambda value: _extract_rank(value, "d"))
            df["phylum"] = df[taxonomy_col].apply(lambda value: _extract_rank(value, "p"))
            has_archaea = bool((df["domain"] == "Archaea").any())
            num_phyla = int(df["phylum"].nunique(dropna=True))
        else:
            has_archaea = False
            num_phyla = 0

        sizes = pd.to_numeric(df[cols["size"]], errors="coerce") / 1e6 if cols["size"] else pd.Series(dtype=float)
        completeness = pd.to_numeric(df[cols["completeness"]], errors="coerce") if cols["completeness"] else pd.Series(dtype=float)
        contamination = pd.to_numeric(df[cols["contamination"]], errors="coerce") if cols["contamination"] else pd.Series(dtype=float)

        binners_raw = df[cols["binner"]].dropna().astype(str).tolist() if cols["binner"] else []
        binners = sorted({binner for binner in (_norm_binner(value) for value in binners_raw) if binner})
        table_headers = [
            "NCBI taxon",
            "Taxid",
            "GTDB taxonomy",
            "Quality",
            "Size (bp)",
            "Contigs",
            "Circular",
            "Mean coverage",
            "Completeness (%)",
            "Contamination (%)",
        ]

        context: dict[str, Any] = {
            "has_metagenome": True,
            "metagenome_csv_path": str(csv_path),
            "assembler": _norm_assembler(_first(df, cols["assembler"])),
            "binners": binners,
            "multiple_binners": len(binners) >= 2,
            "refiner": _norm_refiner(_first(df, cols["refiner"])),
            "checkm_version": _first(df, cols["checkm_version"]),
            "checkm_db": _first(df, cols["checkm_db"]),
            "gtdbtk_version": _first(df, cols["gtdbtk_version"]),
            "gtdb_release": _first(df, cols["gtdb_release"]),
            "use_drep": bool(cols["drep"]),
            "drep_threshold": None,
            "filter_domains": False,
            "mag_contamination": 5,
            "min_trnas": 18,
            "high_completeness": 90,
            "medium_completeness": 50,
            "min_bin_completeness": 50,
            "max_bin_contamination": 10,
            "total_bins": int(len(df)),
            "num_mags": int(df["is_MAG"].sum()),
            "num_circular_mags": int((df["is_MAG"] & df["is_fully_circular"]).sum()),
            "num_phyla": num_phyla,
            "has_archaea": has_archaea,
            "min_size_mbp": _finite_or_none(float(sizes.min(skipna=True))) if not sizes.empty else None,
            "max_size_mbp": _finite_or_none(float(sizes.max(skipna=True))) if not sizes.empty else None,
            "mean_size_mbp": _finite_or_none(float(sizes.mean(skipna=True))) if not sizes.empty else None,
            "std_size_mbp": _finite_or_none(float(sizes.std(skipna=True, ddof=0))) if not sizes.empty else None,
            "mean_completeness": _finite_or_none(float(completeness.mean(skipna=True))) if not completeness.empty else None,
            "std_completeness": _finite_or_none(float(completeness.std(skipna=True, ddof=0))) if not completeness.empty else None,
            "mean_contamination": _finite_or_none(float(contamination.mean(skipna=True))) if not contamination.empty else None,
            "std_contamination": _finite_or_none(float(contamination.std(skipna=True, ddof=0))) if not contamination.empty else None,
            "visualization_method": "custom",
            "metagenome_table_headers": table_headers,
            "metagenome_table_keys": table_headers,
            "metagenome_table_rows": _build_table_rows(df, cols),
            "metagenome_table_caption": "Quality metrics and taxonomic assignments of the binned metagenomes",
            "metagenome_table_alignment": "L" * len(table_headers),
        }
        context.update(self._prebuilt_context(tolid))
        context["has_metagenome"] = True
        return context

    def find_csv(self, tolid: str) -> Path | None:
        root = self.assets_root or _assets_root()
        candidates = [
            root / "metagenomes" / tolid / "bin_data.csv",
            root / "metagenome" / tolid / "bin_data.csv",
        ]
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    def _prebuilt_context(self, tolid: str) -> dict[str, Any]:
        root = self.assets_root or _assets_root()
        context_path = root / "metagenome_figs" / tolid / "metagenome_context.json"
        if not context_path.is_file():
            return {}
        try:
            loaded = json.loads(context_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}
