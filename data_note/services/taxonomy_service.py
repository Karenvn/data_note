from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from ..fetch_gbif_info import fetch_taxonomy_info
from ..ncbi_taxonomy_client import NcbiTaxonomyClient
from ..models import TaxonomyInfo

logger = logging.getLogger(__name__)

_DEFAULT_TAXONOMY_CLIENT = NcbiTaxonomyClient()


@dataclass(slots=True)
class TaxonomyService:
    lineage_fetcher: Callable[[str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_TAXONOMY_CLIENT.fetch_lineage_and_ranks
    )
    gbif_fetcher: Callable[[str], dict[str, Any]] = fetch_taxonomy_info

    def build_context(self, tax_id: str) -> TaxonomyInfo:
        logger.info("Accessing taxonomic information from the NCBI.")
        tax_dict = self.lineage_fetcher(tax_id)

        species = tax_dict["species"]
        logger.info("Species according to the NCBI is: %s", species)

        gbif_dict = self.gbif_fetcher(species)
        return TaxonomyInfo.from_legacy_parts(tax_id=tax_id, lineage_data=tax_dict, gbif_data=gbif_dict)
