from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import taxonomy_mapper
from .assembly_candidate_filter import AssemblyCandidateFilter, AssemblyCandidateInput
from .assembly_mode_detector import AssemblyModeDetector
from .assembly_pair_selector import AssemblyPairSelector
from .models import AssemblyCandidate, AssemblySelection, AssemblySelectionInput


@dataclass(slots=True)
class AssemblySelectionResolver:
    taxonomy_mapper_module: Any | None = None
    candidate_filter: AssemblyCandidateFilter = field(default_factory=AssemblyCandidateFilter)
    mode_detector: AssemblyModeDetector = field(default_factory=AssemblyModeDetector)
    pair_selector: AssemblyPairSelector = field(default_factory=AssemblyPairSelector)
    contiguity_fetcher: Callable[[str], dict[str, Any] | None] | None = None

    def filter_relevant_assemblies(
        self,
        assembly_dicts: list[AssemblyCandidateInput],
        required_tax_id: str,
        *,
        allowed_tax_ids: set[str] | None = None,
    ) -> list[AssemblyCandidate]:
        return self._candidate_filter().filter_relevant_assemblies(
            assembly_dicts,
            required_tax_id,
            allowed_tax_ids=allowed_tax_ids,
        )

    def determine_assembly_type(
        self,
        assembly_dicts: list[AssemblyCandidateInput],
        required_tax_id: str,
        *,
        allowed_tax_ids: set[str] | None = None,
    ) -> str:
        relevant_assemblies = self.filter_relevant_assemblies(
            assembly_dicts,
            required_tax_id,
            allowed_tax_ids=allowed_tax_ids,
        )
        return self.mode_detector.detect(relevant_assemblies)

    def build_selection(
        self,
        assembly_dicts: list[AssemblyCandidateInput],
        tax_id: str,
        selection_input: AssemblySelectionInput | None = None,
    ) -> AssemblySelection:
        allowed_tax_ids = (self.taxonomy_mapper_module or taxonomy_mapper).get_allowed_tax_ids(tax_id)
        relevant_assemblies = self.filter_relevant_assemblies(
            assembly_dicts,
            tax_id,
            allowed_tax_ids=allowed_tax_ids,
        )
        if selection_input is not None and selection_input.has_any():
            selection = self._build_selection_from_input(relevant_assemblies, selection_input)
            selection.validate()
            return selection

        assemblies_type = self.mode_detector.detect(relevant_assemblies)

        if assemblies_type == "hap_asm":
            hap1_record, hap2_record = self._pair_selector().select_haplotype_records(relevant_assemblies)
            selection = AssemblySelection(
                assemblies_type="hap_asm",
                hap1=hap1_record,
                hap2=hap2_record,
            )
        elif assemblies_type == "prim_alt":
            primary_record, alternate_record = self._pair_selector().select_prim_alt_records(relevant_assemblies)
            selection = AssemblySelection(
                assemblies_type="prim_alt",
                primary=primary_record,
                alternate=alternate_record,
            )
        elif assemblies_type == "multiple_primary":
            selection = AssemblySelection(
                assemblies_type="multiple_primary",
                extras=self.extract_multiple_assemblies(assembly_dicts, tax_id),
            )
        else:
            selection = AssemblySelection(assemblies_type="prim_alt")

        selection.validate()
        return selection

    def _build_selection_from_input(
        self,
        relevant_assemblies: list[AssemblyCandidate],
        selection_input: AssemblySelectionInput,
    ) -> AssemblySelection:
        selection_input.validate()

        if selection_input.hap1_accession:
            hap1_record, hap2_record = self._pair_selector().select_haplotype_records_from_hap1(
                relevant_assemblies,
                selection_input.hap1_accession,
                hap2_accession=selection_input.hap2_accession,
            )
            return AssemblySelection(
                assemblies_type="hap_asm",
                hap1=hap1_record,
                hap2=hap2_record,
            )

        if selection_input.assembly_accession:
            candidate = self._find_candidate(relevant_assemblies, selection_input.assembly_accession)
            lower_name = candidate.assembly_name.lower()
            if "alternate haplotype" in lower_name:
                raise ValueError(
                    "The assembly input must point to a primary assembly or haplotype 1 assembly, not an alternate haplotype"
                )
            if "hap2" in lower_name:
                raise ValueError(
                    "The assembly input must point to a primary assembly or haplotype 1 assembly, not haplotype 2"
                )
            if "hap1" in lower_name:
                hap1_record, hap2_record = self._pair_selector().select_haplotype_records_from_hap1(
                    relevant_assemblies,
                    selection_input.assembly_accession,
                    hap2_accession=selection_input.hap2_accession,
                )
                return AssemblySelection(
                    assemblies_type="hap_asm",
                    hap1=hap1_record,
                    hap2=hap2_record,
                )
            primary_record, alternate_record = self._pair_selector().select_prim_alt_records_from_primary(
                relevant_assemblies,
                selection_input.assembly_accession,
                alternate_accession=selection_input.alternate_accession,
            )
            return AssemblySelection(
                assemblies_type="prim_alt",
                primary=primary_record,
                alternate=alternate_record,
            )

        raise ValueError("Assembly selection input did not contain a usable assembly accession")

    def extract_prim_alt_assemblies(
        self,
        assembly_dicts: list[AssemblyCandidateInput],
        tax_id: str,
        *,
        allowed_tax_ids: set[str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        relevant_assemblies = self.filter_relevant_assemblies(
            assembly_dicts,
            tax_id,
            allowed_tax_ids=allowed_tax_ids,
        )
        primary_record, alternate_record = self._pair_selector().select_prim_alt_records(relevant_assemblies)
        primary_assembly_dict: dict[str, Any] = {}
        alternate_haplotype_dict: dict[str, Any] = {}
        if primary_record is not None:
            primary_assembly_dict = {
                "prim_accession": primary_record.accession,
                "prim_assembly_name": primary_record.assembly_name,
            }
        if alternate_record is not None:
            alternate_haplotype_dict = {
                "alt_accession": alternate_record.accession,
                "alt_assembly_name": alternate_record.assembly_name,
            }
        return primary_assembly_dict, alternate_haplotype_dict

    def extract_haplotype_assemblies(
        self,
        assembly_dicts: list[AssemblyCandidateInput],
        tax_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        relevant_assemblies = self.filter_relevant_assemblies(assembly_dicts, tax_id)
        hap1_record, hap2_record = self._pair_selector().select_haplotype_records(relevant_assemblies)
        hap1_dict: dict[str, Any] = {}
        hap2_dict: dict[str, Any] = {}
        if hap1_record is not None:
            hap1_dict = {
                "hap1_accession": hap1_record.accession,
                "hap1_assembly_name": hap1_record.assembly_name,
            }
        if hap2_record is not None:
            hap2_dict = {
                "hap2_accession": hap2_record.accession,
                "hap2_assembly_name": hap2_record.assembly_name,
            }
        return hap1_dict, hap2_dict

    @staticmethod
    def extract_multiple_assemblies(assembly_dicts: list[AssemblyCandidateInput], tax_id: str) -> dict[str, Any]:
        del assembly_dicts
        del tax_id
        return {"multiple_assemblies_info": "Placeholder for multiple assemblies extraction."}

    def _pair_selector(self) -> AssemblyPairSelector:
        if self.contiguity_fetcher is not None:
            self.pair_selector.contiguity_fetcher = self.contiguity_fetcher
        return self.pair_selector

    def _candidate_filter(self) -> AssemblyCandidateFilter:
        if self.candidate_filter.taxonomy_mapper_module is None:
            self.candidate_filter.taxonomy_mapper_module = self.taxonomy_mapper_module
        return self.candidate_filter

    @staticmethod
    def _find_candidate(
        relevant_assemblies: list[AssemblyCandidate],
        accession: str,
    ) -> AssemblyCandidate:
        normalized = accession.strip()
        for candidate in relevant_assemblies:
            if candidate.accession == normalized:
                return candidate
        raise ValueError(f"Requested assembly {normalized} was not found among the relevant assemblies")


__all__ = ["AssemblySelectionResolver"]
