from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import logging

from ..assembly_override_resolver import AssemblyOverrideResolver
from ..assembly_selection_resolver import AssemblySelectionResolver
from ..bioproject_client import BioprojectClient
from ..models import AssemblySelection, AssemblySelectionInput
from .. import taxonomy_mapper

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AssemblyService:
    bioproject_client: BioprojectClient = field(default_factory=BioprojectClient)
    selection_resolver: AssemblySelectionResolver = field(default_factory=AssemblySelectionResolver)
    override_resolver: AssemblyOverrideResolver = field(default_factory=AssemblyOverrideResolver)
    taxonomy_mapper_module: Any = taxonomy_mapper
    selection_input: AssemblySelectionInput | None = None

    def build_context(
        self,
        umbrella_data: dict[str, Any],
        tax_id: str,
        child_accessions: list[str] | None = None,
    ) -> AssemblySelection:
        bioproject_id = umbrella_data.get("study_accession")
        override_resolver = self._override_resolver()
        if not override_resolver.has_runtime_override() and override_resolver.has_mapper_override(bioproject_id):
            return override_resolver.build_selection(bioproject_id)

        if child_accessions is None:
            child_accessions = self.bioproject_client.fetch_child_accessions(umbrella_data)

        assembly_candidates = self.bioproject_client.fetch_assemblies_for_bioprojects(child_accessions)
        resolver = self._resolver()
        override_selection = override_resolver.resolve(
            bioproject_id=bioproject_id,
            assembly_candidates=assembly_candidates,
            tax_id=tax_id,
            selection_resolver=resolver,
        )
        if override_selection is not None:
            return override_selection

        selection = resolver.build_selection(assembly_candidates, tax_id)
        logger.info("Detected %s assembly type.", selection.assemblies_type)
        return selection

    def _resolver(self) -> AssemblySelectionResolver:
        if self.selection_resolver.taxonomy_mapper_module is None:
            self.selection_resolver.taxonomy_mapper_module = self.taxonomy_mapper_module
        return self.selection_resolver

    def _override_resolver(self) -> AssemblyOverrideResolver:
        if self.override_resolver.taxonomy_mapper_module is taxonomy_mapper:
            self.override_resolver.taxonomy_mapper_module = self.taxonomy_mapper_module
        if self.selection_input is not None:
            self.override_resolver.selection_input = self.selection_input
        return self.override_resolver
