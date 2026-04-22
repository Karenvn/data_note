from __future__ import annotations

from .asg import AsgProfile
from .base import ProgrammeProfile
from .darwin import DarwinProfile
from .plant import PlantProfile
from .psyche import PsycheProfile


PROFILE_REGISTRY: dict[str, type[ProgrammeProfile]] = {
    AsgProfile.name: AsgProfile,
    DarwinProfile.name: DarwinProfile,
    PlantProfile.name: PlantProfile,
    PsycheProfile.name: PsycheProfile,
}


def get_profile(name: str | None = None) -> ProgrammeProfile:
    profile_name = (name or DarwinProfile.name).strip().lower()
    try:
        return PROFILE_REGISTRY[profile_name]()
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise ValueError(f"Unknown data_note profile {profile_name!r}. Available profiles: {available}") from exc


__all__ = ["AsgProfile", "DarwinProfile", "PlantProfile", "ProgrammeProfile", "PsycheProfile", "get_profile"]
