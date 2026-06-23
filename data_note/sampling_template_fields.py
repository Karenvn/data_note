from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


_TECHNOLOGIES: tuple[str, ...] = ("pacbio", "hic", "rna", "isoseq")
_SAMPLING_PARAGRAPH_TECHNOLOGIES: tuple[str, ...] = ("pacbio", "hic", "rna")
_IDENTITY_FIELDS: tuple[str, ...] = (
    "specimen_id",
    "tolid",
    "sample_derived_from",
    "sample_accession",
)
_TECHNOLOGY_USE_LABELS = {
    "pacbio": "genome sequencing",
    "hic": "Hi-C sequencing",
    "rna": "RNA sequencing",
    "isoseq": "Iso-Seq sequencing",
}
_TECHNOLOGY_SPECIMEN_LABELS = {
    "pacbio": "genome-sequencing",
    "hic": "Hi-C",
    "rna": "RNA",
    "isoseq": "Iso-Seq",
}
_MISSING_ORGANISM_PARTS = {
    "na",
    "n/a",
    "not applicable",
    "not collected",
    "not provided",
    "unknown",
}
_MISSING_TEXT_VALUES = _MISSING_ORGANISM_PARTS | {
    "missing",
    "none",
    "null",
}


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
    context[f"{tech}_tissue_phrase"] = _format_tissue_phrase(context.get(f"{tech}_organism_part"))
    _set_short_specimen_reference_fields(
        context,
        tech,
        _format_specimen_short_label(context, tech),
    )
    _set_coordinate_display_fields(context, tech, "coll_lat")
    _set_coordinate_display_fields(context, tech, "coll_long")

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
    context["sampling_specimen_paragraph"] = _format_sampling_specimen_paragraph(context)


def _format_sampling_specimen_paragraph(context: MutableMapping[str, Any]) -> str:
    groups = _build_specimen_groups(context)
    if not groups:
        return ""
    if len(groups) == 1:
        return _format_single_specimen_paragraph(context, groups[0])
    return _format_multiple_specimen_paragraph(context, groups)


