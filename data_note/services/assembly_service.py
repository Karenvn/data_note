from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .. import taxonomy_mapper
from ..fetch_bioproject_assemblies import (
    determine_assembly_type,
    extract_haplotype_assemblies,
    extract_multiple_assemblies,
    extract_prim_alt_assemblies,
    fetch_and_update_assembly_details,
    get_child_accessions_for_bioproject,
)


@dataclass(slots=True)
class AssemblyService:
    child_accessions_getter: Callable[[dict[str, Any]], list[str]] = get_child_accessions_for_bioproject
    assembly_details_fetcher: Callable[[str], list[dict[str, Any]] | None] = fetch_and_update_assembly_details
    assembly_type_resolver: Callable[[list[dict[str, Any]], str], str] = determine_assembly_type
    haplotype_extractor: Callable[[list[dict[str, Any]], str], tuple[dict[str, Any], dict[str, Any]]] = extract_haplotype_assemblies
    primary_alternate_extractor: Callable[[list[dict[str, Any]], str], tuple[dict[str, Any], dict[str, Any]]] = extract_prim_alt_assemblies
    multiple_extractor: Callable[[list[dict[str, Any]], str], dict[str, Any]] = extract_multiple_assemblies
    taxonomy_mapper_module: Any = taxonomy_mapper

    def build_context(
        self,
        umbrella_data: dict[str, Any],
        tax_id: str,
        child_accessions: list[str] | None = None,
    ) -> dict[str, Any]:
        assembly_context: dict[str, Any] = {}
        bioproject_id = umbrella_data.get("study_accession")

        if self.taxonomy_mapper_module.has_assembly_override(bioproject_id):
            return self._build_override_context(bioproject_id)

        if child_accessions is None:
            child_accessions = self.child_accessions_getter(umbrella_data)

        allowed_tax_ids = self.taxonomy_mapper_module.get_allowed_tax_ids(tax_id)
        assembly_dicts = [
            assembly
            for bioproject in child_accessions
            for assembly in (self.assembly_details_fetcher(bioproject) or [])
            if assembly.get("tax_id") in allowed_tax_ids
            and not self.taxonomy_mapper_module.should_exclude_by_name(assembly.get("assembly_name", ""))
        ]

        assemblies_type = self.assembly_type_resolver(assembly_dicts, tax_id)
        assembly_context["assemblies_type"] = assemblies_type
        print(f"This is a {assemblies_type} assembly.")

        if assemblies_type == "hap_asm":
            hap1_dict, hap2_dict = self.haplotype_extractor(assembly_dicts, tax_id)
            assembly_context.update(hap1_dict)
            assembly_context.update(hap2_dict)
        elif assemblies_type == "prim_alt":
            primary_dict, alternate_dict = self.primary_alternate_extractor(
                assembly_dicts,
                tax_id,
                allowed_tax_ids=allowed_tax_ids,
            )
            assembly_context.update(primary_dict)
            assembly_context.update(alternate_dict)
        elif assemblies_type == "multiple_primary":
            assembly_context.update(self.multiple_extractor(assembly_dicts, tax_id))

        return assembly_context

    def _build_override_context(self, bioproject_id: str) -> dict[str, Any]:
        override = self.taxonomy_mapper_module.get_assembly_override(bioproject_id)
        print(f"  → Using manual assembly override for {bioproject_id}")
        print(f"    Reason: {override.get('reason')}")

        assembly_context: dict[str, Any] = {"assemblies_type": "prim_alt"}
        if "primary" in override:
            assembly_context["prim_accession"] = override["primary"]["accession"]
            assembly_context["prim_assembly_name"] = override["primary"]["name"]
        if "alternate" in override:
            assembly_context["alt_accession"] = override["alternate"]["accession"]
            assembly_context["alt_assembly_name"] = override["alternate"]["name"]
        if "hap1" in override:
            assembly_context["assemblies_type"] = "hap_asm"
            assembly_context["hap1_accession"] = override["hap1"]["accession"]
            assembly_context["hap1_assembly_name"] = override["hap1"]["name"]
        if "hap2" in override:
            assembly_context["hap2_accession"] = override["hap2"]["accession"]
            assembly_context["hap2_assembly_name"] = override["hap2"]["name"]
        return assembly_context
