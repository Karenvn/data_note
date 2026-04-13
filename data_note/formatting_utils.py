#!/usr/bin/env python


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
