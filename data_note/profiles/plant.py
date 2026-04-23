from __future__ import annotations

from .darwin import DarwinProfile


class PlantProfile(DarwinProfile):
    name = "plant"

    def uses_flow_cytometry(self) -> bool:
        return True
