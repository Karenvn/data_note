from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_btk_info import build_btk_urls, fetch_and_parse_summary, fetch_software_versions


@dataclass(slots=True)
class BtkService:
    summary_fetcher: Callable[..., dict[str, Any] | None] = fetch_and_parse_summary
    software_versions_fetcher: Callable[[str], dict[str, Any] | None] = fetch_software_versions
    url_builder: Callable[..., tuple[dict[str, Any] | None, dict[str, Any] | None]] = build_btk_urls

    def build_context(
        self,
        assemblies_type: str | None,
        assembly_accessions: dict[str, Any],
    ) -> dict[str, Any]:
        btk_dict: dict[str, Any] = {}

        if assemblies_type == "prim_alt":
            self._populate_primary_context(assembly_accessions, btk_dict)
        elif assemblies_type == "hap_asm":
            self._populate_haplotype_context(assembly_accessions, btk_dict)
        else:
            print(f"Warning: Unsupported assemblies type: {assemblies_type}")

        return btk_dict

    def _populate_primary_context(self, assembly_accessions: dict[str, Any], btk_dict: dict[str, Any]) -> None:
        print("Fetching BTK info for primary assembly...")
        prim_accession = assembly_accessions.get("prim_accession")
        if not prim_accession:
            print("Warning: Primary accession is missing.")
            return

        try:
            btk_dict.update(self.summary_fetcher(prim_accession) or {})
            btk_dict.update(self.software_versions_fetcher(prim_accession) or {})
            view_urls, download_urls = self.url_builder(prim_accession)
            btk_dict.update(view_urls or {})
            btk_dict.update(download_urls or {})
        except Exception as exc:
            print(f"Warning: BTK data missing or failed for {prim_accession}: {exc}")

    def _populate_haplotype_context(self, assembly_accessions: dict[str, Any], btk_dict: dict[str, Any]) -> None:
        print("Fetching BTK info for haplotype assemblies...")
        hap1_accession = assembly_accessions.get("hap1_accession")
        if hap1_accession:
            try:
                btk_dict.update(self.summary_fetcher(hap1_accession, prefix="hap1_") or {})
                btk_dict.update(self.software_versions_fetcher(hap1_accession) or {})
                view_urls, download_urls = self.url_builder(hap1_accession, prefix="hap1_")
                btk_dict.update(view_urls or {})
                btk_dict.update(download_urls or {})
            except Exception as exc:
                print(f"Warning: BTK data missing or failed for hap1 {hap1_accession}: {exc}")
        else:
            print("Warning: Hap1 accession is missing.")

        hap2_accession = assembly_accessions.get("hap2_accession")
        if hap2_accession:
            try:
                btk_dict.update(self.summary_fetcher(hap2_accession, prefix="hap2_") or {})
                view_urls, download_urls = self.url_builder(hap2_accession, prefix="hap2_")
                btk_dict.update(view_urls or {})
                btk_dict.update(download_urls or {})
            except Exception as exc:
                print(f"Warning: BTK data missing or failed for hap2 {hap2_accession}: {exc}")
        else:
            print("Warning: Hap2 accession is missing.")
