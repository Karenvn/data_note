from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GbifTaxonomyClient:
    request_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def fetch_species_metadata(
        self,
        species_name: str,
        tax_id: str | None = None,
    ) -> dict[str, Any]:
        metadata = {
            "tax_auth": "",
            "common_name": "",
            "gbif_url": "",
            "gbif_usage_key": "",
            "gbif_match_strategy": "GBIF_NOT_FOUND",
        }

        parts = species_name.split(" ")
        if len(parts) != 2:
            return metadata
        genus, specific_epithet = parts

        match = self._match_species(genus, specific_epithet)
        if self._is_exact_species_match(match, species_name):
            usage_key = match.get("usageKey")
            if usage_key:
                species_record = self._fetch_species_record(usage_key)
                metadata.update(
                    self._build_metadata_from_records(
                        species_name,
                        primary_record=species_record,
                        supporting_record=match,
                        strategy="GBIF_MATCH_EXACT",
                    )
                )
                return metadata

        candidates = self._search_exact_species(species_name)
        if not candidates:
            return metadata

        primary_candidate = self._select_primary_candidate(candidates, tax_id)
        supporting_candidate = self._select_supporting_candidate(candidates)
        if primary_candidate is None:
            return metadata

        usage_key = primary_candidate.get("key") or primary_candidate.get("usageKey")
        species_record = self._fetch_species_record(usage_key) if usage_key else {}
        metadata.update(
            self._build_metadata_from_records(
                species_name,
                primary_record=species_record,
                supporting_record=supporting_candidate or primary_candidate,
                strategy="GBIF_SEARCH_EXACT",
            )
        )
        return metadata

    def _match_species(self, genus: str, specific_epithet: str) -> dict[str, Any]:
        response = self.request_get(
            "https://api.gbif.org/v1/species/match",
            params={
                "strict": "true",
                "genus": genus,
                "specificEpithet": specific_epithet,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json() or {}

    def _search_exact_species(self, species_name: str) -> list[dict[str, Any]]:
        response = self.request_get(
            "https://api.gbif.org/v1/species/search",
            params={
                "q": species_name,
                "rank": "SPECIES",
                "limit": 20,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json() or {}
        target = species_name.strip().lower()
        results = data.get("results", [])
        return [
            result
            for result in results
            if str(result.get("canonicalName") or "").strip().lower() == target
            and str(result.get("rank") or "").upper() == "SPECIES"
        ]

    def _fetch_species_record(self, usage_key: int | str) -> dict[str, Any]:
        response = self.request_get(
            f"https://api.gbif.org/v1/species/{usage_key}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json() or {}

    def _build_metadata_from_records(
        self,
        species_name: str,
        *,
        primary_record: dict[str, Any],
        supporting_record: dict[str, Any] | None,
        strategy: str,
    ) -> dict[str, Any]:
        support = supporting_record or {}
        usage_key = primary_record.get("key") or primary_record.get("usageKey") or support.get("key") or support.get(
            "usageKey"
        )
        authorship = (
            str(primary_record.get("authorship") or "").strip()
            or str(support.get("authorship") or "").strip()
        )
        common_name = (
            self._extract_common_name(primary_record)
            or self._extract_common_name(support)
        )
        return {
            "tax_auth": authorship,
            "common_name": common_name,
            "gbif_url": f"https://www.gbif.org/species/{usage_key}" if usage_key else "",
            "gbif_usage_key": usage_key or "",
            "gbif_match_strategy": strategy,
            "gbif_taxonomic_status": primary_record.get("taxonomicStatus") or support.get("taxonomicStatus"),
        }

    @staticmethod
    def _extract_common_name(record: dict[str, Any]) -> str:
        direct = str(record.get("vernacularName") or "").strip()
        if direct:
            return direct

        vernaculars = record.get("vernacularNames") or []
        if not isinstance(vernaculars, list):
            return ""

        for item in vernaculars:
            if str(item.get("language") or "").lower() in {"eng", "en"}:
                return str(item.get("vernacularName") or "").strip()
        for item in vernaculars:
            name = str(item.get("vernacularName") or "").strip()
            if name:
                return name
        return ""

    @staticmethod
    def _is_exact_species_match(match: dict[str, Any], species_name: str) -> bool:
        if not match.get("usageKey"):
            return False
        if str(match.get("rank") or "").upper() != "SPECIES":
            return False
        if str(match.get("matchType") or "").upper() != "EXACT":
            return False
        canonical = str(match.get("canonicalName") or "").strip().lower()
        return canonical == species_name.strip().lower()

    @staticmethod
    def _select_primary_candidate(
        candidates: list[dict[str, Any]],
        tax_id: str | None,
    ) -> dict[str, Any] | None:
        if not candidates:
            return None

        def score(candidate: dict[str, Any]) -> tuple[int, int, int]:
            taxon_id = str(candidate.get("taxonID") or "").strip()
            matches_tax_id = 1 if tax_id and taxon_id == str(tax_id) else 0
            accepted = 1 if str(candidate.get("taxonomicStatus") or "").upper() == "ACCEPTED" else 0
            has_usage = 1 if candidate.get("key") or candidate.get("usageKey") else 0
            return (matches_tax_id, accepted, has_usage)

        return max(candidates, key=score)

    @staticmethod
    def _select_supporting_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None

        def score(candidate: dict[str, Any]) -> tuple[int, int, int]:
            accepted = 1 if str(candidate.get("taxonomicStatus") or "").upper() == "ACCEPTED" else 0
            has_authorship = 1 if candidate.get("authorship") else 0
            has_vernaculars = 1 if candidate.get("vernacularName") or candidate.get("vernacularNames") else 0
            return (accepted, has_authorship, has_vernaculars)

        return max(candidates, key=score)


__all__ = ["GbifTaxonomyClient"]
