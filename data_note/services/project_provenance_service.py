from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..local_metadata_provider import get_local_metadata_provider
from ..project_provenance import normalise_project_provenance


@dataclass(slots=True)
class ProjectProvenanceService:
    provider_factory: Callable[[], Any] = get_local_metadata_provider

    def build_context(
        self,
        bioproject: str,
        *,
        tolid: str | None = None,
        species: str | None = None,
    ) -> dict[str, Any]:
        provider = self.provider_factory()
        provenance = provider.lookup_project_provenance(
            bioproject,
            tolid=tolid,
            species=species,
        )
        return normalise_project_provenance(provenance)
