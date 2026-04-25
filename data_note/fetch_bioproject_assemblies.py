#! usr/bin/env python3

from __future__ import annotations

from .assembly_candidate_filter import AssemblyCandidateFilter, AssemblyCandidateInput
from .assembly_mode_detector import AssemblyModeDetector
from .assembly_pair_selector import AssemblyPairSelector
from .assembly_selection_resolver import AssemblySelectionResolver
from .bioproject_client import BioprojectClient, EnaPortalClient

__all__ = [
    "AssemblyCandidateFilter",
    "AssemblyCandidateInput",
    "AssemblyModeDetector",
    "AssemblyPairSelector",
    "AssemblySelectionResolver",
    "BioprojectClient",
    "EnaPortalClient",
]


if __name__ == "__main__":
    bioproject = "PRJEB71568"
    print(f"BioProject: {bioproject}")

    bioproject_client = BioprojectClient()
    selection_resolver = AssemblySelectionResolver()
    context: dict[str, str] = {}
    umbrella_data = bioproject_client.fetch_umbrella_project(bioproject)
    umbrella_project_dict = bioproject_client.build_umbrella_project_details(umbrella_data, bioproject)
    tax_id = umbrella_project_dict["tax_id"]
    context.update(umbrella_project_dict)

    child_accessions = bioproject_client.fetch_child_accessions(umbrella_data)
    assembly_candidates = bioproject_client.fetch_assemblies_for_bioprojects(child_accessions)

    selection = selection_resolver.build_selection(assembly_candidates, tax_id)
    context.update(selection.to_context_dict())

    print(f"This is a {selection.assemblies_type} assembly.")
