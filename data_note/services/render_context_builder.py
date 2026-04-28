from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from ..calculate_metrics import calc_ebp_metric
from ..io_utils import load_and_apply_corrections
from ..models import NoteContext, NoteData
from ..sampling_template_fields import populate_sampling_template_fields
from ..tables.common import (
    has_alternate_assembly,
    is_haploid_note,
    resolve_single_assembly_label,
    resolve_single_assembly_metric_label,
    resolve_single_assembly_metric_prefix,
    resolve_single_assembly_phrase,
)
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
        self._apply_assembly_rendering_context(note_context)
        populate_sampling_template_fields(note_context)
        note_context["ebp_metric"] = self.ebp_metric_calculator(note_context)
        rendered_context = profile.build_tables(note_context)
        if isinstance(rendered_context, NoteContext):
            return rendered_context
        return NoteContext.from_mapping(rendered_context)

    @staticmethod
    def _apply_assembly_rendering_context(note_context: NoteContext) -> None:
        if note_context.get("assemblies_type") != "prim_alt":
            return

        is_haploid = is_haploid_note(note_context)
        note_context["is_haploid"] = is_haploid
        note_context["has_alternate_assembly"] = has_alternate_assembly(note_context)
        note_context["single_assembly_label"] = resolve_single_assembly_label(note_context)
        note_context["single_assembly_phrase"] = resolve_single_assembly_phrase(note_context)
        note_context["single_assembly_metric_label"] = resolve_single_assembly_metric_label(note_context)
        note_context["single_assembly_metric_prefix"] = resolve_single_assembly_metric_prefix(note_context)

        if "hifiasm_primary_mode" not in note_context:
            note_context["hifiasm_primary_mode"] = is_haploid
        if "hifiasm_internal_purging_disabled" not in note_context:
            note_context["hifiasm_internal_purging_disabled"] = is_haploid
        if is_haploid:
            if "hifiasm_options" not in note_context:
                note_context["hifiasm_options"] = "--primary -l0"
            if "hifiasm_options_sentence" not in note_context:
                note_context["hifiasm_options_sentence"] = (
                    "For this haploid genome, Hifiasm was run with `--primary` and `-l0`; "
                    "`-l0` switches off internal Hifiasm purging."
                )

        if not note_context["has_alternate_assembly"]:
            for key in ("alt_accession", "alt_assembly_name", "alt_QV", "alt_kmer_completeness"):
                note_context.pop(key, None)
