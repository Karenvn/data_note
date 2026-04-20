from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from ..fetch_biosample_info import create_biosample_dict
from ..models import (
    AssemblySelection,
    AuthorInfo,
    CurationBundle,
    NoteData,
    NoteContext,
    SamplingInfo,
    SequencingSummary,
)
from .author_service import AuthorService
from .curation_service import CurationService
from .render_context_builder import RenderContextBuilder
from .sequencing_service import SequencingService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SequencingWorkflowService:
    sequencing_service: SequencingService = field(default_factory=SequencingService)
    curation_service: CurationService = field(default_factory=CurationService)
    author_service: AuthorService = field(default_factory=AuthorService)
    render_context_builder: RenderContextBuilder = field(default_factory=RenderContextBuilder)
    biosample_dict_builder: Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]] = (
        create_biosample_dict
    )
    warning_logger: Callable[..., None] = logger.warning
    progress_printer: Callable[[str], None] = logger.info

    def build_sections(
        self,
        note_data: NoteData,
        *,
        bioproject: str,
        child_accessions: list[str] | None,
        species: str | None,
        assembly_selection: AssemblySelection,
        tolid: str | None,
    ) -> NoteContext:
        sequencing_projects = child_accessions or [bioproject]
        sequencing_summary = self.sequencing_service.build_context(sequencing_projects, tolid)
        note_data.sequencing = sequencing_summary

        extraction_lookup_id = sequencing_summary.pacbio_library_name() or tolid
        try:
            note_data.curation = self.curation_service.build_context(
                assembly_selection,
                species=species,
                tolid=tolid,
                extraction_lookup_id=extraction_lookup_id,
            )
        except Exception as exc:
            self.warning_logger("Failed to process curation data for %r: %s", bioproject, exc)

        note_data.sampling = self.build_sampling(sequencing_summary.technology_data)
        context = self.render_context_builder.snapshot(note_data)
        note_data.author = self.author_service.build_context(context)
        return self.render_context_builder.snapshot(note_data)

    def build_sampling(self, technology_data: dict[str, Any]) -> SamplingInfo:
        self.progress_printer("Accessing BioSample information from BioSamples.")
        pacbio_sample_dict, rna_sample_dict, hic_sample_dict, isoseq_sample_dict = self.biosample_dict_builder(
            technology_data
        )
        return SamplingInfo.from_legacy_dicts(
            pacbio=pacbio_sample_dict,
            rna=rna_sample_dict,
            hic=hic_sample_dict,
            isoseq=isoseq_sample_dict,
        )

    def build_author(self, context: NoteContext | dict[str, Any]) -> AuthorInfo:
        return self.author_service.build_context(context)
