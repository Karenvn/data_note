from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


_TECHNOLOGIES: tuple[str, ...] = ("pacbio", "hic", "rna", "isoseq")
_IDENTITY_FIELDS: tuple[str, ...] = (
    "specimen_id",
    "tolid",
    "sample_derived_from",
    "sample_accession",
)


def populate_sampling_template_fields(context: MutableMapping[str, Any]) -> None:
    for tech in _TECHNOLOGIES:
        _populate_display_fields(context, tech)

    _populate_relationship_fields(context)


def _populate_display_fields(context: MutableMapping[str, Any], tech: str) -> None:
    collector = context.get(f"{tech}_collector")
    collector_institute = context.get(f"{tech}_collector_institute")
    identifier = context.get(f"{tech}_identifier")
    identifier_affiliation = context.get(f"{tech}_identifier_affiliation")

    context[f"{tech}_collector_text"] = _format_pipe_text(collector)
    context[f"{tech}_collector_institute_text"] = _format_pipe_text(collector_institute)
    context[f"{tech}_collector_display"] = _format_people_with_affiliations(collector, collector_institute)
    context[f"{tech}_identifier_text"] = _format_pipe_text(identifier)
    context[f"{tech}_identifier_affiliation_text"] = _format_pipe_text(identifier_affiliation)
    context[f"{tech}_identifier_display"] = _format_people_with_affiliations(identifier, identifier_affiliation)
    context[f"{tech}_specimen_label"] = _format_specimen_label(context, tech)

    # Backfill the legacy template typo with a readable value.
    context[f"{tech}_coll_institute"] = context[f"{tech}_collector_institute_text"]


def _populate_relationship_fields(context: MutableMapping[str, Any]) -> None:
    hic_to_pacbio = _relationship(context, "hic", "pacbio")
    rna_to_pacbio = _relationship(context, "rna", "pacbio")
    rna_to_hic = _relationship(context, "rna", "hic")

    context["hic_same_as_pacbio"] = hic_to_pacbio == "same"
    context["hic_differs_from_pacbio"] = hic_to_pacbio == "different"
    context["rna_same_as_pacbio"] = rna_to_pacbio == "same"
    context["rna_differs_from_pacbio"] = rna_to_pacbio == "different"
    context["rna_same_as_hic"] = rna_to_hic == "same"
    context["rna_differs_from_hic"] = rna_to_hic == "different"

    pacbio_label = _clean_string(context.get("pacbio_specimen_label"))
    hic_label = _clean_string(context.get("hic_specimen_label"))
    rna_label = _clean_string(context.get("rna_specimen_label"))

    context["pacbio_specimen_reference"] = _with_label("the specimen used for genome sequencing", pacbio_label)

    if context["hic_same_as_pacbio"]:
        hic_base = "the specimen used for genome sequencing"
        hic_reference_label = hic_label or pacbio_label
    else:
        hic_base = "the Hi-C specimen"
        hic_reference_label = hic_label
    context["hic_specimen_reference"] = _with_label(hic_base, hic_reference_label)

    if context["rna_same_as_pacbio"]:
        rna_base = "the specimen used for genome sequencing"
        rna_reference_label = rna_label or pacbio_label
    elif context["rna_same_as_hic"]:
        rna_base = "the same specimen used for Hi-C sequencing"
        rna_reference_label = rna_label or hic_label
    else:
        rna_base = "the RNA specimen"
        rna_reference_label = rna_label
    context["rna_specimen_reference"] = _with_label(rna_base, rna_reference_label)

    isoseq_label = _clean_string(context.get("isoseq_specimen_label"))
    context["isoseq_specimen_reference"] = _with_label("the Iso-Seq specimen", isoseq_label)


def _relationship(context: MutableMapping[str, Any], left: str, right: str) -> str:
    shared_match = False
    shared_conflict = False

    for field_name in _IDENTITY_FIELDS:
        left_value = _clean_string(context.get(f"{left}_{field_name}"))
        right_value = _clean_string(context.get(f"{right}_{field_name}"))
        if not left_value or not right_value:
            continue
        if left_value.casefold() == right_value.casefold():
            shared_match = True
        else:
            shared_conflict = True

    if shared_match:
        return "same"
    if shared_conflict:
        return "different"
    return "unknown"


def _format_specimen_label(context: MutableMapping[str, Any], tech: str) -> str:
    parts: list[str] = []
    specimen_id = _clean_string(context.get(f"{tech}_specimen_id"))
    tolid = _clean_string(context.get(f"{tech}_tolid"))
    sample_accession = _clean_string(context.get(f"{tech}_sample_accession"))
    source_individual = _clean_string(context.get(f"{tech}_sample_derived_from"))

    if specimen_id:
        parts.append(f"specimen ID {specimen_id}")
    if tolid:
        parts.append(f"ToLID {tolid}")
    if not parts and sample_accession:
        parts.append(f"BioSample {sample_accession}")
    if not parts and source_individual:
        parts.append(f"source individual BioSample {source_individual}")
    return ", ".join(parts)


def _format_people_with_affiliations(names: Any, affiliations: Any) -> str:
    people = _split_pipe_values(names)
    institutes = _split_pipe_values(affiliations)

    if not people:
        return ""
    if not institutes:
        return _natural_join(people)
    if len(institutes) == 1:
        return f"{_natural_join(people)} ({institutes[0]})"
    if len(people) == len(institutes):
        paired = [
            f"{person} ({institute})" if institute else person
            for person, institute in zip(people, institutes)
        ]
        return _natural_join(paired)
    return f"{_natural_join(people)} ({_natural_join(institutes)})"


def _format_pipe_text(value: Any) -> str:
    return _natural_join(_split_pipe_values(value))


def _split_pipe_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []

    seen: set[str] = set()
    values: list[str] = []
    for raw_part in str(value).split("|"):
        cleaned = raw_part.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(cleaned)
    return values


def _natural_join(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _with_label(base: str, label: str) -> str:
    if not label:
        return base
    return f"{base} ({label})"


def _clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""
