from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class FigureAsset:
    kind: str
    key: str
    stem: str
    alt_text: str
    png_path: Path
    tif_path: Path
    gif_path: Path
    extras: dict[str, Any] = field(default_factory=dict)

    def to_context_entry(self) -> str:
        return f"![{self.alt_text}](./{self.gif_path.name})"

    def to_context_dict(self) -> dict[str, str]:
        return {self.key: self.to_context_entry()}


@dataclass(slots=True)
class FigureBundle:
    assets: dict[str, FigureAsset] = field(default_factory=dict)

    def add(self, asset: FigureAsset) -> None:
        self.assets[asset.key] = asset

    def get(self, key: str) -> FigureAsset | None:
        return self.assets.get(key)

    def to_context_dict(self) -> dict[str, str]:
        context: dict[str, str] = {}
        for asset in self.assets.values():
            context.update(asset.to_context_dict())
        return context
