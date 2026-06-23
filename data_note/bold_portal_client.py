from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

import requests

from .species_summary_models import BoldBinSummary


BOLD_PORTAL_BASE_URL = "https://portal.boldsystems.org"
BOLD_BIN_PATTERN = re.compile(r"^BOLD:[A-Z]{3}\d{4,5}$")


@dataclass(slots=True)
class BoldPortalClient:
    session_get: Callable[..., Any] = requests.get
    base_url: str = BOLD_PORTAL_BASE_URL
    timeout: int = 30

    def fetch_species_bin_summary(
        self,
        species_name: str,
        *,
        marker_code: str = "COI-5P",
    ) -> BoldBinSummary | None:
        species = str(species_name or "").strip()
        if not species:
            return None

        summary = self._fetch_summary(species)
        marker_count = self._marker_count(summary, marker_code)
        if marker_count <= 0:
            return None

        bin_uri = self._single_bin_uri(summary)
        if not bin_uri:
            return None

        ancillary = self._fetch_bin_ancillary(bin_uri)
        if not ancillary:
            return None

        return BoldBinSummary(
            bin_uri=bin_uri,
            doi=self._clean_string(ancillary.get("barcodecluster.doi")),
            sequence_count=marker_count,
            marker_code=marker_code,
            avg_distance=self._coerce_float(ancillary.get("barcodecluster.avgdist")),
            max_distance=self._coerce_float(ancillary.get("barcodecluster.maxdist")),
        )

    def _fetch_summary(self, species_name: str) -> dict[str, Any]:
        response = self.session_get(
            f"{self.base_url.rstrip('/')}/api/summary",
            params={
                "query": f"tax:species:{species_name}",
                "fields": "bin_uri,marker_code,species,specimens",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json() or {}
        return data if isinstance(data, dict) else {}

    def _fetch_bin_ancillary(self, bin_uri: str) -> dict[str, Any] | None:
        response = self.session_get(
            f"{self.base_url.rstrip('/')}/api/ancillary",
            params={
                "collection": "barcodeclusters",
                "key": "barcodecluster.uri",
                "values": bin_uri,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json() or []
        if not isinstance(data, list) or not data:
            return None
        first = data[0]
        return first if isinstance(first, dict) else None

    @staticmethod
    def _marker_count(summary: dict[str, Any], marker_code: str) -> int:
        marker_counts = summary.get("marker_code") or {}
        if not isinstance(marker_counts, dict):
            return 0
        return BoldPortalClient._coerce_int(marker_counts.get(marker_code))

    @staticmethod
    def _single_bin_uri(summary: dict[str, Any]) -> str | None:
        bin_counts = summary.get("bin_uri") or {}
        if not isinstance(bin_counts, dict):
            return None
        bins = [
            str(bin_uri).strip()
            for bin_uri in bin_counts
            if BOLD_BIN_PATTERN.match(str(bin_uri).strip())
        ]
        return bins[0] if len(bins) == 1 else None

    @staticmethod
    def _coerce_int(value: Any) -> int:
        if value in (None, ""):
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None


__all__ = ["BoldPortalClient"]
