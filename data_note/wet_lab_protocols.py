from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
import unicodedata
from typing import Any


COLLECTION_TITLE = "Sanger Tree of Life Wet Laboratory Protocol Collection"
COLLECTION_VERSION = 3
COLLECTION_PUBLISHED = "2025-11-18"
COLLECTION_URL = (
    "https://www.protocols.io/view/"
    "sanger-tree-of-life-wet-laboratory-protocol-collec-8epv5xxy6g1b/v3"
)
COLLECTION_DOI = "https://dx.doi.org/10.17504/protocols.io.8epv5xxy6g1b/v3"


@dataclass(frozen=True, slots=True)
class WetLabProtocol:
    key: str
    category: str
    title: str
    slug: str
    version: int = 1
    aliases: tuple[str, ...] = ()

    @property
    def url(self) -> str:
        return f"https://www.protocols.io/view/{self.slug}"

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category,
            "title": self.title,
            "url": self.url,
            "version": self.version,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True, slots=True)
class WetLabProtocolMatch:
    protocol: WetLabProtocol
    confidence: str
    source: str
    matched_value: str = ""
    note: str = ""
    review_required: bool = False

    def to_context_dict(self) -> dict[str, Any]:
        context = self.protocol.to_context_dict()
        context.update(
            {
                "confidence": self.confidence,
                "source": self.source,
                "matched_value": self.matched_value,
                "note": self.note,
                "review_required": self.review_required,
            }
        )
        return context


