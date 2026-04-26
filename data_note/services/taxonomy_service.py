from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from ..gbif_taxonomy_client import GbifTaxonomyClient
from ..ncbi_taxonomy_client import NcbiTaxonomyClient
from ..models import TaxonomyInfo

logger = logging.getLogger(__name__)

_DEFAULT_TAXONOMY_CLIENT = NcbiTaxonomyClient()
_DEFAULT_GBIF_CLIENT = GbifTaxonomyClient()


@dataclass(slots=True)
class TaxonomyService:
    lineage_fetcher: Callable[[str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_TAXONOMY_CLIENT.fetch_lineage_and_ranks
    )
    gbif_fetcher: Callable[[str, str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_GBIF_CLIENT.fetch_species_metadata
    )

    def build_context(self, tax_id: str) -> TaxonomyInfo:
        logger.info("Accessing taxonomic information from the NCBI.")
        tax_dict = self.lineage_fetcher(tax_id)

        species = tax_dict["species"]
        logger.info("Species according to the NCBI is: %s", species)

        gbif_dict = self.gbif_fetcher(species, tax_id)
        resolved = self._resolve_public_taxonomy(tax_dict, gbif_dict)
        return TaxonomyInfo.from_legacy_parts(tax_id=tax_id, lineage_data=tax_dict, gbif_data=resolved)

    @staticmethod
    def _resolve_public_taxonomy(
        lineage_data: dict[str, Any],
        gbif_data: dict[str, Any],
    ) -> dict[str, Any]:
        resolved = dict(gbif_data)
        ncbi_authority = str(lineage_data.get("tax_auth_ncbi") or "").strip()
        gbif_authority = str(gbif_data.get("tax_auth") or "").strip()
        gbif_common_name = str(gbif_data.get("common_name") or "").strip()
        ncbi_common_name = str(lineage_data.get("common_name_ncbi") or "").strip()

        resolved["tax_auth"] = ncbi_authority or gbif_authority
        resolved["common_name"] = gbif_common_name or ncbi_common_name
        resolved["tax_auth_source"] = "ncbi_datasets" if ncbi_authority else ("gbif" if gbif_authority else "")
        resolved["common_name_source"] = "gbif" if gbif_common_name else ("ncbi_datasets" if ncbi_common_name else "")
        if gbif_authority:
            resolved["gbif_tax_auth"] = gbif_authority
        return resolved
