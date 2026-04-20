from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..models import NoteContext, NoteData


@dataclass(slots=True)
class ContextAssembler:
    def merge(
        self,
        context: NoteContext | Mapping[str, Any] | None = None,
        *sections: Any,
    ) -> NoteContext:
        note_context = self._ensure_note_context(context)
        for section in sections:
            if isinstance(section, NoteData):
                note_context = self.merge(note_context, *section.context_sections())
                continue
            note_context.update(self._section_to_mapping(section))
        return note_context

    def build(self, note_data: NoteData, context: NoteContext | Mapping[str, Any] | None = None) -> NoteContext:
        return self.merge(context, note_data)

    @staticmethod
    def _ensure_note_context(context: NoteContext | Mapping[str, Any] | None) -> NoteContext:
        if isinstance(context, NoteContext):
            return context
        if context is None:
            return NoteContext()
        return NoteContext.from_mapping(dict(context))

    @staticmethod
    def _section_to_mapping(section: Any) -> dict[str, Any]:
        if section is None:
            return {}
        if isinstance(section, NoteContext):
            return section.to_dict()
        if isinstance(section, Mapping):
            return dict(section)

        to_context_dict = getattr(section, "to_context_dict", None)
        if callable(to_context_dict):
            mapping = to_context_dict()
            if isinstance(mapping, Mapping):
                return dict(mapping)

        raise TypeError(f"Cannot merge context section of type {type(section).__name__}")