WET_LAB_PROTOCOLS: tuple[WetLabProtocol, ...] = (
    WetLabProtocol(
        "sample_preparation_triage_dissection",
        "sample_preparation",
        "Sanger Tree of Life Sample Preparation: Triage and Dissection",
        "sanger-tree-of-life-sample-preparation-triage-and-cztex6je",
        aliases=("triage", "dissection", "sample preparation"),
    ),
    WetLabProtocol(
        "homogenisation_powermash",
        "homogenisation",
        "Sanger Tree of Life Sample Homogenisation: PowerMash",
        "sanger-tree-of-life-sample-homogenisation-powermas-cyf8xtrw",
        aliases=("powermash", "power mash", "powermashing"),
    ),
    WetLabProtocol(
        "homogenisation_covaris_cryoprep",
        "homogenisation",
        "Sanger Tree of Life Sample Homogenisation: Covaris cryoPREP Automated Dry Pulverizer",
        "sanger-tree-of-life-sample-homogenisation-covaris-c45pyy5n",
        version=2,
        aliases=("covaris", "cryoprep", "cryo prep", "cryogenic disruption"),
    ),
    WetLabProtocol(
        "homogenisation_cryogenic_bead_beating",
        "homogenisation",
        "Sanger Tree of Life Sample Homogenisation: Cryogenic Bead Beating of Samples with FastPrep-96",
        "sanger-tree-of-life-sample-homogenisation-cryogeni-g9nubz5ex",
        version=2,
        aliases=("cryogenic bead beating", "fastprep", "fastprep 96", "bead beating"),
    ),
    WetLabProtocol(
        "homogenisation_sponge_squeezing",
        "homogenisation",
        "Sanger Tree of Life Sample Homogenisation: Sponge Squeezing",
        "sanger-tree-of-life-sample-homogenisation-sponge-s-ha7cb2hix",
        aliases=("sponge squeezing", "sponge"),
    ),
    WetLabProtocol(
        "extraction_manual_magattract",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual MagAttract",
        "sanger-tree-of-life-hmw-dna-extraction-manual-maga-cy3ixyke",
        aliases=("manual magattract", "magattract manual"),
    ),
    WetLabProtocol(
        "extraction_manual_magattract_v3",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual MagAttract v3",
        "sanger-tree-of-life-hmw-dna-extraction-manual-maga-g9cpbz2vp",
        aliases=("manual magattract v3", "magattract manual v3"),
    ),
    WetLabProtocol(
        "extraction_automated_magattract_v1",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated MagAttract v.1",
        "sanger-tree-of-life-hmw-dna-extraction-automated-m-czh2x38e",
        aliases=("automated magattract v1", "automatic magattract v1"),
    ),
    WetLabProtocol(
        "extraction_automated_magattract_v2",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated MagAttract v.2",
        "sanger-tree-of-life-hmw-dna-extraction-automated-m-czjux4nw",
        aliases=("automated magattract v2", "automatic magattract v2", "magattract standard 48xrn"),
    ),
    WetLabProtocol(
        "extraction_automated_magattract_v3",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated MagAttract v.3",
        "sanger-tree-of-life-hmw-dna-extraction-automated-m-g9ctbz2wp",
        aliases=("automated magattract v3", "automatic magattract v3"),
    ),
    WetLabProtocol(
        "extraction_automated_magattract_small_arthropods",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated MagAttract for Small Arthropods",
        "sanger-tree-of-life-hmw-dna-extraction-automated-m-c85rzy56",
        aliases=("small arthropods", "small arthropod", "magattract small arthropods"),
    ),
    WetLabProtocol(
        "extraction_manual_plant_magattract_v1",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Plant MagAttract v.1",
        "sanger-tree-of-life-hmw-dna-extraction-manual-plan-cy3jxykn",
        aliases=("manual plant magattract v1",),
    ),
    WetLabProtocol(
        "extraction_manual_plant_magattract_v23",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Plant MagAttract v.2/3",
        "sanger-tree-of-life-hmw-dna-extraction-manual-plan-czhrx356",
        aliases=("manual plant magattract v2", "manual plant magattract v3"),
    ),
    WetLabProtocol(
        "extraction_manual_plant_magattract_v4",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Plant MagAttract v.4",
        "sanger-tree-of-life-hmw-dna-extraction-manual-plan-czjsx4ne",
        aliases=("manual plant magattract v4",),
    ),
    WetLabProtocol(
        "extraction_manual_plant_magattract_v5",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Plant MagAttract v.5",
        "sanger-tree-of-life-hmw-dna-extraction-manual-plan-g9csbz2wf",
        aliases=("manual plant magattract v5",),
    ),
    WetLabProtocol(
        "extraction_automated_plant_magattract_v1",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Plant MagAttract v.1",
        "sanger-tree-of-life-hmw-dna-extraction-automated-p-czj3x4qn",
        aliases=("automated plant magattract v1", "automatic plant magattract v1"),
    ),
    WetLabProtocol(
        "extraction_automated_plant_magattract_v2",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Plant MagAttract v.2",
        "sanger-tree-of-life-hmw-dna-extraction-automated-p-czj6x4re",
        aliases=("automated plant magattract v2", "automatic plant magattract v2"),
    ),
    WetLabProtocol(
        "extraction_automated_plant_magattract_v3",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Plant MagAttract v.3",
        "sanger-tree-of-life-hmw-dna-extraction-automated-p-czj9x4r6",
        aliases=("automated plant magattract v3", "automatic plant magattract v3"),
    ),
    WetLabProtocol(
        "extraction_automated_plant_magattract_v4",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Plant MagAttract v.4",
        "sanger-tree-of-life-hmw-dna-extraction-automated-p-czhhx336",
        aliases=("automated plant magattract v4", "automatic plant magattract v4", "plant magattract 48xrn v4"),
    ),
    WetLabProtocol(
        "extraction_automated_plant_magattract_v5",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Plant MagAttract v.5",
        "sanger-tree-of-life-hmw-dna-extraction-automated-p-g9cvbz2w7",
        aliases=("automated plant magattract v5", "automatic plant magattract v5", "plant magattract 48xrn v5"),
    ),
    WetLabProtocol(
        "extraction_automated_plant_organic_poe",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Plant Organic HMW gDNA Extraction (POE)",
        "sanger-tree-of-life-hmw-dna-extraction-automated-c5gay3se",
        aliases=("poe", "plant organic extraction", "plant organic hmw gdna extraction"),
    ),
    WetLabProtocol(
        "extraction_hypertonic_washing_plant",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Hypertonic Washing of Plant Tissue Homogenates",
        "sanger-tree-of-life-hmw-dna-extraction-hypertonic-dsnc6daw",
        aliases=("hypertonic washing", "plant tissue homogenates"),
    ),
    WetLabProtocol(
        "extraction_automated_low_input_plant_organic_lopoe_bryophyta",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Low-Input Plant Organic HMW DNA Extraction (LoPOE) of Bryophyta",
        "sanger-tree-of-life-hmw-dna-extraction-automated-l-dy5u7y6w",
        aliases=("lopoe", "low input plant organic", "bryophyta"),
    ),
    WetLabProtocol(
        "extraction_manual_nucleated_blood_nanobind",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Nucleated Blood Nanobind",
        "sanger-tree-of-life-hmw-dna-extraction-manual-nucl-czhgx33w",
        aliases=("manual nucleated blood nanobind", "blood nanobind manual"),
    ),
    WetLabProtocol(
        "extraction_automated_nucleated_blood_nanobind",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Nucleated Blood Nanobind",
        "sanger-tree-of-life-hmw-dna-extraction-automated-n-dd2e28be",
        aliases=("automated nucleated blood nanobind", "blood nanobind automated"),
    ),
    WetLabProtocol(
        "extraction_manual_tissue_nanobind_v2",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Tissue Nanobind v.2",
        "sanger-tree-of-life-hmw-dna-extraction-manual-tiss-g7wjbzpcp",
        version=2,
        aliases=("manual tissue nanobind", "tissue nanobind"),
    ),
    WetLabProtocol(
        "extraction_manual_modified_omega_biotek_v2",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Manual Modified Omega Bio-Tek E.Z.N.A.",
        "sanger-tree-of-life-hmw-dna-extraction-manual-modi-dyn57vg6",
        version=2,
        aliases=("manual modified omega", "manual omega biotek", "manual e z n a"),
    ),
    WetLabProtocol(
        "extraction_automated_modified_omega_biotek",
        "extraction",
        "Sanger Tree of Life HMW DNA Extraction: Automated Modified Omega Bio-Tek E.Z.N.A.",
        "sanger-tree-of-life-hmw-dna-extraction-automated-m-dy7r7zm6",
        aliases=("automated modified omega", "automated omega biotek", "automated e z n a"),
    ),
    WetLabProtocol(
        "fragmentation_megaruptor_pacbio_hifi",
        "fragmentation",
        "Sanger Tree of Life HMW DNA Fragmentation: Diagenode Megaruptor3 for PacBio HiFi",
        "sanger-tree-of-life-hmw-dna-fragmentation-diagenod-cztmx6k6",
        aliases=("megaruptor pacbio hifi", "megaruptor hifi"),
    ),
    WetLabProtocol(
        "fragmentation_megaruptor_li_pacbio",
        "fragmentation",
        "Sanger Tree of Life HMW DNA Fragmentation: Diagenode Megaruptor3 for LI PacBio",
        "sanger-tree-of-life-hmw-dna-fragmentation-diagenod-czhmx346",
        aliases=("megaruptor li pacbio", "megaruptor low input pacbio"),
    ),
    WetLabProtocol(
        "fragmentation_opentrons_ot2_pacbio_li",
        "fragmentation",
        "Sanger Tree of Life HMW DNA Fragmentation: Opentrons OT-2 for PacBio LI",
        "sanger-tree-of-life-hmw-dna-fragmentation-opentron-g9cwbz2xf",
        aliases=("opentrons pacbio li", "opentrons ot 2 pacbio"),
    ),
    WetLabProtocol(
        "fragmentation_opentrons_ot2_ont",
        "fragmentation",
        "Sanger Tree of Life HMW DNA Fragmentation: Opentrons OT-2 for ONT",
        "sanger-tree-of-life-hmw-dna-fragmentation-opentron-hbifb2kbp",
        aliases=("opentrons ont", "opentrons ot 2 ont"),
    ),
    WetLabProtocol(
        "fragmentation_covaris_gtube_uli_pacbio",
        "fragmentation",
        "Sanger Tree of Life HMW DNA Fragmentation: Covaris g-TUBE for ULI PacBio",
        "sanger-tree-of-life-hmw-dna-fragmentation-covaris-cztpx6mn",
        aliases=("covaris g tube", "gtube", "g tube", "uli pacbio", "ultra low input"),
    ),
    WetLabProtocol(
        "cleanup_manual_spri",
        "cleanup",
        "Sanger Tree of Life Fragmented DNA clean up: Manual SPRI",
        "sanger-tree-of-life-fragmented-dna-clean-up-manual-czhkx34w",
        aliases=("manual spri", "pronex manual"),
    ),
    WetLabProtocol(
        "cleanup_automated_spri",
        "cleanup",
        "Sanger Tree of Life Fragmented DNA clean up: Automated SPRI",
        "sanger-tree-of-life-fragmented-dna-clean-up-automa-g9c3bz2yp",
        version=2,
        aliases=("automated spri", "automatic spri", "auto kf", "kingfisher"),
    ),
    WetLabProtocol(
        "rna_extraction_manual_trizol",
        "rna_extraction",
        "Sanger Tree of Life RNA Extraction: Manual TRIzol",
        "sanger-tree-of-life-rna-extraction-manual-trizol-cy3kxykw",
        aliases=("manual trizol", "trizol"),
    ),
    WetLabProtocol(
        "rna_extraction_automated_magmax_mirvana",
        "rna_extraction",
        "Sanger Tree of Life RNA Extraction: Automated MagMax mirVana",
        "sanger-tree-of-life-rna-extraction-automated-magma-cxxnxpme",
        aliases=("automated magmax mirvana", "magmax mirvana", "magmax", "mirvana"),
    ),
    WetLabProtocol(
        "extraction_pooling",
        "pooling",
        "Sanger Tree of Life HMW DNA Extraction: Pooling",
        "sanger-tree-of-life-hmw-dna-extraction-pooling-cxxvxpn6",
        aliases=("pooling", "hmw dna pooling"),
    ),
)

