from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable

from ..models import AnnotationInfo, AssemblyBundle, NoteData, NoteContext, QualityMetrics
from .annotation_service import AnnotationService
from .render_context_builder import RenderContextBuilder
from .server_data_service import ServerDataService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AnnotationQualityWorkflowService:
    annotation_service: AnnotationService = field(default_factory=AnnotationService)
    server_data_service: ServerDataService = field(default_factory=ServerDataService)
    render_context_builder: RenderContextBuilder = field(default_factory=RenderContextBuilder)
    progress_printer: Callable[[str], None] = logger.info
    warning_logger: Callable[[str], None] = logger.warning

    def build_sections(
        self,
        note_data: NoteData,
        *,
        bioproject: str,
        species: str | None,
        assembly_bundle: AssemblyBundle,
        tax_id: str | int | None,
    ) -> NoteContext:
        self.progress_printer("Checking for Ensembl annotation...")
        try:
            ensembl_accession = assembly_bundle.preferred_accession()
            annotation_info = self.annotation_service.build_context(ensembl_accession, species, tax_id)
            annotation_context = annotation_info.to_context_dict()
            if not annotation_context:
                self.progress_printer(
                    f"No Ensembl annotation found for {species} / {assembly_bundle.preferred_accession()}"
                )
            else:
                note_data.annotation = annotation_info
                if os.environ.get("GN_DEBUG_ENSEMBL") == "1":
                    self.progress_printer(
                        f"Ensembl annotation: {annotation_context['ensembl_annotation_url']}"
                    )
        except Exception as exc:
            self.warning_logger(
                f"Warning: Ensembl fetch failed for {bioproject} ({assembly_bundle.assemblies_type}): {exc}"
            )

        note_data.quality = self.server_data_service.build_context(
            assembly_bundle.assemblies_type,
            note_data.base.tolid,
        )
        return self.render_context_builder.snapshot(note_data)

    def build_annotation(
        self,
        assembly_accession: str | None,
        species: str,
        tax_id: str | int | None,
    ) -> AnnotationInfo:
        return self.annotation_service.build_context(assembly_accession, species, tax_id)

    def build_quality(self, assemblies_type: str | None, tolid: str | None) -> QualityMetrics:
        return self.server_data_service.build_context(assemblies_type, tolid)
