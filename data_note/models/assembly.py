from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AssemblyMode = Literal["prim_alt", "hap_asm", "multiple_primary"]
AssemblyRole = Literal["primary", "alternate", "hap1", "hap2"]


@dataclass(slots=True)
class AssemblyRecord:
    accession: str
    assembly_name: str
    role: AssemblyRole

    @classmethod
    def from_legacy_dict(
        cls,
        data: dict[str, Any],
        *,
        accession_key: str,
        assembly_name_key: str,
        role: AssemblyRole,
    ) -> "AssemblyRecord | None":
        accession = data.get(accession_key)
        assembly_name = data.get(assembly_name_key)
        if not accession and not assembly_name:
            return None
        return cls(
            accession=str(accession or ""),
            assembly_name=str(assembly_name or ""),
            role=role,
        )

    def validate(self) -> None:
        if not self.accession:
            raise ValueError(f"{self.role} assembly is missing an accession")
        if not self.assembly_name:
            raise ValueError(f"{self.role} assembly is missing an assembly name")


@dataclass(slots=True)
class AssemblySelection:
    assemblies_type: AssemblyMode
    primary: AssemblyRecord | None = None
    alternate: AssemblyRecord | None = None
    hap1: AssemblyRecord | None = None
    hap2: AssemblyRecord | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.assemblies_type == "prim_alt":
            if self.primary is not None:
                self.primary.validate()
            if self.alternate is not None:
                self.alternate.validate()
        elif self.assemblies_type == "hap_asm":
            if self.hap1 is not None:
                self.hap1.validate()
            if self.hap2 is not None:
                self.hap2.validate()

    def to_context_dict(self) -> dict[str, Any]:
        context = {"assemblies_type": self.assemblies_type, **self.extras}
        if self.primary is not None:
            context["prim_accession"] = self.primary.accession
            context["prim_assembly_name"] = self.primary.assembly_name
        if self.alternate is not None:
            context["alt_accession"] = self.alternate.accession
            context["alt_assembly_name"] = self.alternate.assembly_name
        if self.hap1 is not None:
            context["hap1_accession"] = self.hap1.accession
            context["hap1_assembly_name"] = self.hap1.assembly_name
        if self.hap2 is not None:
            context["hap2_accession"] = self.hap2.accession
            context["hap2_assembly_name"] = self.hap2.assembly_name
        return context

    def assembly_accessions(self) -> dict[str, str | None]:
        return {
            "prim_accession": self.primary.accession if self.primary is not None else None,
            "hap1_accession": self.hap1.accession if self.hap1 is not None else None,
            "hap2_accession": self.hap2.accession if self.hap2 is not None else None,
        }
