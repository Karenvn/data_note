from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

from ..models import AssemblySelection, BtkAssemblyRecord, BtkSummary
from ..fetch_btk_info import build_btk_urls, fetch_and_parse_summary, fetch_software_versions

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BtkService:
    summary_fetcher: Callable[..., dict[str, Any] | None] = fetch_and_parse_summary
    software_versions_fetcher: Callable[[str], dict[str, Any] | None] = fetch_software_versions
    url_builder: Callable[..., tuple[dict[str, Any] | None, dict[str, Any] | None]] = build_btk_urls

    def build_context(
        self,
        assembly_selection: AssemblySelection,
    ) -> BtkSummary:
        btk_summary = BtkSummary(assemblies_type=assembly_selection.assemblies_type)

        if assembly_selection.assemblies_type == "prim_alt":
            self._populate_primary_context(assembly_selection, btk_summary)
        elif assembly_selection.assemblies_type == "hap_asm":
            self._populate_haplotype_context(assembly_selection, btk_summary)
        else:
            logger.warning("Unsupported assemblies type for BTK: %s", assembly_selection.assemblies_type)

        return btk_summary

    def _populate_primary_context(self, assembly_selection: AssemblySelection, btk_summary: BtkSummary) -> None:
        logger.info("Fetching BTK info for primary assembly.")
        if assembly_selection.primary is None:
            logger.warning("Primary accession is missing.")
            return
        prim_accession = assembly_selection.primary.accession

        try:
            btk_summary.primary = self._build_record(prim_accession)
            btk_summary.shared_fields.update(self.software_versions_fetcher(prim_accession) or {})
        except Exception as exc:
            logger.warning("BTK data missing or failed for %s: %s", prim_accession, exc)

    def _populate_haplotype_context(self, assembly_selection: AssemblySelection, btk_summary: BtkSummary) -> None:
        logger.info("Fetching BTK info for haplotype assemblies.")
        if assembly_selection.hap1 is not None:
            hap1_accession = assembly_selection.hap1.accession
            try:
                btk_summary.hap1 = self._build_record(hap1_accession, prefix="hap1_")
                btk_summary.shared_fields.update(self.software_versions_fetcher(hap1_accession) or {})
            except Exception as exc:
                logger.warning("BTK data missing or failed for hap1 %s: %s", hap1_accession, exc)
        else:
            logger.warning("Hap1 accession is missing.")

        if assembly_selection.hap2 is not None:
            hap2_accession = assembly_selection.hap2.accession
            try:
                btk_summary.hap2 = self._build_record(hap2_accession, prefix="hap2_")
            except Exception as exc:
                logger.warning("BTK data missing or failed for hap2 %s: %s", hap2_accession, exc)
        else:
            logger.warning("Hap2 accession is missing.")

    def _build_record(self, accession: str, *, prefix: str = "") -> BtkAssemblyRecord:
        view_urls, download_urls = self.url_builder(accession, prefix=prefix)
        return BtkAssemblyRecord(
            summary_fields=self.summary_fetcher(accession, prefix=prefix) or {},
            view_urls=view_urls or {},
            download_urls=download_urls or {},
        )