def _build_specimen_groups(context: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for tech in _SAMPLING_PARAGRAPH_TECHNOLOGIES:
        if not _has_specimen_context(context, tech):
            continue

        for group in groups:
            if _relationship(context, tech, group["representative"]) == "same":
                group["technologies"].append(tech)
                break
        else:
            groups.append({"representative": tech, "technologies": [tech]})

    return groups


def _has_specimen_context(context: MutableMapping[str, Any], tech: str) -> bool:
    if tech == "pacbio" and _metadata_text(context.get("species")):
        return True
    return any(
        _metadata_text(context.get(f"{tech}_{field_name}"))
        for field_name in _IDENTITY_FIELDS
    )


def _format_single_specimen_paragraph(context: MutableMapping[str, Any], group: dict[str, Any]) -> str:
    techs = group["technologies"]
    representative = group["representative"]
    label = _format_parenthetical_specimen_label(
        context,
        representative,
        include_figure="pacbio" in techs,
    )
    specimen_description = _format_singular_specimen_description(context, representative)

    if "pacbio" in techs:
        sentences = [f"The specimen used for genome sequencing was {specimen_description}{label}."]
        additional_techs = [tech for tech in techs if tech != "pacbio"]
        if additional_techs:
            sentences.append(
                f"The same specimen was also used for {_format_technology_use_phrase(additional_techs)}."
            )
    else:
        sentences = [
            f"The {_format_group_specimen_noun(techs)} was {specimen_description}{label}."
        ]

    collection_sentence = _format_collection_sentence(
        context,
        representative,
        subject="It",
        be_verb="was",
        object_pronoun="it",
    )
    if collection_sentence:
        sentences.append(collection_sentence)
    return " ".join(sentences)


def _format_multiple_specimen_paragraph(
    context: MutableMapping[str, Any],
    groups: list[dict[str, Any]],
) -> str:
    count_word = _count_word(len(groups))
    specimen_description = _format_plural_specimen_description(context, groups)
    specimen_items = [
        _format_specimen_group_item(context, group)
        for group in groups
    ]
    sentences = [
        f"{_sentence_start(count_word)} {specimen_description} were used: {_natural_join(specimen_items)}."
    ]

    if _groups_share_collection_sentence(context, groups):
        collection_sentence = _format_collection_sentence(
            context,
            groups[0]["representative"],
            subject=f"All {count_word}",
            be_verb="were",
            object_pronoun="them",
        )
        if collection_sentence:
            sentences.append(collection_sentence)
    else:
        for group in groups:
            collection_sentence = _format_collection_sentence(
                context,
                group["representative"],
                subject=_sentence_start(f"the {_format_group_specimen_noun(group['technologies'])}"),
                be_verb="was",
                object_pronoun="it",
            )
            if collection_sentence:
                sentences.append(collection_sentence)

    return " ".join(sentences)


def _format_specimen_group_item(context: MutableMapping[str, Any], group: dict[str, Any]) -> str:
    techs = group["technologies"]
    label = _format_parenthetical_specimen_label(
        context,
        group["representative"],
        include_figure="pacbio" in techs,
    )
    return f"the {_format_group_specimen_noun(techs)}{label}"


def _format_singular_specimen_description(context: MutableMapping[str, Any], tech: str) -> str:
    parts = [
        _metadata_text(context.get(f"{tech}_lifestage")),
        _metadata_text(context.get(f"{tech}_sex")) or _metadata_text(context.get("observed_sex")),
    ]
    descriptor = " ".join(part for part in parts if part)
    species = _format_species(context)
    noun_phrase = " ".join(part for part in (descriptor, species) if part)
    if not noun_phrase:
        noun_phrase = "specimen"
    return f"{_indefinite_article(noun_phrase)} {noun_phrase}"


def _format_plural_specimen_description(
    context: MutableMapping[str, Any],
    groups: list[dict[str, Any]],
) -> str:
    lifestage = _common_group_field(context, groups, "lifestage")
    sex = _common_group_field(context, groups, "sex", fallback_key="observed_sex")
    descriptor = " ".join(part for part in (lifestage, sex) if part)
    species = _format_species(context)
    return " ".join(part for part in (descriptor, species, "specimens") if part)


def _common_group_field(
    context: MutableMapping[str, Any],
    groups: list[dict[str, Any]],
    field_name: str,
    *,
    fallback_key: str | None = None,
) -> str:
    values: list[str] = []
    for group in groups:
        representative = group["representative"]
        value = _metadata_text(context.get(f"{representative}_{field_name}"))
        if not value and fallback_key:
            value = _metadata_text(context.get(fallback_key))
        values.append(value)

    present_values = [value for value in values if value]
    if len(present_values) != len(values):
        return ""
    first = present_values[0]
    if all(value.casefold() == first.casefold() for value in present_values):
        return first
    return ""


def _format_species(context: MutableMapping[str, Any]) -> str:
    species = _metadata_text(context.get("species"))
    if not species:
        return ""
    if species.startswith("*") and species.endswith("*"):
        return species
    return f"*{species}*"


def _format_parenthetical_specimen_label(
    context: MutableMapping[str, Any],
    tech: str,
    *,
    include_figure: bool,
) -> str:
    parts = []
    label = _metadata_text(context.get(f"{tech}_specimen_label"))
    if label:
        parts.append(label)
    if include_figure:
        parts.append("Figure [-@fig:Fig_1]")
    if not parts:
        return ""
    return f" ({'; '.join(parts)})"


def _format_group_specimen_noun(techs: list[str]) -> str:
    labels = [
        _TECHNOLOGY_SPECIMEN_LABELS[tech]
        for tech in techs
        if tech in _TECHNOLOGY_SPECIMEN_LABELS
    ]
    if not labels:
        return "specimen"
    return f"{_natural_join(labels)} specimen"


def _format_technology_use_phrase(techs: list[str]) -> str:
    labels = [
        _TECHNOLOGY_USE_LABELS[tech]
        for tech in techs
        if tech in _TECHNOLOGY_USE_LABELS
    ]
    return _natural_join(labels)


def _format_collection_sentence(
    context: MutableMapping[str, Any],
    tech: str,
    *,
    subject: str,
    be_verb: str,
    object_pronoun: str,
) -> str:
    collection_phrase = _format_collection_phrase(context, tech)
    collector = _metadata_text(context.get(f"{tech}_collector_display"))
    identifier = _metadata_text(context.get(f"{tech}_identifier_display"))
    preserv_method = _metadata_text(context.get(f"{tech}_preserv_method"))

    if collection_phrase:
        sentence = f"{subject} {be_verb} collected {collection_phrase}"
        if collector:
            sentence += f" by {collector}"
        if identifier:
            if collector and collector.casefold() == identifier.casefold():
                sentence += f", who also identified {object_pronoun}"
            else:
                sentence += f" and identified by {identifier}"
        if preserv_method:
            sentence += f" and preserved {preserv_method}"
        return f"{sentence}."

    actions: list[str] = []
    if collector and identifier and collector.casefold() == identifier.casefold():
        actions.append(f"collected and identified by {collector}")
    else:
        if collector:
            actions.append(f"collected by {collector}")
        if identifier:
            actions.append(f"identified by {identifier}")
    if preserv_method:
        actions.append(f"preserved {preserv_method}")

    if not actions:
        return ""
    return f"{subject} {be_verb} {_natural_join(actions)}."


def _format_collection_phrase(context: MutableMapping[str, Any], tech: str) -> str:
    location = _metadata_text(context.get(f"{tech}_coll_location"))
    latitude = _metadata_text(context.get(f"{tech}_coll_lat_display")) or _metadata_text(
        context.get(f"{tech}_coll_lat")
    )
    longitude = _metadata_text(context.get(f"{tech}_coll_long_display")) or _metadata_text(
        context.get(f"{tech}_coll_long")
    )
    date = _metadata_text(context.get(f"{tech}_coll_date"))

    phrase = ""
    if location:
        phrase = f"from {location}"
        if latitude and longitude:
            phrase += f" (latitude {latitude}, longitude {longitude})"
    elif latitude and longitude:
        phrase = f"from latitude {latitude}, longitude {longitude}"

    if date:
        phrase = f"{phrase} on {date}" if phrase else f"on {date}"
    return phrase


def _groups_share_collection_sentence(
    context: MutableMapping[str, Any],
    groups: list[dict[str, Any]],
) -> bool:
    representatives = [group["representative"] for group in groups]
    compared_fields = ("collector_display", "identifier_display", "preserv_method")
    collection_phrases = [_format_collection_phrase(context, tech) for tech in representatives]
    field_values = [
        [_metadata_text(context.get(f"{tech}_{field_name}")) for tech in representatives]
        for field_name in compared_fields
    ]

    has_any_summary_detail = any(collection_phrases) or any(any(values) for values in field_values)
    if not has_any_summary_detail:
        return False

    if any(collection_phrases):
        first_collection = collection_phrases[0]
        if not first_collection or any(phrase.casefold() != first_collection.casefold() for phrase in collection_phrases):
            return False

    for values in field_values:
        present_values = [value for value in values if value]
        if present_values and (
            len(present_values) != len(values)
            or any(value.casefold() != present_values[0].casefold() for value in present_values)
        ):
            return False

    return True


def _count_word(value: int) -> str:
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
    }
    return words.get(value, str(value))