PROTOCOL_BY_KEY: dict[str, WetLabProtocol] = {protocol.key: protocol for protocol in WET_LAB_PROTOCOLS}

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


def build_wet_lab_protocol_context(context: Mapping[str, Any]) -> dict[str, Any]:
    homogenisation = _select_homogenisation(context)
    extraction, extraction_candidates, extraction_warnings = _select_extraction(context)
    fragmentation, fragmentation_candidates, fragmentation_warnings = _select_fragmentation(context, extraction)
    cleanup, cleanup_warnings = _select_cleanup(context)
    rna_extraction, rna_warnings = _select_rna_extraction(context)

    warnings = [
        *extraction_warnings,
        *fragmentation_warnings,
        *cleanup_warnings,
        *rna_warnings,
    ]
    matches = {
        "sample_preparation": _match(
            "sample_preparation_triage_dissection",
            confidence="published",
            source="collection",
            note="Default sample preparation protocol in the collection.",
        ).to_context_dict(),
        "homogenisation": _as_context(homogenisation),
        "extraction": _as_context(extraction),
        "extraction_candidates": _as_context_list(extraction_candidates),
        "fragmentation": _as_context(fragmentation),
        "fragmentation_candidates": _as_context_list(fragmentation_candidates),
        "cleanup": _as_context(cleanup),
        "rna_extraction": _as_context(rna_extraction),
    }
    selected = {
        step: value["title"]
        for step, value in matches.items()
        if isinstance(value, dict) and value.get("title")
    }
    review_required = any(
        match.get("review_required")
        for match in matches.values()
        if isinstance(match, dict)
    ) or bool(extraction_candidates or fragmentation_candidates or warnings)

    return {
        "wet_lab_protocol_collection": {
            "title": COLLECTION_TITLE,
            "version": COLLECTION_VERSION,
            "published": COLLECTION_PUBLISHED,
            "url": COLLECTION_URL,
            "doi": COLLECTION_DOI,
        },
        "wet_lab_protocol_catalog": [protocol.to_context_dict() for protocol in WET_LAB_PROTOCOLS],
        "wet_lab_protocol_matches": matches,
        "wet_lab_protocol_selection_summary": selected,
        "wet_lab_protocol_warnings": warnings,
        "wet_lab_protocol_review_required": review_required,
        "wet_lab_protocol_review_note": _review_note(warnings, extraction_candidates, fragmentation_candidates),
        "wet_lab_protocol_editor_comment": _editor_comment(
            source_context=context,
            matches=matches,
            warnings=warnings,
            review_required=review_required,
        ),
        "sample_preparation_protocol": matches["sample_preparation"],
        "homogenisation_protocol": matches["homogenisation"],
        "extraction_protocol_match": matches["extraction"],
        "extraction_protocol_candidates": matches["extraction_candidates"],
        "fragmentation_protocol": matches["fragmentation"],
        "fragmentation_protocol_candidates": matches["fragmentation_candidates"],
        "cleanup_protocol": matches["cleanup"],
        "rna_extraction_protocol": matches["rna_extraction"],
    }


