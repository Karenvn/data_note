#!/usr/bin/env python


import math
import re
from collections.abc import Iterable, Mapping
from typing import Any


EBP_STANDARD_REFERENCE = "6.C.Q40"
EBP_ULI_REFERENCE = "5.C.Q40"

_REFERENCE_STANDARDS = {
    EBP_STANDARD_REFERENCE: {
        "contig_n50_mb": 1.0,
        "qv": 40.0,
        "percent_assigned_to_chromosomes": 90.0,
        "contig_benchmark_label": "≥ 1 Mb",
    },
    EBP_ULI_REFERENCE: {
        "contig_n50_mb": 0.1,
        "qv": 40.0,
        "percent_assigned_to_chromosomes": 90.0,
        "contig_benchmark_label": "≥ 0.1 Mb",
    },
}


def calc_ebp_metric(context):
    """
    Calculate the EBP metric string based on contig N50, scaffold N50 or % assembled, and QV.
    Returns a string like '6.C.Q40'.
    Assumes N50 values are in megabases.
    """

    metric_input = _metric_input(context)
    if metric_input is None:
        return "?.?.Q?"

    contig_n50 = metric_input["contig_n50"]
    scaffold_n50 = metric_input["scaffold_n50"]
    perc_assembled = metric_input["perc_assembled"]
    qv = metric_input["qv"]

    # First part: log10(contig N50 in bp), rounded down
    contig_n50_float = _as_float(contig_n50)
    if contig_n50_float is None or contig_n50_float <= 0:
        ebp1 = "?"
    else:
        ebp1 = str(int(math.log10(contig_n50_float * 1_000_000)))

    # Second part: 'C' if at least 90% is assigned else log10(scaffold N50 in bp), rounded down
    perc_assembled_float = _as_float(perc_assembled)
    scaffold_n50_float = _as_float(scaffold_n50)
    if perc_assembled_float is not None and perc_assembled_float >= 90:
        ebp2 = "C"
    elif scaffold_n50_float is not None and scaffold_n50_float > 0:
        ebp2 = str(int(math.log10(scaffold_n50_float * 1_000_000)))
    else:
        ebp2 = "?"

    # Third part: QV, rounded down
    qv_float = _as_float(qv)
    if qv_float is None:
        ebp3 = "?"
    else:
        ebp3 = str(int(qv_float))

    return f"{ebp1}.{ebp2}.Q{ebp3}"


def evaluate_ebp_reference_standard(context: Mapping[str, Any]) -> dict[str, Any]:
    """Return template/table context describing whether the EBP standard is met."""
    standard, reason = _resolve_reference_standard(context)
    thresholds = _REFERENCE_STANDARDS[standard]
    metric_input = _metric_input(context)

    failures: list[str] = []
    missing_metrics: list[str] = []

    if metric_input is None:
        missing_metrics.extend(["contig_n50", "percent_assigned_to_chromosomes", "qv"])
    else:
        contig_n50 = _as_float(metric_input["contig_n50"])
        perc_assembled = _as_float(metric_input["perc_assembled"])
        qv = _as_float(metric_input["qv"])

        if contig_n50 is None:
            missing_metrics.append("contig_n50")
        elif contig_n50 < thresholds["contig_n50_mb"]:
            failures.append("contig_n50_below_standard")

        if perc_assembled is None:
            missing_metrics.append("percent_assigned_to_chromosomes")
        elif perc_assembled < thresholds["percent_assigned_to_chromosomes"]:
            failures.append("percent_assigned_to_chromosomes_below_standard")

        if qv is None:
            missing_metrics.append("qv")
        elif qv < thresholds["qv"]:
            failures.append("qv_below_standard")

    if failures:
        met: bool | None = False
        status = "not_met"
    elif missing_metrics:
        met = None
        status = "unknown"
    else:
        met = True
        status = "met"

    return {
        "ebp_reference_standard": standard,
        "ebp_reference_standard_reason": reason,
        "ebp_reference_standard_met": met,
        "ebp_reference_standard_status": status,
        "ebp_reference_standard_failures": failures,
        "ebp_reference_standard_missing_metrics": missing_metrics,
        "ebp_contig_n50_benchmark_mb": thresholds["contig_n50_mb"],
        "ebp_contig_n50_benchmark_label": thresholds["contig_benchmark_label"],
        "ebp_perc_assembled_benchmark": thresholds["percent_assigned_to_chromosomes"],
        "ebp_qv_benchmark": int(thresholds["qv"]),
    }


def _metric_input(context: Mapping[str, Any]) -> dict[str, Any] | None:
    assemblies_type = context.get("assemblies_type")

    if assemblies_type == "hap_asm":
        return {
            "contig_n50": context.get("hap1_contig_N50"),
            "scaffold_n50": context.get("hap1_scaffold_N50"),
            "perc_assembled": context.get("hap1_perc_assembled"),
            "qv": context.get("hap1_QV"),
        }
    if assemblies_type == "prim_alt":
        return {
            "contig_n50": context.get("contig_N50"),
            "scaffold_n50": context.get("scaffold_N50"),
            "perc_assembled": context.get("perc_assembled"),
            "qv": context.get("prim_QV"),
        }
    return None


def _resolve_reference_standard(context: Mapping[str, Any]) -> tuple[str, str]:
    override = _normalise_reference_standard(
        context.get("ebp_reference_standard_override")
        or context.get("ebp_reference_standard")
        or context.get("ebp_standard_override")
    )
    if override is not None:
        return override, "manual_override"

    if _is_truthy(context.get("is_uli")) or _is_truthy(context.get("uli_sample")) or _is_truthy(
        context.get("low_input_material")
    ):
        return EBP_ULI_REFERENCE, "low_input_material"

    if _context_indicates_uli(context):
        return EBP_ULI_REFERENCE, "uli"

    return EBP_STANDARD_REFERENCE, "standard_input"


def _context_indicates_uli(context: Mapping[str, Any]) -> bool:
    candidates: list[Any] = [
        context.get("pacbio_protocols"),
        context.get("pacbio_library_construction_protocol"),
        context.get("pacbio_library_prep"),
    ]
    technology_data = context.get("technology_data")
    if isinstance(technology_data, Mapping):
        candidates.append(technology_data.get("pacbio"))

    return any(_text_indicates_uli(text) for text in _iter_strings(candidates))


def _text_indicates_uli(text: str) -> bool:
    folded = text.casefold()
    return bool(
        "ultra-low" in folded
        or "ultra low" in folded
        or re.search(r"\buli\b", folded)
    )


def _iter_strings(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_strings(nested)
        return
    if isinstance(value, Iterable):
        for nested in value:
            yield from _iter_strings(nested)


def _normalise_reference_standard(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    if cleaned in _REFERENCE_STANDARDS:
        return cleaned
    return None


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("\u202f", "").replace("\xa0", "").strip()
    if not text or text.casefold() == "nan":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None
