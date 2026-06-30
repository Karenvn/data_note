from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


AEGIS_ACCESSION = "PRJEB80366"
DTOL_ACCESSION = "PRJEB40665"
TOL_PROGRAMME_ACCESSION = "PRJEB43745"

SUPPLEMENTAL_PARENT_PROJECT_ACCESSIONS = frozenset({AEGIS_ACCESSION})

KNOWN_PROJECTS: dict[str, dict[str, str]] = {
    AEGIS_ACCESSION: {
        "project_name": "AEGIS",
        "accession": AEGIS_ACCESSION,
    },
    "aegis": {
        "project_name": "AEGIS",
        "accession": AEGIS_ACCESSION,
    },
    "ancient environmental genomics initiative for sustainability": {
        "project_name": "AEGIS",
        "accession": AEGIS_ACCESSION,
    },
    DTOL_ACCESSION: {
        "project_name": "Darwin Tree of Life Project",
        "accession": DTOL_ACCESSION,
    },
    "darwin tree of life project": {
        "project_name": "Darwin Tree of Life Project",
        "accession": DTOL_ACCESSION,
    },
    "dtol": {
        "project_name": "Darwin Tree of Life Project",
        "accession": DTOL_ACCESSION,
    },
    TOL_PROGRAMME_ACCESSION: {
        "project_name": "Sanger Institute Tree of Life Programme",
        "accession": TOL_PROGRAMME_ACCESSION,
    },
    "sanger institute tree of life programme": {
        "project_name": "Sanger Institute Tree of Life Programme",
        "accession": TOL_PROGRAMME_ACCESSION,
    },
    "tree of life programme": {
        "project_name": "Sanger Institute Tree of Life Programme",
        "accession": TOL_PROGRAMME_ACCESSION,
    },
}


def project_accession(project: Any) -> str | None:
    if isinstance(project, Mapping):
        for key in ("accession", "study_accession", "project_accession"):
            accession = _clean_text(project.get(key))
            if accession:
                return accession
        known = _known_project(project.get("project_name") or project.get("name") or project.get("title"))
        if known:
            return known["accession"]
        return None

    known = _known_project(project)
    if known:
        return known["accession"]
    text = _clean_text(project)
    if text and text.upper().startswith(("PRJEB", "PRJNA", "ERP")):
        return text
    return None


def project_label(project: Any) -> str | None:
    normalised = _normalise_project(project)
    if not normalised:
        return None

    name = _clean_text(
        normalised.get("project_name")
        or normalised.get("name")
        or normalised.get("title")
    )
    accession = _clean_text(normalised.get("accession"))
    if name and accession:
        return f"{name} ({accession})"
    return name or accession


def format_project_list(projects: Iterable[Any] | None) -> str | None:
    labels = [label for project in projects or [] if (label := project_label(project))]
    if not labels:
        return None
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def normalise_project_entries(raw_projects: Any) -> list[dict[str, Any]]:
    if raw_projects in (None, ""):
        return []

    if isinstance(raw_projects, Mapping):
        if _looks_like_project(raw_projects):
            projects = [raw_projects]
        else:
            projects = raw_projects.values()
    elif isinstance(raw_projects, str):
        projects = [raw_projects]
    elif isinstance(raw_projects, Iterable):
        projects = raw_projects
    else:
        projects = [raw_projects]

    normalised: list[dict[str, Any]] = []
    for project in projects:
        entry = _normalise_project(project)
        if entry:
            normalised.append(entry)
    return normalised


def split_parent_projects(
    parent_projects: Iterable[Any] | None,
    *,
    explicit_project_accessions: Iterable[str | None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    explicit_accessions = {
        str(accession).strip()
        for accession in explicit_project_accessions or []
        if str(accession or "").strip()
    }
    primary: list[dict[str, Any]] = []
    supplemental: list[dict[str, Any]] = []

    for project in normalise_project_entries(parent_projects):
        accession = project_accession(project)
        if (
            accession in SUPPLEMENTAL_PARENT_PROJECT_ACCESSIONS
            and accession not in explicit_accessions
        ):
            supplemental.append(project)
        else:
            primary.append(project)

    return primary, supplemental


def normalise_project_provenance(raw_provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    if not raw_provenance:
        return {}

    context: dict[str, Any] = {}
    for field in (
        "funding_projects",
        "data_reuse_projects",
        "programme_projects",
        "supplemental_parent_projects",
    ):
        projects = normalise_project_entries(raw_provenance.get(field))
        if projects:
            context[field] = projects
            context[f"formatted_{field}"] = format_project_list(projects)

    for field in (
        "funding_statement",
        "project_provenance_note",
        "project_provenance_source",
    ):
        value = _clean_text(raw_provenance.get(field))
        if value:
            context[field] = value

    return context


def _normalise_project(project: Any) -> dict[str, Any] | None:
    known = _known_project(project)
    if known:
        return dict(known)

    if isinstance(project, Mapping):
        entry = dict(project)
        name = _clean_text(
            entry.get("project_name")
            or entry.get("name")
            or entry.get("title")
        )
        accession = project_accession(entry)
        if name:
            entry["project_name"] = name
        if accession:
            entry["accession"] = accession
        if entry.get("project_name") or entry.get("accession"):
            return entry
        return None

    text = _clean_text(project)
    if not text:
        return None
    if text.upper().startswith(("PRJEB", "PRJNA", "ERP")):
        return {"accession": text}
    return {"project_name": text}


def _known_project(raw_value: Any) -> dict[str, str] | None:
    text = _clean_text(raw_value)
    if not text:
        return None
    return KNOWN_PROJECTS.get(text) or KNOWN_PROJECTS.get(text.casefold())


def _looks_like_project(value: Mapping[str, Any]) -> bool:
    return any(key in value for key in ("accession", "study_accession", "project_accession", "project_name", "name", "title"))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