def all_wet_lab_protocols(category: str | None = None) -> tuple[WetLabProtocol, ...]:
    if category is None:
        return WET_LAB_PROTOCOLS
    return tuple(protocol for protocol in WET_LAB_PROTOCOLS if protocol.category == category)


def _select_homogenisation(context: Mapping[str, Any]) -> WetLabProtocolMatch | None:
    value = _joined_context(context, "disruption_method")
    norm = _normalise(value)
    if not norm:
        return None
    if _contains_any(norm, "powermash", "power mash", "powermashing"):
        return _match("homogenisation_powermash", source="disruption_method", matched_value=value)
    if _contains_any(norm, "sponge"):
        return _match("homogenisation_sponge_squeezing", source="disruption_method", matched_value=value)
    if _contains_any(norm, "fastprep", "fastprep 96", "bead beating", "cryogenic bead"):
        return _match("homogenisation_cryogenic_bead_beating", source="disruption_method", matched_value=value)
    if _contains_any(norm, "covaris", "cryoprep", "cryo prep", "cryogenic disruption", "cryo"):
        return _match("homogenisation_covaris_cryoprep", source="disruption_method", matched_value=value)
    return None


def _select_extraction(
    context: Mapping[str, Any],
) -> tuple[WetLabProtocolMatch | None, list[WetLabProtocolMatch], list[str]]:
    protocol_value = _joined_context(context, "extraction_protocol", "protocol")
    mode_value = _joined_context(context, "extraction_mode")
    protocol_norm = _normalise(protocol_value)
    mode_norm = _normalise(mode_value)
    if not protocol_norm:
        return None, [], []

    source = "extraction_protocol"
    blob_norm = _normalise(" ".join((protocol_value, mode_value)))
    manual = _contains_any(blob_norm, "manual")
    automated = _contains_any(blob_norm, "automated", "automatic", "auto", "kingfisher", "48xrn")
    version = _version_from_text(blob_norm)

    if _contains_any(blob_norm, "small arthropod", "small arthropods"):
        return _inferred("extraction_automated_magattract_small_arthropods", source, protocol_value), [], []
    if _contains_any(blob_norm, "lopoe", "low input plant organic"):
        return _inferred("extraction_automated_low_input_plant_organic_lopoe_bryophyta", source, protocol_value), [], []
    if _contains_any(blob_norm, "hypertonic"):
        return _inferred("extraction_hypertonic_washing_plant", source, protocol_value), [], []
    if _contains_any(blob_norm, "poe", "plant organic extraction", "plant organic hmw"):
        return _inferred("extraction_automated_plant_organic_poe", source, protocol_value), [], []
    if _contains_any(blob_norm, "omega", "e z n a", "ezna"):
        key = "extraction_manual_modified_omega_biotek_v2" if manual else "extraction_automated_modified_omega_biotek"
        return _inferred(key, source, protocol_value), [], []
    if _contains_any(blob_norm, "nanobind"):
        return _select_nanobind(blob_norm, protocol_value, source, manual, automated)
    if _contains_any(blob_norm, "plant") and _contains_any(blob_norm, "magattract"):
        return _select_plant_magattract(protocol_value, source, manual, automated, version)
    if _contains_any(blob_norm, "magattract"):
        return _select_magattract(protocol_value, source, manual, automated, version)

    warning = f"No wet lab extraction protocol mapping for extraction_protocol={protocol_value!r}."
    return None, [], [warning]


