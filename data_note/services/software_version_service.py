from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..software_versions import read_local_software_versions


@dataclass(slots=True)
class SoftwareVersionService:
    version_fetcher: Callable[[str | None, str | Path | None], dict[str, Any]] = read_local_software_versions
    assets_root: str | Path | None = None

    def build_context(self, tolid: str | None) -> dict[str, Any]:
        return self.version_fetcher(tolid, self.assets_root)
