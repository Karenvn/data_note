from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_gbif_info import fetch_taxonomy_info
from ..fetch_ncbi_data import get_taxonomy_lineage_and_ranks


@dataclass(slots=True)
class TaxonomyService:
    lineage_fetcher: Callable[[str], dict[str, Any]] = get_taxonomy_lineage_and_ranks
    gbif_fetcher: Callable[[str], dict[str, Any]] = fetch_taxonomy_info

    def build_context(self, tax_id: str) -> dict[str, Any]:
        tax_context: dict[str, Any] = {}
        print("Accessing taxonomic information from the NCBI.")
        tax_dict = self.lineage_fetcher(tax_id)
        tax_context.update(tax_dict)

        species = tax_dict["species"]
        print("Species according to the NCBI is:", species)

        gbif_dict = self.gbif_fetcher(species)
        tax_context.update(gbif_dict)
        return tax_context