def _select_nanobind(
    blob_norm: str,
    matched_value: str,
    source: str,
    manual: bool,
    automated: bool,
) -> tuple[WetLabProtocolMatch | None, list[WetLabProtocolMatch], list[str]]:
    if _contains_any(blob_norm, "blood", "nucleated blood"):
        if automated and not manual:
            return _inferred("extraction_automated_nucleated_blood_nanobind", source, matched_value), [], []
        return _inferred("extraction_manual_nucleated_blood_nanobind", source, matched_value), [], []
    if _contains_any(blob_norm, "tissue"):
        return _inferred("extraction_manual_tissue_nanobind_v2", source, matched_value), [], []
    candidates = [
        _candidate("extraction_manual_nucleated_blood_nanobind", source, matched_value),
        _candidate("extraction_automated_nucleated_blood_nanobind", source, matched_value),
        _candidate("extraction_manual_tissue_nanobind_v2", source, matched_value),
    ]
    return None, candidates, [f"Nanobind extraction metadata is ambiguous: {matched_value!r}."]


def _select_plant_magattract(
    matched_value: str,
    source: str,
    manual: bool,
    automated: bool,
    version: str | None,
) -> tuple[WetLabProtocolMatch | None, list[WetLabProtocolMatch], list[str]]:
    manual_by_version = {
        "1": "extraction_manual_plant_magattract_v1",
        "2": "extraction_manual_plant_magattract_v23",
        "3": "extraction_manual_plant_magattract_v23",
        "4": "extraction_manual_plant_magattract_v4",
        "5": "extraction_manual_plant_magattract_v5",
    }
    automated_by_version = {
        "1": "extraction_automated_plant_magattract_v1",
        "2": "extraction_automated_plant_magattract_v2",
        "3": "extraction_automated_plant_magattract_v3",
        "4": "extraction_automated_plant_magattract_v4",
        "5": "extraction_automated_plant_magattract_v5",
    }
    if version in manual_by_version and manual:
        return _inferred(manual_by_version[version], source, matched_value), [], []
    if version in automated_by_version and automated:
        return _inferred(automated_by_version[version], source, matched_value), [], []
    if version in automated_by_version:
        match = _candidate(
            automated_by_version[version],
            source,
            matched_value,
            note="Version was mapped, but manual/automated status should be checked.",
        )
        return match, [], [f"Check plant MagAttract manual/automated status for {matched_value!r}."]

    candidates = [
        _candidate("extraction_manual_plant_magattract_v23", source, matched_value),
        _candidate("extraction_automated_plant_magattract_v3", source, matched_value),
        _candidate("extraction_automated_plant_magattract_v4", source, matched_value),
        _candidate("extraction_automated_plant_magattract_v5", source, matched_value),
    ]
    return None, candidates, [f"Plant MagAttract extraction metadata is missing a clear version: {matched_value!r}."]


