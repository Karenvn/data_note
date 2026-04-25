from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from Bio import Entrez
import requests

from .ncbi_datasets_client import safe_ncbi_request


@dataclass(slots=True)
class NcbiSequenceReportClient:
    request_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def fetch_reports(self, accession: str) -> list[dict[str, Any]]:
        api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/sequence_reports"
        response = safe_ncbi_request(
            api_url,
            self._headers(),
            request_get=self.request_get,
            timeout=self.timeout,
        )
        data = response.json() or {}
        return data.get("reports", [])

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "accept": "application/json",
            "User-Agent": f"Python script; {Entrez.email}",
        }


__all__ = ["NcbiSequenceReportClient"]