def _indefinite_article(phrase: str) -> str:
    text = phrase.strip()
    if not text:
        return "a"
    first_word = text.strip("*").split(maxsplit=1)[0]
    return "an" if first_word[:1].casefold() in {"a", "e", "i", "o", "u"} else "a"


def _relationship(context: MutableMapping[str, Any], left: str, right: str) -> str:
    shared_match = False
    shared_conflict = False

    for field_name in _IDENTITY_FIELDS:
        left_value = _metadata_text(context.get(f"{left}_{field_name}"))
        right_value = _metadata_text(context.get(f"{right}_{field_name}"))
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
    specimen_id = _metadata_text(context.get(f"{tech}_specimen_id"))
    tolid = _metadata_text(context.get(f"{tech}_tolid"))
    sample_accession = _metadata_text(context.get(f"{tech}_sample_accession"))
    source_individual = _metadata_text(context.get(f"{tech}_sample_derived_from"))

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
    tolid = _metadata_text(context.get(f"{tech}_tolid"))
    specimen_id = _metadata_text(context.get(f"{tech}_specimen_id"))
    source_individual = _metadata_text(context.get(f"{tech}_sample_derived_from"))
    sample_accession = _metadata_text(context.get(f"{tech}_sample_accession"))

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
    if _metadata_text(context.get(f"{tech}_tolid")) or _metadata_text(context.get(f"{tech}_specimen_id")):
        return _metadata_text(context.get(f"{tech}_specimen_short_label"))

    if fallback_tech:
        fallback_label = _metadata_text(context.get(f"{fallback_tech}_specimen_short_label"))
        if fallback_label:
            return fallback_label

    return _metadata_text(context.get(f"{tech}_specimen_short_label"))


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
    left_date = _metadata_text(context.get(f"{left}_coll_date"))
    right_date = _metadata_text(context.get(f"{right}_coll_date"))
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


def _set_coordinate_display_fields(context: MutableMapping[str, Any], tech: str, field_name: str) -> None:
    key = f"{tech}_{field_name}"
    display_key = f"{key}_display"
    raw_value = context.get(key)
    display_value = _format_coordinate(raw_value)
    context[display_key] = display_value
    if display_value and display_value != _clean_string(raw_value):
        context[key] = display_value


def _format_tissue_phrase(organism_part: Any) -> str:
    part = _clean_string(organism_part)
    if not part:
        return "tissue"

    normalised_part = part.replace("_", " ").casefold()
    if normalised_part in _MISSING_ORGANISM_PARTS:
        return "tissue"
    if normalised_part == "tissue" or normalised_part.endswith(" tissue"):
        return part
    return f"{part} tissue"


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


def _metadata_text(value: Any) -> str:
    text = _clean_string(value)
    if text.casefold() in _MISSING_TEXT_VALUES:
        return ""
    return text
