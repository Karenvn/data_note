from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class FigureSpec:
    kind: str
    key: str
    stem: str
    alt_text: str


@dataclass(frozen=True, slots=True)
class TableSpec:
    key: str
    builder: Callable[[dict[str, Any]], dict[str, Any] | None]


class ProgrammeProfile(ABC):
    name: str

    @abstractmethod
    def figure_specs(self) -> tuple[FigureSpec, ...]:
        raise NotImplementedError

    def build_tables(self, context: dict[str, Any]) -> dict[str, Any]:
        tables: dict[str, dict[str, Any]] = {}
        for spec in self.table_specs():
            table = spec.builder(context)
            if table is not None:
                tables[spec.key] = table
        context["tables"] = tables
        return context

    @abstractmethod
    def table_specs(self) -> tuple[TableSpec, ...]:
        raise NotImplementedError