def _select_magattract(
    matched_value: str,
    source: str,
    manual: bool,
    automated: bool,
    version: str | None,
) -> tuple[WetLabProtocolMatch | None, list[WetLabProtocolMatch], list[str]]:
    if version == "3" and manual:
        return _inferred("extraction_manual_magattract_v3", source, matched_value), [], []
    if version == "3" and automated:
        return _inferred("extraction_automated_magattract_v3", source, matched_value), [], []
    if version == "3":
        candidates = [
            _candidate("extraction_manual_magattract_v3", source, matched_value),
            _candidate("extraction_automated_magattract_v3", source, matched_value),
        ]
        return None, candidates, [f"MagAttract v3 metadata is missing manual/automated status: {matched_value!r}."]
    if version == "1" and manual:
        return _inferred("extraction_manual_magattract", source, matched_value), [], []
    if version == "1":
        return _inferred("extraction_automated_magattract_v1", source, matched_value), [], []
    if version == "2" or automated:
        match = _candidate(
            "extraction_automated_magattract_v2",
            source,
            matched_value,
            note="Standard 48xrn MagAttract is treated as the automated v.2 candidate.",
        )
        return match, [], [f"Check MagAttract version/status for {matched_value!r}."]
    if manual:
        return _inferred("extraction_manual_magattract", source, matched_value), [], []
    candidates = [
        _candidate("extraction_manual_magattract", source, matched_value),
        _candidate("extraction_automated_magattract_v2", source, matched_value),
        _candidate("extraction_automated_magattract_v3", source, matched_value),
    ]
    return None, candidates, [f"MagAttract extraction metadata is ambiguous: {matched_value!r}."]


def _select_fragmentation(
    context: Mapping[str, Any],
    extraction: WetLabProtocolMatch | None,
) -> tuple[WetLabProtocolMatch | None, list[WetLabProtocolMatch], list[str]]:
    values = _context_values(context, "pacbio_protocols", "pacbio_library_construction_protocol")
    matched_value = "; ".join(values)
    norm = _normalise(matched_value)
    if not norm:
        return None, [], []
    if _contains_any(norm, "ultra low", "ultra low input", "ultra low input uli", "uli"):
        return _inferred(
            "fragmentation_covaris_gtube_uli_pacbio",
            "pacbio_protocols",
            matched_value,
            note="PacBio library metadata indicates ULI.",
        ), [], []
    if _contains_any(norm, "opentrons") and _has_word(norm, "ont"):
        return _inferred("fragmentation_opentrons_ot2_ont", "pacbio_protocols", matched_value), [], []
    if _contains_any(norm, "opentrons"):
        return _inferred("fragmentation_opentrons_ot2_pacbio_li", "pacbio_protocols", matched_value), [], []
    if _has_word(norm, "li") or _contains_any(norm, "low input"):
        return _inferred("fragmentation_megaruptor_li_pacbio", "pacbio_protocols", matched_value), [], []

    if extraction is not None:
        hifi_extractions = {
            "extraction_automated_magattract_v1",
            "extraction_automated_plant_magattract_v1",
            "extraction_automated_plant_magattract_v2",
        }
        key = extraction.protocol.key
        if key in hifi_extractions:
            return _inferred(
                "fragmentation_megaruptor_pacbio_hifi",
                "extraction_protocol",
                extraction.matched_value,
                note="Inferred from extraction protocol family.",
                review_required=extraction.review_required,
            ), [], []
        if key.startswith("extraction_"):
            return _inferred(
                "fragmentation_megaruptor_li_pacbio",
                "extraction_protocol",
                extraction.matched_value,
                note="Inferred from extraction protocol family.",
                review_required=extraction.review_required,
            ), [], []

    candidates = [
        _candidate("fragmentation_megaruptor_pacbio_hifi", "pacbio_protocols", matched_value),
        _candidate("fragmentation_megaruptor_li_pacbio", "pacbio_protocols", matched_value),
    ]
    return None, candidates, [f"PacBio protocol metadata does not distinguish HiFi vs LI fragmentation: {matched_value!r}."]


