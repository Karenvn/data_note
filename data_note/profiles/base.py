from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class TableSpec:
    key: str
    builder: Callable[[dict[str, Any]], dict[str, Any]]


class ProgrammeProfile(ABC):
    name: str

    def build_tables(self, context: dict[str, Any]) -> dict[str, Any]:
        context["tables"] = {spec.key: spec.builder(context) for spec in self.table_specs()}
        return context

    @abstractmethod
    def table_specs(self) -> tuple[TableSpec, ...]:
        raise NotImplementedError
