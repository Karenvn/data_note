from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Any, ClassVar


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
    formatted_parent_projects: str | None = None
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
        "formatted_parent_projects",
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

    def apply_known_tolid_fix(self, known_fixes: dict[str, str]) -> None:
        current_accession = self.current_accession()
        fixed_tolid = known_fixes.get(current_accession)
        if fixed_tolid:
            print(f"Overriding ToLID for {current_accession} -> {fixed_tolid} (NCBI mislabel).")
            self.tolid = fixed_tolid

    def set_formatted_parent_projects(
        self,
        default_text: str = "the Sanger Institute Tree of Life Programme (PRJEB43745)",
    ) -> None:
        parent_projects = self.parent_projects or []
        if parent_projects:
            formatted_list = [f"{proj['project_name']} ({proj['accession']})" for proj in parent_projects]
            if len(formatted_list) == 1:
                self.formatted_parent_projects = formatted_list[0]
            elif len(formatted_list) == 2:
                self.formatted_parent_projects = " and ".join(formatted_list)
            else:
                self.formatted_parent_projects = ", ".join(formatted_list[:-1]) + " and " + formatted_list[-1]
            return
        self.formatted_parent_projects = default_text
