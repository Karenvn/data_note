from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from ..calculate_metrics import calc_ebp_metric
from ..io_utils import load_and_apply_corrections
from ..models import NoteContext, NoteData
from ..profiles.base import ProgrammeProfile
from .context_assembler import ContextAssembler


@dataclass(slots=True)
class RenderContextBuilder:
    context_assembler: ContextAssembler = field(default_factory=ContextAssembler)
    correction_loader: Callable[[dict[str, Any], str], dict[str, Any]] = load_and_apply_corrections
    ebp_metric_calculator: Callable[[dict[str, Any]], str] = calc_ebp_metric

    def snapshot(
        self,
        note_data: NoteData,
        context: NoteContext | Mapping[str, Any] | None = None,
    ) -> NoteContext:
        return self.context_assembler.build(note_data, context=context)

    def derive_note_fields(
        self,
        note_data: NoteData,
        *,
        context: NoteContext | Mapping[str, Any] | None = None,
        known_tolid_fixes: Mapping[str, str] | None = None,
    ) -> NoteContext:
        note_context = self.snapshot(note_data, context=context)
        note_context.set_formatted_parent_projects()
        note_context.ensure_tolid()
        if known_tolid_fixes:
            note_context.apply_known_tolid_fix(dict(known_tolid_fixes))

        note_data.base.formatted_parent_projects = note_context.formatted_parent_projects
        if note_context.tax_id:
            note_data.base.tax_id = note_context.tax_id
        if note_context.tolid:
            note_data.base.tolid = note_context.tolid
        return note_context

    def build(
        self,
        note_data: NoteData,
        profile: ProgrammeProfile,
        *,
        corrections_file: str | None = None,
        known_tolid_fixes: Mapping[str, str] | None = None,
    ) -> NoteContext:
        note_context = self.derive_note_fields(
            note_data,
            known_tolid_fixes=known_tolid_fixes,
        )
        if corrections_file:
            self.correction_loader(note_context, corrections_file)
        note_context["ebp_metric"] = self.ebp_metric_calculator(note_context)
        rendered_context = profile.build_tables(note_context)
        if isinstance(rendered_context, NoteContext):
            return rendered_context
        return NoteContext.from_mapping(rendered_context)
