from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

from .fetch_ncbi_data import fetch_prim_assembly_info
from .models import AssemblyCandidate, AssemblyRecord

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AssemblyPairSelector:
    contiguity_fetcher: Callable[[str], dict[str, Any] | None] | None = None
    _contiguity_cache: dict[str, dict[str, Any]] | None = None

    def select_prim_alt_records(
        self,
        relevant_assemblies: list[AssemblyCandidate],
    ) -> tuple[AssemblyRecord | None, AssemblyRecord | None]:
        primary_candidates = [
            assembly for assembly in relevant_assemblies if not self._is_alternate_haplotype_name(assembly.assembly_name)
        ]
        alternate_candidates = [
            assembly for assembly in relevant_assemblies if self._is_alternate_haplotype_name(assembly.assembly_name)
        ]

        chosen_primary = self._select_best_primary_like_candidate(primary_candidates)
        if chosen_primary is None:
            return None, None

        matching_alternates = self._find_matching_candidates(
            chosen_primary,
            alternate_candidates,
            assemblies_type="prim_alt",
        )
        chosen_alternate = self._select_best_primary_like_candidate(matching_alternates)
        primary_record = chosen_primary.to_record(
            "primary",
            assembly_name=chosen_primary.assembly_name.replace("alternate haplotype", "").strip(),
        )
        alternate_record = chosen_alternate.to_record("alternate") if chosen_alternate is not None else None
        return primary_record, alternate_record

    def select_prim_alt_records_from_primary(
        self,
        relevant_assemblies: list[AssemblyCandidate],
        primary_accession: str,
        *,
        alternate_accession: str | None = None,
    ) -> tuple[AssemblyRecord | None, AssemblyRecord | None]:
        primary_candidates = [
            assembly for assembly in relevant_assemblies if not self._is_alternate_haplotype_name(assembly.assembly_name)
        ]
        alternate_candidates = [
            assembly for assembly in relevant_assemblies if self._is_alternate_haplotype_name(assembly.assembly_name)
        ]

        chosen_primary = self._candidate_by_accession(primary_candidates, primary_accession, role="primary")
        chosen_alternate = self._resolve_matching_candidate(
            chosen_primary,
            alternate_candidates,
            assemblies_type="prim_alt",
            explicit_accession=alternate_accession,
            explicit_role="alternate",
        )
        primary_record = chosen_primary.to_record(
            "primary",
            assembly_name=chosen_primary.assembly_name.replace("alternate haplotype", "").strip(),
        )
        alternate_record = chosen_alternate.to_record("alternate") if chosen_alternate is not None else None
        return primary_record, alternate_record

    def select_haplotype_records(
        self,
        relevant_assemblies: list[AssemblyCandidate],
    ) -> tuple[AssemblyRecord | None, AssemblyRecord | None]:
        hap1_candidates = [
            assembly for assembly in relevant_assemblies if self._is_haplotype_label(assembly.assembly_name, "hap1")
        ]
        hap2_candidates = [
            assembly for assembly in relevant_assemblies if self._is_haplotype_label(assembly.assembly_name, "hap2")
        ]

        chosen_hap1 = self._select_best_primary_like_candidate(hap1_candidates)
        if chosen_hap1 is None:
            return None, None

        matching_hap2 = self._find_matching_candidates(
            chosen_hap1,
            hap2_candidates,
            assemblies_type="hap_asm",
        )
        chosen_hap2 = self._select_best_primary_like_candidate(matching_hap2)
        if chosen_hap2 is None and len(hap2_candidates) == 1:
            chosen_hap2 = hap2_candidates[0]
        hap1_record = chosen_hap1.to_record("hap1")
        hap2_record = chosen_hap2.to_record("hap2") if chosen_hap2 is not None else None
        return hap1_record, hap2_record

    def select_haplotype_records_from_hap1(
        self,
        relevant_assemblies: list[AssemblyCandidate],
        hap1_accession: str,
        *,
        hap2_accession: str | None = None,
    ) -> tuple[AssemblyRecord | None, AssemblyRecord | None]:
        hap1_candidates = [
            assembly for assembly in relevant_assemblies if self._is_haplotype_label(assembly.assembly_name, "hap1")
        ]
        hap2_candidates = [
            assembly for assembly in relevant_assemblies if self._is_haplotype_label(assembly.assembly_name, "hap2")
        ]

        chosen_hap1 = self._candidate_by_accession(hap1_candidates, hap1_accession, role="hap1")
        chosen_hap2 = self._resolve_matching_candidate(
            chosen_hap1,
            hap2_candidates,
            assemblies_type="hap_asm",
            explicit_accession=hap2_accession,
            explicit_role="hap2",
        )
        hap1_record = chosen_hap1.to_record("hap1")
        hap2_record = chosen_hap2.to_record("hap2") if chosen_hap2 is not None else None
        return hap1_record, hap2_record

    def _select_best_primary_like_candidate(
        self,
        candidates: list[AssemblyCandidate],
    ) -> AssemblyCandidate | None:
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        return max(candidates, key=self._candidate_rank)

    def _candidate_rank(self, candidate: AssemblyCandidate) -> tuple[int, float, float, tuple[int, int]]:
        accession = candidate.accession
        metrics = self._fetch_contiguity_metrics(accession)
        assembly_level = str(metrics.get("assembly_level") or "").lower()
        scaffold_n50 = self._as_float(metrics.get("scaffold_N50"))
        contig_n50 = self._as_float(metrics.get("contig_N50"))
        return (
            self._assembly_level_rank(assembly_level),
            scaffold_n50,
            contig_n50,
            self._accession_sort_key(accession),
        )

    def _fetch_contiguity_metrics(self, accession: str) -> dict[str, Any]:
        if not accession:
            return {}
        if self._contiguity_cache is None:
            self._contiguity_cache = {}
        if accession in self._contiguity_cache:
            return self._contiguity_cache[accession]

        fetcher = self.contiguity_fetcher or fetch_prim_assembly_info
        try:
            metrics = fetcher(accession) or {}
        except Exception as exc:
            logger.warning("Failed to fetch contiguity metrics for %s: %s", accession, exc)
            metrics = {}
        self._contiguity_cache[accession] = metrics
        return metrics

    def _find_matching_candidates(
        self,
        selected_candidate: AssemblyCandidate,
        candidates: list[AssemblyCandidate],
        *,
        assemblies_type: str,
    ) -> list[AssemblyCandidate]:
        if not candidates:
            return []

        selected_accession = selected_candidate.accession
        selected_metrics = self._fetch_contiguity_metrics(selected_accession)
        selected_links = set(self._linked_assemblies(selected_metrics))
        if selected_links:
            linked_matches = []
            for candidate in candidates:
                candidate_accession = candidate.accession
                candidate_metrics = self._fetch_contiguity_metrics(candidate_accession)
                candidate_links = set(self._linked_assemblies(candidate_metrics))
                if candidate_accession in selected_links or selected_accession in candidate_links:
                    linked_matches.append(candidate)
            if linked_matches:
                return linked_matches

        pair_key = self._pair_key(selected_candidate.assembly_name, assemblies_type=assemblies_type)
        return [
            candidate
            for candidate in candidates
            if self._pair_key(candidate.assembly_name, assemblies_type=assemblies_type) == pair_key
        ]

    def _resolve_matching_candidate(
        self,
        selected_candidate: AssemblyCandidate,
        candidates: list[AssemblyCandidate],
        *,
        assemblies_type: str,
        explicit_accession: str | None,
        explicit_role: str,
    ) -> AssemblyCandidate | None:
        if explicit_accession:
            return self._candidate_by_accession(candidates, explicit_accession, role=explicit_role)
        matching_candidates = self._find_matching_candidates(
            selected_candidate,
            candidates,
            assemblies_type=assemblies_type,
        )
        chosen_candidate = self._select_best_primary_like_candidate(matching_candidates)
        if chosen_candidate is None and len(candidates) == 1:
            return candidates[0]
        return chosen_candidate

    @staticmethod
    def _candidate_by_accession(
        candidates: list[AssemblyCandidate],
        accession: str,
        *,
        role: str,
    ) -> AssemblyCandidate:
        normalized = accession.strip()
        for candidate in candidates:
            if candidate.accession == normalized:
                return candidate
        raise ValueError(f"Requested {role} assembly {normalized} was not found among the relevant assemblies")

    @staticmethod
    def _assembly_level_rank(level: str) -> int:
        level_map = {
            "complete genome": 5,
            "chromosome": 4,
            "scaffold": 3,
            "contig": 2,
        }
        return level_map.get(level, 0)

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _accession_sort_key(accession: str) -> tuple[int, int]:
        if "_" not in accession:
            return (0, 0)
        _, tail = accession.split("_", 1)
        core, _, version = tail.partition(".")
        try:
            return (int(core), int(version or 0))
        except ValueError:
            return (0, 0)

    @staticmethod
    def _is_alternate_haplotype_name(name: str) -> bool:
        return "alternate haplotype" in name.lower()

    @staticmethod
    def _is_haplotype_label(name: str, label: str) -> bool:
        return label in name.lower()

    @staticmethod
    def _linked_assemblies(metrics: dict[str, Any]) -> list[str]:
        linked = metrics.get("linked_assemblies", [])
        if not isinstance(linked, list):
            return []
        return [str(accession) for accession in linked if accession]

    @classmethod
    def _pair_key(cls, name: str, *, assemblies_type: str) -> str:
        lower = name.lower().strip()
        if assemblies_type == "prim_alt":
            return lower.replace(" alternate haplotype", "").strip()
        if assemblies_type == "hap_asm":
            for token in ("hap1", "hap2"):
                lower = lower.replace(token, "")
            return " ".join(lower.replace("..", ".").split())
        return lower


__all__ = ["AssemblyPairSelector"]
