from __future__ import annotations

from dataclasses import dataclass

from .models import AssemblyCandidate, AssemblyMode


@dataclass(slots=True)
class AssemblyModeDetector:
    def detect(self, relevant_assemblies: list[AssemblyCandidate]) -> AssemblyMode:
        for assembly in relevant_assemblies:
            name = assembly.assembly_name
            if "hap1" in name or "hap2" in name:
                return "hap_asm"
        return "prim_alt"


__all__ = ["AssemblyModeDetector"]
