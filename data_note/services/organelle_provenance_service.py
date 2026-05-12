from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..organelle_provenance import read_local_organelle_provenance


@dataclass(slots=True)
class OrganelleProvenanceService:
    provenance_fetcher: Callable[[str | None, str | Path | None], dict[str, Any]] = read_local_organelle_provenance
    assets_root: str | Path | None = None

    def build_context(self, tolid: str | None) -> dict[str, Any]:
        return self.provenance_fetcher(tolid, self.assets_root)
