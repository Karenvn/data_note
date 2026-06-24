#!/usr/bin/env python

import re


def safe_convert(value, to_type, default):
    try:
        return to_type(value)
    except (ValueError, TypeError):
        return default


def clean_numeric_string(value):
    if not value:
        return "0"
    return "".join(c for c in str(value) if c.isdigit() or c == ".")


def format_kb(val):
    try:
        return f"{round(float(val) / 1000, 1)}"
    except (TypeError, ValueError):
        return ""


def format_sex_chromosomes(sex_chromosomes):
    if not sex_chromosomes:
        return None
    if len(sex_chromosomes) == 1:
        return sex_chromosomes[0]
    if len(sex_chromosomes) == 2:
        return f"{sex_chromosomes[0]} and {sex_chromosomes[1]}"
    return ", ".join(sex_chromosomes[:-1]) + f", and {sex_chromosomes[-1]}"


def format_assigned_chromosomes_phrase(
    sex_chromosomes=None,
    supernumerary_chromosomes=None,
):
    phrases = []
    sex_phrase = _format_chromosome_kind_phrase(sex_chromosomes, "sex")
    supernumerary_phrase = _format_chromosome_kind_phrase(supernumerary_chromosomes, "supernumerary")
    if sex_phrase:
        phrases.append(sex_phrase)
    if supernumerary_phrase:
        phrases.append(supernumerary_phrase)
    return " and ".join(phrases) if phrases else None


def populate_assigned_chromosome_phrases(context):
    if not context.get("assigned_chromosomes_phrase"):
        context["assigned_chromosomes_phrase"] = format_assigned_chromosomes_phrase(
            context.get("sex_chromosomes"),
            context.get("supernumerary_chromosomes"),
        )
    if not context.get("hap1_assigned_chromosomes_phrase"):
        context["hap1_assigned_chromosomes_phrase"] = format_assigned_chromosomes_phrase(
            context.get("hap1_sex_chromosomes"),
            context.get("hap1_supernumerary_chromosomes"),
        )
    if not context.get("hap2_assigned_chromosomes_phrase"):
        context["hap2_assigned_chromosomes_phrase"] = format_assigned_chromosomes_phrase(
            context.get("hap2_sex_chromosomes"),
            context.get("hap2_supernumerary_chromosomes"),
        )
    if not context.get("all_assigned_chromosomes_phrase"):
        context["all_assigned_chromosomes_phrase"] = format_assigned_chromosomes_phrase(
            context.get("all_sex_chromosomes"),
            context.get("all_supernumerary_chromosomes"),
        )
    return context


def _format_chromosome_kind_phrase(chromosomes, chromosome_kind):
    labels = _split_chromosome_labels(chromosomes)
    if not labels:
        return None
    label_text = format_sex_chromosomes(labels)
    plural = "" if len(labels) == 1 else "s"
    return f"the {label_text} {chromosome_kind} chromosome{plural}"


def _split_chromosome_labels(chromosomes):
    if not chromosomes:
        return []
    if isinstance(chromosomes, (list, tuple, set)):
        labels = []
        for chromosome in chromosomes:
            labels.extend(_split_chromosome_labels(chromosome))
        return _dedupe_chromosome_labels(labels)

    parts = re.split(r",|;|\band\b", str(chromosomes), flags=re.IGNORECASE)
    return _dedupe_chromosome_labels(part.strip() for part in parts)


def _dedupe_chromosome_labels(labels):
    deduped = []
    seen = set()
    for label in labels:
        normalized = str(label).strip()
        if not normalized:
            continue
        key = normalized.upper()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def format_scientific(value):
    return "{:.2e}".format(value)


def format_with_comma(value, as_int=False):
    if value is None:
        return None

    try:
        if as_int:
            return f"{int(value):,}"
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_with_nbsp(value, as_int=False, digits=2):
    if value is None:
        return ""

    try:
        if as_int:
            return f"{int(value):,}".replace(",", "\u202f")
        return f"{float(value):,.{digits}f}".replace(",", "\u202f")
    except (TypeError, ValueError):
        return str(value)


def bytes_to_gb(bytes_str):
    try:
        bytes_int = int(bytes_str)
        return round(bytes_int / (1024**3), 2)
    except ValueError:
        return 0


def in_mb(length):
    return format_length(length, 6)


def in_gb(length):
    return format_length(length, 9)


def format_length(length, power_of_ten):
    return "{:.2f}".format(int(length) / 10**power_of_ten)


def percentage_change_from_a_to_b(a, b):
    if a == 0:
        return 0.0
    return round(((b - a) / a) * 100.0, 2)


def round_gc_percent(gc_percent):
    return round(gc_percent * 2) / 2


def round_coordinates(value):
    return round(value, 2)
