from __future__ import annotations

from typing import Any

from .assembly_selection_resolver import AssemblySelectionResolver
from .bioproject_client import BioprojectClient


def _portal_client() -> BioprojectClient:
    return BioprojectClient()


def _selection_resolver() -> AssemblySelectionResolver:
    return AssemblySelectionResolver()


def fetch_data(bioproject_id: str) -> dict[str, Any] | None:
    return _portal_client().fetch_umbrella_project(bioproject_id)


def get_umbrella_project_details(umbrella_data: dict[str, Any] | None, bioproject_id: str) -> dict[str, str]:
    return BioprojectClient.build_umbrella_project_details(umbrella_data, bioproject_id)


def get_child_accessions_for_bioproject(umbrella_data: dict[str, Any] | None) -> list[str]:
    return _portal_client().fetch_child_accessions(umbrella_data)


def fetch_and_update_assembly_details(bioproject: str) -> list[dict[str, Any]] | None:
    assemblies = _portal_client().fetch_and_update_assembly_details(bioproject)
    if assemblies is None:
        return None
    return [assembly.to_mapping() for assembly in assemblies]


def fetch_assembly_details(bioproject: str) -> list[dict[str, Any]] | None:
    assemblies = _portal_client().fetch_assembly_details(bioproject)
    if assemblies is None:
        return None
    return [assembly.to_mapping() for assembly in assemblies]


def determine_assembly_type(
    assembly_dicts: list[dict[str, Any]],
    required_tax_id: str,
) -> str:
    return _selection_resolver().determine_assembly_type(assembly_dicts, required_tax_id)


def extract_prim_alt_assemblies(
    assembly_dicts: list[dict[str, Any]],
    tax_id: str,
    allowed_tax_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _selection_resolver().extract_prim_alt_assemblies(
        assembly_dicts,
        tax_id,
        allowed_tax_ids=allowed_tax_ids,
    )


def extract_haplotype_assemblies(
    assembly_dicts: list[dict[str, Any]],
    tax_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _selection_resolver().extract_haplotype_assemblies(assembly_dicts, tax_id)


def extract_multiple_assemblies(assembly_dicts: list[dict[str, Any]], tax_id: str) -> dict[str, Any]:
    return _selection_resolver().extract_multiple_assemblies(assembly_dicts, tax_id)


def get_parent_bioprojects(bioproject_id: str) -> dict[str, Any]:
    return _portal_client().fetch_parent_projects(bioproject_id)


__all__ = [
    "determine_assembly_type",
    "extract_haplotype_assemblies",
    "extract_multiple_assemblies",
    "extract_prim_alt_assemblies",
    "fetch_and_update_assembly_details",
    "fetch_assembly_details",
    "fetch_data",
    "get_child_accessions_for_bioproject",
    "get_parent_bioprojects",
    "get_umbrella_project_details",
]
