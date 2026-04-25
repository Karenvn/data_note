from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from ..chromosome_analyzer import ChromosomeAnalyzer
from ..models import AssemblyBundle, AssemblyCoverageInput, AssemblySelection, NoteData, NoteContext
from ..ncbi_sequence_report_client import NcbiSequenceReportClient
from .assembly_service import AssemblyService
from .btk_service import BtkService
from .chromosome_service import ChromosomeService
from .ncbi_datasets_service import NcbiDatasetsService
from .render_context_builder import RenderContextBuilder

logger = logging.getLogger(__name__)

_DEFAULT_SEQUENCE_REPORT_CLIENT = NcbiSequenceReportClient()
_DEFAULT_CHROMOSOME_ANALYZER = ChromosomeAnalyzer(
    chromosome_length_fetcher=lambda accession: ChromosomeAnalyzer().get_chromosome_lengths(
        _DEFAULT_SEQUENCE_REPORT_CLIENT.fetch_reports(accession)
    )
)


@dataclass(slots=True)
class AssemblyWorkflowService:
    assembly_service: AssemblyService = field(default_factory=AssemblyService)
    ncbi_datasets_service: NcbiDatasetsService = field(default_factory=NcbiDatasetsService)
    chromosome_service: ChromosomeService = field(default_factory=ChromosomeService)
    btk_service: BtkService = field(default_factory=BtkService)
    render_context_builder: RenderContextBuilder = field(default_factory=RenderContextBuilder)
    coverage_calculator: Callable[[AssemblyCoverageInput], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_CHROMOSOME_ANALYZER.calculate_percentage_assembled
    )

    def build_bundle(
        self,
        note_data: NoteData,
        umbrella_data: dict[str, Any],
        tax_id: str,
        *,
        child_accessions: list[str] | None = None,
        known_tolid_fixes: Mapping[str, str] | None = None,
    ) -> tuple[AssemblyBundle, NoteContext]:
        assembly_selection = self.assembly_service.build_context(
            umbrella_data,
            tax_id,
            child_accessions=child_accessions,
        )
        assembly_bundle = AssemblyBundle(selection=assembly_selection)
        note_data.assembly = assembly_bundle
        note_data.base.assemblies_type = assembly_bundle.assemblies_type
        note_data.base.assembly_name = assembly_bundle.preferred_assembly_name()

        context = self.render_context_builder.derive_note_fields(note_data)
        datasets_ok = True
        try:
            assembly_bundle.datasets = self.ncbi_datasets_service.build_context(assembly_selection)
        except Exception as exc:
            datasets_ok = False
            note_data.base.extras["ncbi_datasets_error"] = str(exc)
            logger.warning(
                "NCBI datasets fetch failed for %s (%s): %s",
                note_data.base.bioproject,
                assembly_bundle.assemblies_type,
                exc,
            )

        context = self.render_context_builder.derive_note_fields(note_data)

        if datasets_ok:
            try:
                chromosome_context = self.render_context_builder.snapshot(note_data).to_dict()
                assembly_bundle.chromosomes = self.chromosome_service.build_context(
                    assembly_selection,
                    chromosome_context,
                )
            except Exception as exc:
                logger.warning(
                    "Chromosome processing failed for %s (%s): %s",
                    note_data.base.bioproject,
                    assembly_bundle.assemblies_type,
                    exc,
                )

        if datasets_ok and assembly_bundle.assemblies_type in {"prim_alt", "hap_asm"}:
            coverage_context = self.render_context_builder.snapshot(note_data).to_dict()
            coverage_input = AssemblyCoverageInput.from_selection_and_context(
                assembly_selection,
                coverage_context,
            )
            assembly_bundle.coverage_fields = self.coverage_calculator(coverage_input)

        if assembly_bundle.assemblies_type in {"prim_alt", "hap_asm"}:
            assembly_bundle.btk = self.btk_service.build_context(assembly_selection)

        context = self.render_context_builder.derive_note_fields(
            note_data,
            known_tolid_fixes=known_tolid_fixes,
        )
        return assembly_bundle, context
