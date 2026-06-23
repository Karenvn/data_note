from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

import requests

from .ncbi_datasets_client import safe_ncbi_request
from .taxonomic_authority import format_taxonomic_authority

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NcbiTaxonomyClient:
    session_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def fetch_lineage_and_ranks(self, taxid: str) -> dict[str, Any]:
        reports = self.fetch_taxonomy_reports(str(taxid))
        if not reports:
            logger.warning("No taxonomy report data found for taxid %s", taxid)
            return {}

        report = reports[0]
        lineage_records = self.fetch_parent_lineage(report)
        return self.parse_taxonomy_report(report, lineage_records=lineage_records)

    def fetch_taxonomy_reports(
        self,
        taxons: str,
        *,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        api_url = (
            "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/"
            f"{taxons}/dataset_report"
        )
        params: dict[str, Any] = {"returned_content": "METADATA"}
        if page_size is not None:
            params["page_size"] = page_size
        response = safe_ncbi_request(
            api_url,
            {"accept": "application/json"},
            request_get=self.session_get,
            params=params,
            timeout=self.timeout,
        )
        data = response.json() or {}
        return data.get("reports", [])

    def fetch_parent_lineage(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        taxonomy = report.get("taxonomy", {})
        parent_ids = self._ordered_parent_ids(taxonomy.get("parents", []))
        parent_ids = [tax_id for tax_id in parent_ids if not self._is_root_taxid(tax_id)]
        if not parent_ids:
            return []

        try:
            parent_reports = self.fetch_taxonomy_reports(
                ",".join(parent_ids),
                page_size=len(parent_ids),
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch full NCBI taxonomy lineage for %s: %s",
                taxonomy.get("tax_id"),
                exc,
            )
            return []

        parent_summaries = {
            str(summary["tax_id"]): summary
            for summary in (self._taxonomy_summary(parent_report) for parent_report in parent_reports)
            if summary.get("tax_id") is not None
        }
        lineage = [
            parent_summaries[tax_id]
            for tax_id in parent_ids
            if tax_id in parent_summaries and not self._is_root_name(parent_summaries[tax_id].get("name"))
        ]
        current = self._taxonomy_summary(report)
        if current.get("name") and not self._is_root_name(current.get("name")):
            lineage.append(current)
        return lineage

    @classmethod
    def parse_taxonomy_report(
        cls,
        report: dict[str, Any],
        *,
        lineage_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        taxonomy = report.get("taxonomy", {})
        classification = taxonomy.get("classification", {})
        lineage_parts = cls._lineage_parts_from_records(lineage_records or [])
        if not lineage_parts:
            lineage_parts = cls._lineage_parts_from_classification(classification)

        current_name = taxonomy.get("current_scientific_name", {})
        species_name = classification.get("species", {}).get("name") or current_name.get("name")
        basionym = current_name.get("basionym", {})
        if not isinstance(basionym, dict):
            basionym = {}
        authority = format_taxonomic_authority(
            current_name.get("authority") or basionym.get("authority"),
            current_name=species_name,
            original_name=basionym.get("name"),
        )
        authority_extras = {}
        if authority.original_combination:
            authority_extras["original_combination_ncbi"] = authority.original_combination
            authority_extras["tax_auth_ncbi_verification"] = authority.status
        raw_authority = current_name.get("authority")
        if raw_authority and authority.authority != str(raw_authority).strip():
            authority_extras["tax_auth_ncbi_raw"] = raw_authority
        return {
            "tax_id": str(taxonomy.get("tax_id")) if taxonomy.get("tax_id") is not None else None,
            "lineage": "; ".join(lineage_parts),
            "lineage_source": (
                "ncbi_datasets_parents" if lineage_records else "ncbi_datasets_classification"
            ),
            "phylum": classification.get("phylum", {}).get("name"),
            "phylum_taxid": classification.get("phylum", {}).get("id"),
            "class": classification.get("class", {}).get("name"),
            "class_taxid": classification.get("class", {}).get("id"),
            "order": classification.get("order", {}).get("name"),
            "order_taxid": classification.get("order", {}).get("id"),
            "family": classification.get("family", {}).get("name"),
            "family_taxid": classification.get("family", {}).get("id"),
            "genus": classification.get("genus", {}).get("name"),
            "genus_taxid": classification.get("genus", {}).get("id"),
            "species": species_name,
            "species_taxid": classification.get("species", {}).get("id") or taxonomy.get("tax_id"),
            "domain": classification.get("domain", {}).get("name"),
            "domain_taxid": classification.get("domain", {}).get("id"),
            "kingdom": classification.get("kingdom", {}).get("name"),
            "kingdom_taxid": classification.get("kingdom", {}).get("id"),
            "tax_auth_ncbi": authority.authority,
            "common_name_ncbi": taxonomy.get("curator_common_name"),
            "group_name_ncbi": taxonomy.get("group_name"),
            "rank_ncbi": taxonomy.get("rank"),
            **authority_extras,
        }

    @classmethod
    def _lineage_parts_from_records(cls, records: list[dict[str, Any]]) -> list[str]:
        return [
            cls._format_lineage_name(record["name"], record.get("rank"))
            for record in records
            if record.get("name")
        ]

    @classmethod
    def _lineage_parts_from_classification(cls, classification: dict[str, Any]) -> list[str]:
        lineage_parts = []
        seen_taxids = set()
        for rank in (
            "domain",
            "superkingdom",
            "kingdom",
            "phylum",
            "class",
            "order",
            "family",
            "genus",
            "subgenus",
            "species",
        ):
            taxon = classification.get(rank, {})
            name = taxon.get("name")
            taxid = taxon.get("id")
            if not name or (taxid is not None and taxid in seen_taxids):
                continue
            if taxid is not None:
                seen_taxids.add(taxid)
            lineage_parts.append(cls._format_lineage_name(name, rank))
        return lineage_parts

    @staticmethod
    def _format_lineage_name(name: str, rank: str | None) -> str:
        normalized_rank = str(rank or "").lower().replace("_", " ")
        if normalized_rank in {"genus", "subgenus", "species"}:
            return f"*{name}*"
        return name

    @classmethod
    def _ordered_parent_ids(cls, parent_ids: list[Any]) -> list[str]:
        ordered = [str(parent_id) for parent_id in parent_ids if parent_id is not None]
        if ordered and not cls._is_root_taxid(ordered[0]) and cls._is_root_taxid(ordered[-1]):
            ordered.reverse()
        return ordered

    @staticmethod
    def _taxonomy_summary(report: dict[str, Any]) -> dict[str, Any]:
        taxonomy = report.get("taxonomy", {})
        return {
            "tax_id": str(taxonomy.get("tax_id")) if taxonomy.get("tax_id") is not None else None,
            "rank": taxonomy.get("rank"),
            "name": taxonomy.get("current_scientific_name", {}).get("name"),
        }

    @staticmethod
    def _is_root_taxid(taxid: str) -> bool:
        return str(taxid) in {"1", "131567"}

    @staticmethod
    def _is_root_name(name: Any) -> bool:
        return str(name or "").strip().lower() in {"root", "cellular organisms"}


__all__ = ["NcbiTaxonomyClient"]
