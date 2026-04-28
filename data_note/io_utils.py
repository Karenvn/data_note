#!/usr/bin/env python

import json
from pathlib import Path
import re

import pandas as pd


BIOPROJECT_ACCESSION_PATTERN = re.compile(r"^PRJ[A-Z]{2}\d+$")


def dict_to_csv(data_dict, csv_filename):
    df = pd.DataFrame(data_dict.items(), columns=["key", "value"])
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")


def _apply_context_overrides(context_dict, corrections):
    overrides = corrections.get("context_overrides", {})
    if not isinstance(overrides, dict):
        return

    global_overrides = overrides.get("all")
    if isinstance(global_overrides, dict):
        context_dict.update(global_overrides)

    for scope in ("bioproject", "tolid", "species"):
        scoped_overrides = overrides.get(scope, {})
        if not isinstance(scoped_overrides, dict):
            continue
        scope_value = context_dict.get(scope)
        if scope_value in (None, ""):
            continue
        matched_override = scoped_overrides.get(scope_value)
        if isinstance(matched_override, dict):
            context_dict.update(matched_override)


def load_and_apply_corrections(context_dict, corrections_file):
    with open(corrections_file, "r") as file:
        corrections = json.load(file)

    specific_replacements = corrections.get("specific_replacements", {})
    for key, replacements in specific_replacements.items():
        if key in context_dict and context_dict[key] in replacements:
            context_dict[key] = replacements[context_dict[key]]

    generic_replacements = corrections.get("generic_replacements", {})
    for key, value in context_dict.items():
        if isinstance(value, str):
            for wrong, right in generic_replacements.items():
                if wrong in value:
                    value = value.replace(wrong, right)
            context_dict[key] = value

    _apply_context_overrides(context_dict, corrections)

    return context_dict


def read_bioprojects_from_file(file_path):
    with open(file_path, "r") as file:
        return [line.strip() for line in file.readlines()]


def read_bioprojects_input(input_value: str) -> list[str]:
    candidate = input_value.strip()
    path = Path(candidate).expanduser()
    if path.is_file():
        return read_bioprojects_from_file(str(path))
    if BIOPROJECT_ACCESSION_PATTERN.match(candidate):
        return [candidate]
    raise FileNotFoundError(
        f"BioProject input {input_value!r} is neither an existing file nor a BioProject accession"
    )
