from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..project_provenance import format_project_list, project_accession, split_parent_projects


@dataclass(slots=True)
class NoteContext(MutableMapping[str, Any]):
    bioproject: str | None = None
    tax_id: str | None = None
    tax_id_umbrella: str | None = None
    species: str | None = None
    tolid: str | None = None
    assemblies_type: str | None = None
    assembly_name: str | None = None
    jira: str | None = None
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
        "tax_id",
        "tax_id_umbrella",
        "species",
        "tolid",
        "assemblies_type",
        "assembly_name",
        "jira",
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

    def __getitem__(self, key: str) -> Any:
        if key in self.CORE_FIELD_SET:
            value = getattr(self, key)
            if value is None:
                raise KeyError(key)
            return value
        return self.extras[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.CORE_FIELD_SET:
            setattr(self, key, value)
            return
        self.extras[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self.CORE_FIELD_SET:
            if getattr(self, key) is None:
                raise KeyError(key)
            setattr(self, key, None)
            return
        del self.extras[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    @classmethod
    def from_mapping(cls, mapping: MutableMapping[str, Any] | dict[str, Any]) -> "NoteContext":
        context = cls()
        context.update(mapping)
        return context

    def to_dict(self) -> dict[str, Any]:
        data = {key: getattr(self, key) for key in self.CORE_FIELDS if getattr(self, key) is not None}
        data.update(self.extras)
        return data

    def copy(self) -> dict[str, Any]:
        return self.to_dict()

    def assembly_accessions(self) -> dict[str, Any]:
        return {
            "prim_accession": self.get("prim_accession"),
            "alt_accession": self.get("alt_accession"),
            "hap1_accession": self.get("hap1_accession"),
            "hap2_accession": self.get("hap2_accession"),
        }

    def current_accession(self) -> str | None:
        return self.get("prim_accession") or self.get("hap1_accession") or self.get("accession")

    def ensure_tolid(self) -> None:
        if self.tolid:
            return
        assembly_name = self.assembly_name or self.get("hap1_assembly_name") or self.get("prim_assembly_name")
        if assembly_name:
            self.tolid = assembly_name.split(".", 1)[0]

    def set_formatted_parent_projects(
        self,
        default_text: str = "the Sanger Institute Tree of Life Programme (PRJEB43745)",
    ) -> None:
        parent_projects = self.parent_projects or []
        if parent_projects:
            explicit_accessions = {
                project_accession(project)
                for project in (self.funding_projects or []) + (self.programme_projects or [])
            }
            primary_projects, supplemental_projects = split_parent_projects(
                parent_projects,
                explicit_project_accessions=explicit_accessions,
            )
            if supplemental_projects:
                self.supplemental_parent_projects = supplemental_projects
                self.formatted_supplemental_parent_projects = format_project_list(supplemental_projects)
            if primary_projects:
                self.formatted_parent_projects = format_project_list(primary_projects)
            else:
                self.formatted_parent_projects = default_text
            return
        self.formatted_parent_projects = default_text
