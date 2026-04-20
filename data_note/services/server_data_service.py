from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_server_data import (
    get_merqury_results_haplotype_assemblies,
    get_merqury_results_prim_alt,
    parse_genomescope,
)
from ..models import QualityMetrics


@dataclass(slots=True)
class ServerDataService:
    prim_alt_merqury_fetcher: Callable[[str], dict[str, Any]] = get_merqury_results_prim_alt
    haplotype_merqury_fetcher: Callable[[str], dict[str, Any]] = get_merqury_results_haplotype_assemblies
    genomescope_fetcher: Callable[[str], dict[str, Any]] = parse_genomescope

    def build_context(self, assemblies_type: str | None, tolid: str | None) -> QualityMetrics:
        if not tolid:
            return QualityMetrics()

        merqury: dict[str, Any] = {}
        if assemblies_type == "prim_alt":
            merqury.update(self.prim_alt_merqury_fetcher(tolid))
        elif assemblies_type == "hap_asm":
            merqury.update(self.haplotype_merqury_fetcher(tolid))

        genomescope = self.genomescope_fetcher(tolid)
        return QualityMetrics.from_legacy_parts(
            genomescope=genomescope,
            merqury=merqury,
        )
