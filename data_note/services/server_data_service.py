from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_server_data import (
    get_merqury_results_haplotype_assemblies,
    get_merqury_results_prim_alt,
    parse_genomescope,
)


@dataclass(slots=True)
class ServerDataService:
    prim_alt_merqury_fetcher: Callable[[str], dict[str, Any]] = get_merqury_results_prim_alt
    haplotype_merqury_fetcher: Callable[[str], dict[str, Any]] = get_merqury_results_haplotype_assemblies
    genomescope_fetcher: Callable[[str], dict[str, Any]] = parse_genomescope

    def build_context(self, assemblies_type: str | None, tolid: str) -> dict[str, Any]:
        server_data: dict[str, Any] = {}
        if assemblies_type == "prim_alt":
            server_data.update(self.prim_alt_merqury_fetcher(tolid))
        elif assemblies_type == "hap_asm":
            server_data.update(self.haplotype_merqury_fetcher(tolid))

        server_data.update(self.genomescope_fetcher(tolid))
        return server_data
