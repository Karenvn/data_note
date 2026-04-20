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
    formatted_parent_projects: str | None = None
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
        "formatted_parent_projects",
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
