from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..models import AssemblyRecord, AssemblySelection
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
    ) -> AssemblySelection:
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
        print(f"This is a {assemblies_type} assembly.")

        if assemblies_type == "hap_asm":
            hap1_dict, hap2_dict = self.haplotype_extractor(assembly_dicts, tax_id)
            selection = AssemblySelection(
                assemblies_type="hap_asm",
                hap1=AssemblyRecord.from_legacy_dict(
                    hap1_dict,
                    accession_key="hap1_accession",
                    assembly_name_key="hap1_assembly_name",
                    role="hap1",
                ),
                hap2=AssemblyRecord.from_legacy_dict(
                    hap2_dict,
                    accession_key="hap2_accession",
                    assembly_name_key="hap2_assembly_name",
                    role="hap2",
                ),
            )
        elif assemblies_type == "prim_alt":
            primary_dict, alternate_dict = self.primary_alternate_extractor(
                assembly_dicts,
                tax_id,
                allowed_tax_ids=allowed_tax_ids,
            )
            selection = AssemblySelection(
                assemblies_type="prim_alt",
                primary=AssemblyRecord.from_legacy_dict(
                    primary_dict,
                    accession_key="prim_accession",
                    assembly_name_key="prim_assembly_name",
                    role="primary",
                ),
                alternate=AssemblyRecord.from_legacy_dict(
                    alternate_dict,
                    accession_key="alt_accession",
                    assembly_name_key="alt_assembly_name",
                    role="alternate",
                ),
            )
        elif assemblies_type == "multiple_primary":
            selection = AssemblySelection(
                assemblies_type="multiple_primary",
                extras=self.multiple_extractor(assembly_dicts, tax_id),
            )
        else:
            selection = AssemblySelection(assemblies_type="prim_alt")

        selection.validate()
        return selection

    def _build_override_context(self, bioproject_id: str) -> AssemblySelection:
        override = self.taxonomy_mapper_module.get_assembly_override(bioproject_id)
        print(f"  → Using manual assembly override for {bioproject_id}")
        print(f"    Reason: {override.get('reason')}")

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
