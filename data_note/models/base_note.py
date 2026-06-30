from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping


@dataclass(slots=True)
class BaseNoteInfo:
    bioproject: str | None = None
    study_title: str | None = None
    tax_id: str | None = None
    tax_id_umbrella: str | None = None
    tolid: str | None = None
    assemblies_type: str | None = None
    assembly_name: str | None = None
    auto_text: str | None = None
    distribution_text: str | None = None
    barcode_text: str | None = None
    formatted_parent_projects: str | None = None
    supplemental_parent_projects: list[dict[str, Any]] | None = None
    formatted_supplemental_parent_projects: str | None = None
    funding_projects: list[dict[str, Any]] | None = None
    formatted_funding_projects: str | None = None
    data_reuse_projects: list[dict[str, Any]] | None = None
    formatted_data_reuse_projects: str | None = None
    programme_projects: list[dict[str, Any]] | None = None
    formatted_programme_projects: str | None = None
    funding_statement: str | None = None
    project_provenance_note: str | None = None
    project_provenance_source: str | None = None
    child_bioprojects: list[str] | None = None
    parent_projects: list[dict[str, Any]] | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    CORE_FIELDS: ClassVar[tuple[str, ...]] = (
        "bioproject",
        "study_title",
        "tax_id",
        "tax_id_umbrella",
        "tolid",
        "assemblies_type",
        "assembly_name",
        "auto_text",
        "distribution_text",
        "barcode_text",
        "formatted_parent_projects",
        "supplemental_parent_projects",
        "formatted_supplemental_parent_projects",
        "funding_projects",
        "formatted_funding_projects",
        "data_reuse_projects",
        "formatted_data_reuse_projects",
        "programme_projects",
        "formatted_programme_projects",
        "funding_statement",
        "project_provenance_note",
        "project_provenance_source",
        "child_bioprojects",
        "parent_projects",
    )
    CORE_FIELD_SET: ClassVar[frozenset[str]] = frozenset(CORE_FIELDS)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None = None) -> "BaseNoteInfo":
        info = cls()
        if mapping:
            info.update(mapping)
        return info

    def update(self, mapping: Mapping[str, Any]) -> None:
        for key, value in mapping.items():
            if key in self.CORE_FIELD_SET:
                setattr(self, key, value)
            else:
                self.extras[key] = value

    def to_context_dict(self) -> dict[str, Any]:
        data = {key: getattr(self, key) for key in self.CORE_FIELDS if getattr(self, key) is not None}
        data.update(self.extras)
        return data
