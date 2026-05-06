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
    _set_short_specimen_reference_fields(
        context,
        tech,
        _format_specimen_short_label(context, tech),
    )
    context[f"{tech}_coll_lat_display"] = _format_coordinate(context.get(f"{tech}_coll_lat"))
    context[f"{tech}_coll_long_display"] = _format_coordinate(context.get(f"{tech}_coll_long"))

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
    context["hic_collection_same_as_pacbio"] = _same_collection_event(context, "hic", "pacbio")
    context["rna_collection_same_as_pacbio"] = _same_collection_event(context, "rna", "pacbio")
    context["rna_collection_same_as_hic"] = _same_collection_event(context, "rna", "hic")

    pacbio_label = _clean_string(context.get("pacbio_specimen_label"))
    hic_label = _clean_string(context.get("hic_specimen_label"))
    rna_label = _clean_string(context.get("rna_specimen_label"))

    context["pacbio_specimen_reference"] = _with_label("the specimen used for genome sequencing", pacbio_label)
    _set_short_specimen_reference_fields(
        context,
        "pacbio",
        _clean_string(context.get("pacbio_specimen_short_label")),
    )

    if context["hic_same_as_pacbio"]:
        hic_base = "the specimen used for genome sequencing"
        hic_reference_label = hic_label or pacbio_label
        hic_short_label = _preferred_short_label(context, "hic", fallback_tech="pacbio")
    else:
        hic_base = "the Hi-C specimen"
        hic_reference_label = hic_label
        hic_short_label = _preferred_short_label(context, "hic")
    context["hic_specimen_reference"] = _with_label(hic_base, hic_reference_label)
    _set_short_specimen_reference_fields(context, "hic", hic_short_label)

    if context["rna_same_as_pacbio"]:
        rna_base = "the specimen used for genome sequencing"
        rna_reference_label = rna_label or pacbio_label
        rna_short_label = _preferred_short_label(context, "rna", fallback_tech="pacbio")
    elif context["rna_same_as_hic"]:
        rna_base = "the same specimen used for Hi-C sequencing"
        rna_reference_label = rna_label or hic_label
        rna_short_label = _preferred_short_label(context, "rna", fallback_tech="hic")
    else:
        rna_base = "the RNA specimen"
        rna_reference_label = rna_label
        rna_short_label = _preferred_short_label(context, "rna")
    context["rna_specimen_reference"] = _with_label(rna_base, rna_reference_label)
    _set_short_specimen_reference_fields(context, "rna", rna_short_label)

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


def _format_specimen_short_label(context: MutableMapping[str, Any], tech: str) -> str:
    tolid = _clean_string(context.get(f"{tech}_tolid"))
    specimen_id = _clean_string(context.get(f"{tech}_specimen_id"))
    source_individual = _clean_string(context.get(f"{tech}_sample_derived_from"))
    sample_accession = _clean_string(context.get(f"{tech}_sample_accession"))

    if tolid:
        return f"{tolid} specimen"
    if specimen_id:
        return f"specimen {specimen_id}"
    if source_individual:
        return f"source individual BioSample {source_individual}"
    if sample_accession:
        return f"BioSample {sample_accession}"
    return ""


def _preferred_short_label(
    context: MutableMapping[str, Any],
    tech: str,
    *,
    fallback_tech: str | None = None,
) -> str:
    if _clean_string(context.get(f"{tech}_tolid")) or _clean_string(context.get(f"{tech}_specimen_id")):
        return _clean_string(context.get(f"{tech}_specimen_short_label"))

    if fallback_tech:
        fallback_label = _clean_string(context.get(f"{fallback_tech}_specimen_short_label"))
        if fallback_label:
            return fallback_label

    return _clean_string(context.get(f"{tech}_specimen_short_label"))


def _set_short_specimen_reference_fields(
    context: MutableMapping[str, Any],
    tech: str,
    label: str,
) -> None:
    short_label = _clean_string(label)
    short_reference = f"the {short_label}" if short_label else "the specimen"
    context[f"{tech}_specimen_short_label"] = short_label
    context[f"{tech}_specimen_short_reference"] = short_reference
    context[f"{tech}_specimen_short_sentence_reference"] = _sentence_start(short_reference)


def _same_collection_event(context: MutableMapping[str, Any], left: str, right: str) -> bool:
    left_date = _clean_string(context.get(f"{left}_coll_date"))
    right_date = _clean_string(context.get(f"{right}_coll_date"))
    if not left_date or not right_date or left_date != right_date:
        return False

    return _same_collection_location(context, left, right)


def _same_collection_location(context: MutableMapping[str, Any], left: str, right: str) -> bool:
    left_lat = _clean_string(context.get(f"{left}_coll_lat"))
    left_long = _clean_string(context.get(f"{left}_coll_long"))
    right_lat = _clean_string(context.get(f"{right}_coll_lat"))
    right_long = _clean_string(context.get(f"{right}_coll_long"))

    if left_lat and left_long and right_lat and right_long:
        return _same_coordinate(left_lat, right_lat) and _same_coordinate(left_long, right_long)

    left_location = _clean_string(context.get(f"{left}_coll_location"))
    right_location = _clean_string(context.get(f"{right}_coll_location"))
    return bool(left_location and right_location and left_location.casefold() == right_location.casefold())


def _same_coordinate(left: str, right: str) -> bool:
    try:
        return float(left.replace("\u2212", "-")) == float(right.replace("\u2212", "-"))
    except ValueError:
        return _normalise_coordinate_text(left) == _normalise_coordinate_text(right)


def _format_coordinate(value: Any) -> str:
    text = _clean_string(value)
    if text.startswith("--"):
        return "\u2212" + text[2:]
    if text.startswith("-"):
        return "\u2212" + text[1:]
    return text


def _normalise_coordinate_text(value: str) -> str:
    text = _clean_string(value)
    if text.startswith("--"):
        text = "-" + text[2:]
    if text.startswith("\u2212"):
        text = "-" + text[1:]
    return text


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


def _sentence_start(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _clean_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""