def _select_cleanup(context: Mapping[str, Any]) -> tuple[WetLabProtocolMatch | None, list[str]]:
    matched_value = _joined_context(context, "spri_type")
    norm = _normalise(matched_value)
    pacbio_norm = _normalise(_joined_context(context, "pacbio_protocols"))
    if _contains_any(norm, "manual", "pronex manual"):
        return _match("cleanup_manual_spri", source="spri_type", matched_value=matched_value), []
    if _contains_any(norm, "automated", "automatic", "auto", "kingfisher", "kf", "apex"):
        return _match("cleanup_automated_spri", source="spri_type", matched_value=matched_value), []
    if _contains_any(pacbio_norm, "uli", "ultra low"):
        return _candidate(
            "cleanup_automated_spri",
            "pacbio_protocols",
            _joined_context(context, "pacbio_protocols"),
            note="ULI samples are expected to use automated SPRI, but check the wet lab record.",
        ), []
    if matched_value:
        return None, [f"No wet lab cleanup protocol mapping for spri_type={matched_value!r}."]
    return None, []


def _select_rna_extraction(context: Mapping[str, Any]) -> tuple[WetLabProtocolMatch | None, list[str]]:
    values = _context_values(context, "rna_extraction_protocol", "rna_protocol")
    values.extend(_rna_nested_protocol_values(context))
    matched_value = "; ".join(values)
    norm = _normalise(matched_value)
    if _contains_any(norm, "trizol"):
        return _inferred("rna_extraction_manual_trizol", "rna_extraction_protocol", matched_value), []
    if _contains_any(norm, "magmax", "mirvana"):
        return _inferred("rna_extraction_automated_magmax_mirvana", "rna_extraction_protocol", matched_value), []
    if _has_rna_data(context):
        return _candidate(
            "rna_extraction_automated_magmax_mirvana",
            "rna_tolid",
            str(context.get("rna_tolid") or ""),
            note="RNA is present, but the extraction protocol is not explicit in the current metadata.",
        ), ["RNA data are present, but RNA extraction protocol metadata should be checked manually."]
    return None, []


