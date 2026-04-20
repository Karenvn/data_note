from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_gbif_info import fetch_taxonomy_info
from ..fetch_ncbi_data import get_taxonomy_lineage_and_ranks
from ..models import TaxonomyInfo


@dataclass(slots=True)
class TaxonomyService:
    lineage_fetcher: Callable[[str], dict[str, Any]] = get_taxonomy_lineage_and_ranks
    gbif_fetcher: Callable[[str], dict[str, Any]] = fetch_taxonomy_info

    def build_context(self, tax_id: str) -> TaxonomyInfo:
        print("Accessing taxonomic information from the NCBI.")
        tax_dict = self.lineage_fetcher(tax_id)

        species = tax_dict["species"]
        print("Species according to the NCBI is:", species)

        gbif_dict = self.gbif_fetcher(species)
        return TaxonomyInfo.from_legacy_parts(tax_id=tax_id, lineage_data=tax_dict, gbif_data=gbif_dict)
