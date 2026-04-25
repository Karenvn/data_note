from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

import requests

from .ncbi_datasets_client import safe_ncbi_request

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NcbiTaxonomyClient:
    session_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def fetch_lineage_and_ranks(self, taxid: str) -> dict[str, Any]:
        api_url = (
            "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/"
            f"{taxid}/dataset_report"
        )
        response = safe_ncbi_request(
            api_url,
            {"accept": "application/json"},
            request_get=self.session_get,
            timeout=self.timeout,
        )
        data = response.json() or {}
        reports = data.get("reports", [])
        if not reports:
            logger.warning("No taxonomy report data found for taxid %s", taxid)
            return {}
        return self.parse_taxonomy_report(reports[0])

    @staticmethod
    def parse_taxonomy_report(report: dict[str, Any]) -> dict[str, Any]:
        taxonomy = report.get("taxonomy", {})
        classification = taxonomy.get("classification", {})
        lineage_parts = []
        for rank in ("domain", "kingdom", "phylum", "class", "order", "family", "genus", "species"):
            name = classification.get(rank, {}).get("name")
            if name:
                lineage_parts.append(name)

        current_name = taxonomy.get("current_scientific_name", {})
        return {
            "tax_id": str(taxonomy.get("tax_id")) if taxonomy.get("tax_id") is not None else None,
            "lineage": "; ".join(lineage_parts),
            "phylum": classification.get("phylum", {}).get("name"),
            "class": classification.get("class", {}).get("name"),
            "order": classification.get("order", {}).get("name"),
            "family": classification.get("family", {}).get("name"),
            "genus": classification.get("genus", {}).get("name"),
            "species": classification.get("species", {}).get("name") or current_name.get("name"),
            "domain": classification.get("domain", {}).get("name"),
            "kingdom": classification.get("kingdom", {}).get("name"),
            "tax_auth_ncbi": current_name.get("authority"),
            "common_name_ncbi": taxonomy.get("curator_common_name"),
            "group_name_ncbi": taxonomy.get("group_name"),
            "rank_ncbi": taxonomy.get("rank"),
        }


__all__ = ["NcbiTaxonomyClient"]
