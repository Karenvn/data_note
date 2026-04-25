from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from . import taxonomy_mapper
from .assembly_selection_resolver import AssemblySelectionResolver
from .models import AssemblyCandidate, AssemblyRecord, AssemblySelection, AssemblySelectionInput

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AssemblyOverrideResolver:
    taxonomy_mapper_module: Any = taxonomy_mapper
    selection_input: AssemblySelectionInput | None = None

    def has_override(self, bioproject_id: str | None) -> bool:
        return self.has_runtime_override() or self.has_mapper_override(bioproject_id)

    def has_runtime_override(self) -> bool:
        return self.selection_input is not None and self.selection_input.has_any()

    def has_mapper_override(self, bioproject_id: str | None) -> bool:
        return self.taxonomy_mapper_module.has_assembly_override(bioproject_id)

    def resolve(
        self,
        *,
        bioproject_id: str | None,
        assembly_candidates: list[AssemblyCandidate],
        tax_id: str,
        selection_resolver: AssemblySelectionResolver,
    ) -> AssemblySelection | None:
        if self.has_runtime_override():
            logger.info("Using runtime assembly selection override for %s", bioproject_id)
            return selection_resolver.build_selection(
                assembly_candidates,
                tax_id,
                selection_input=self.selection_input,
            )

        if bioproject_id and self.has_mapper_override(bioproject_id):
            return self.build_selection(bioproject_id)
        return None

    def build_selection(self, bioproject_id: str) -> AssemblySelection:
        override = self.taxonomy_mapper_module.get_assembly_override(bioproject_id)
        logger.info(
            "Using manual assembly override for %s (%s)",
            bioproject_id,
            override.get("reason"),
        )

        selection = AssemblySelection(assemblies_type="prim_alt")
        if "primary" in override:
            selection.primary = AssemblyRecord(
                accession=override["primary"]["accession"],
                assembly_name=override["primary"]["name"],
                role="primary",
            )
        if "alternate" in override:
            selection.alternate = AssemblyRecord(
                accession=override["alternate"]["accession"],
                assembly_name=override["alternate"]["name"],
                role="alternate",
            )
        if "hap1" in override:
            selection.assemblies_type = "hap_asm"
            selection.hap1 = AssemblyRecord(
                accession=override["hap1"]["accession"],
                assembly_name=override["hap1"]["name"],
                role="hap1",
            )
        if "hap2" in override:
            selection.hap2 = AssemblyRecord(
                accession=override["hap2"]["accession"],
                assembly_name=override["hap2"]["name"],
                role="hap2",
            )
        selection.validate()
        return selection


__all__ = ["AssemblyOverrideResolver"]
