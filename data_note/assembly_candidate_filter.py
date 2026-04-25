from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from . import taxonomy_mapper
from .models import AssemblyCandidate

AssemblyCandidateInput = AssemblyCandidate | Mapping[str, Any]


@dataclass(slots=True)
class AssemblyCandidateFilter:
    taxonomy_mapper_module: Any | None = None

    def filter_relevant_assemblies(
        self,
        assembly_dicts: list[AssemblyCandidateInput],
        required_tax_id: str,
        *,
        allowed_tax_ids: set[str] | None = None,
    ) -> list[AssemblyCandidate]:
        mapper = self.taxonomy_mapper_module or taxonomy_mapper
        allowed = allowed_tax_ids or mapper.get_allowed_tax_ids(required_tax_id)
        assembly_candidates = self.coerce_candidates(assembly_dicts)
        return [
            assembly
            for assembly in assembly_candidates
            if assembly.tax_id in allowed
            and not mapper.should_exclude_by_name(assembly.assembly_name)
        ]

    @staticmethod
    def coerce_candidates(
        assembly_dicts: list[AssemblyCandidateInput],
    ) -> list[AssemblyCandidate]:
        candidates: list[AssemblyCandidate] = []
        for assembly in assembly_dicts:
            if isinstance(assembly, AssemblyCandidate):
                candidates.append(assembly)
                continue

            accession_key = "assembly_set_accession"
            if "assembly_set_accession" not in assembly and "accession" in assembly:
                accession_key = "accession"
            candidates.append(AssemblyCandidate.from_mapping(assembly, accession_key=accession_key))
        return candidates


__all__ = ["AssemblyCandidateFilter", "AssemblyCandidateInput"]
