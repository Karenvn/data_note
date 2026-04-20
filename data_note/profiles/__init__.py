from __future__ import annotations

from .base import ProgrammeProfile
from .darwin import DarwinProfile
from .psyche import PsycheProfile


PROFILE_REGISTRY: dict[str, type[ProgrammeProfile]] = {
    DarwinProfile.name: DarwinProfile,
    PsycheProfile.name: PsycheProfile,
}


def get_profile(name: str | None = None) -> ProgrammeProfile:
    profile_name = (name or DarwinProfile.name).strip().lower()
    try:
        return PROFILE_REGISTRY[profile_name]()
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise ValueError(f"Unknown data_note profile {profile_name!r}. Available profiles: {available}") from exc


__all__ = ["DarwinProfile", "ProgrammeProfile", "PsycheProfile", "get_profile"]