def _rna_nested_protocol_values(context: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    technology_data = context.get("technology_data")
    if isinstance(technology_data, Mapping):
        rna_data = technology_data.get("rna") or technology_data.get("RNA")
        if isinstance(rna_data, Mapping):
            values.extend(_as_strings(rna_data.get("rna_library_construction_protocol")))
    seq_data = context.get("seq_data")
    if isinstance(seq_data, Mapping):
        for row in seq_data.get("RNA") or []:
            if isinstance(row, Mapping):
                values.extend(_as_strings(row.get("library_construction_protocol")))
    return [value for value in values if _contains_any(_normalise(value), "trizol", "magmax", "mirvana")]


def _has_rna_data(context: Mapping[str, Any]) -> bool:
    if context.get("rna_tolid"):
        return True
    technology_data = context.get("technology_data")
    if isinstance(technology_data, Mapping) and technology_data.get("rna"):
        return True
    seq_data = context.get("seq_data")
    if isinstance(seq_data, Mapping) and seq_data.get("RNA"):
        return True
    return False


def _match(
    key: str,
    *,
    confidence: str = "mapped",
    source: str,
    matched_value: str = "",
    note: str = "",
    review_required: bool = False,
) -> WetLabProtocolMatch:
    return WetLabProtocolMatch(
        protocol=PROTOCOL_BY_KEY[key],
        confidence=confidence,
        source=source,
        matched_value=matched_value,
        note=note,
        review_required=review_required,
    )


def _inferred(
    key: str,
    source: str,
    matched_value: str,
    *,
    note: str = "",
    review_required: bool = False,
) -> WetLabProtocolMatch:
    return _match(
        key,
        confidence="inferred",
        source=source,
        matched_value=matched_value,
        note=note,
        review_required=review_required,
    )


def _candidate(key: str, source: str, matched_value: str, *, note: str = "") -> WetLabProtocolMatch:
    return _match(
        key,
        confidence="candidate",
        source=source,
        matched_value=matched_value,
        note=note,
        review_required=True,
    )


def _as_context(match: WetLabProtocolMatch | None) -> dict[str, Any] | None:
    return match.to_context_dict() if match else None


def _as_context_list(matches: Sequence[WetLabProtocolMatch]) -> list[dict[str, Any]]:
    return [match.to_context_dict() for match in matches]


def _review_note(
    warnings: Sequence[str],
    extraction_candidates: Sequence[WetLabProtocolMatch],
    fragmentation_candidates: Sequence[WetLabProtocolMatch],
) -> str:
    notes = list(warnings)
    if extraction_candidates:
        notes.append("Multiple extraction protocol candidates are available in extraction_protocol_candidates.")
    if fragmentation_candidates:
        notes.append("Multiple fragmentation protocol candidates are available in fragmentation_protocol_candidates.")
    if not notes:
        return "Wet lab protocol mapping found no review-only ambiguities."
    return "Manual wet lab protocol review recommended: " + " ".join(notes)


def _editor_comment(
    *,
    source_context: Mapping[str, Any],
    matches: Mapping[str, Any],
    warnings: Sequence[str],
    review_required: bool,
) -> str:
    lines = [
        "<!--",
        "Wet lab protocol editor note",
        f"Collection: {COLLECTION_TITLE} V.{COLLECTION_VERSION}",
        f"Collection URL: {COLLECTION_URL}",
        f"Manual review required: {'yes' if review_required else 'no'}",
        "",
        "Source metadata:",
    ]
    for key in (
        "extraction_protocol",
        "protocol",
        "extraction_mode",
        "disruption_method",
        "spri_type",
        "pacbio_protocols",
        "pacbio_library_construction_protocol",
        "rna_tolid",
        "rna_extraction_protocol",
        "rna_protocol",
    ):
        value = source_context.get(key)
        if value not in (None, "", []):
            lines.append(f"- {key}: {_display_value(value)}")

    lines.extend(["", "Likely protocol choices from current metadata:"])
    for step in (
        "sample_preparation",
        "homogenisation",
        "extraction",
        "fragmentation",
        "cleanup",
        "rna_extraction",
    ):
        value = matches.get(step)
        if isinstance(value, Mapping):
            lines.append(f"- {step}: {_match_summary(value)}")
        else:
            lines.append(f"- {step}: no automatic match")

    _append_candidates(lines, "extraction candidates", matches.get("extraction_candidates"))
    _append_candidates(lines, "fragmentation candidates", matches.get("fragmentation_candidates"))

    if warnings:
        lines.extend(["", "Mapping warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(["", "Published protocol catalog:"])
    for protocol in WET_LAB_PROTOCOLS:
        lines.append(f"- {protocol.category}: {protocol.title} - {protocol.url}")

    lines.extend(
        [
            "",
            "Edit the methods prose below by hand if the portal metadata is incomplete or the mapped protocol is wrong.",
            "-->",
        ]
    )
    return "\n".join(_sanitize_comment_line(line) for line in lines)


def _append_candidates(lines: list[str], heading: str, candidates: Any) -> None:
    if not candidates:
        return
    lines.extend(["", f"{heading}:"])
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            lines.append(f"- {_match_summary(candidate)}")


def _match_summary(match: Mapping[str, Any]) -> str:
    summary = f"[{match.get('confidence', 'mapped')}] {match.get('title', '')} - {match.get('url', '')}"
    matched_value = match.get("matched_value")
    if matched_value:
        summary += f" (matched {match.get('source', 'metadata')}: {_display_value(matched_value)})"
    note = match.get("note")
    if note:
        summary += f" Note: {note}"
    if match.get("review_required"):
        summary += " Review before finalising."
    return summary


def _display_value(value: Any) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "; ".join(str(item) for item in value)
    return str(value)


def _sanitize_comment_line(line: str) -> str:
    if line in {"<!--", "-->"}:
        return line
    return line.replace("--", "-")


def _context_values(context: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(_as_strings(context.get(key)))
    return [value for value in values if value]


def _joined_context(context: Mapping[str, Any], *keys: str) -> str:
    return "; ".join(_context_values(context, *keys))


def _as_strings(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(item) for item in value.values() if item not in (None, "")]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = _NON_WORD_RE.sub(" ", value.lower())
    return _SPACE_RE.sub(" ", value).strip()


def _contains_any(norm_value: str, *needles: str) -> bool:
    return any(_normalise(needle) in norm_value for needle in needles)


def _has_word(norm_value: str, word: str) -> bool:
    return re.search(rf"(?:^|\s){re.escape(_normalise(word))}(?:\s|$)", norm_value) is not None


def _version_from_text(norm_value: str) -> str | None:
    for version in ("5", "4", "3", "2", "1"):
        if re.search(rf"(?:^|\s)v\s*{version}(?:\s|$)", norm_value):
            return version
        if re.search(rf"(?:^|\s)version\s*{version}(?:\s|$)", norm_value):
            return version
    return None
