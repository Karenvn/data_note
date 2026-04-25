from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from ..models import AssemblyDatasetRecord, AssemblyDatasetsInfo, AssemblySelection
from ..chromosome_analyzer import ChromosomeAnalyzer
from ..ncbi_datasets_client import NcbiDatasetsClient
from ..ncbi_organelle_client import NcbiOrganelleClient
from ..ncbi_sequence_report_client import NcbiSequenceReportClient

logger = logging.getLogger(__name__)

_DEFAULT_DATASETS_CLIENT = NcbiDatasetsClient()
_DEFAULT_ORGANELLE_CLIENT = NcbiOrganelleClient()
_DEFAULT_SEQUENCE_REPORT_CLIENT = NcbiSequenceReportClient()
_DEFAULT_CHROMOSOME_ANALYZER = ChromosomeAnalyzer()


@dataclass(slots=True)
class NcbiDatasetsService:
    primary_info_fetcher: Callable[[str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_DATASETS_CLIENT.fetch_primary_assembly_info
    )
    haplotype_info_fetcher: Callable[[str, str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_DATASETS_CLIENT.fetch_haplotype_assembly_info
    )
    organelle_template_fetcher: Callable[[str], Any] = field(
        default_factory=lambda: _DEFAULT_ORGANELLE_CLIENT.fetch_organelle_template_data
    )
    organelle_info_fetcher: Callable[[str], dict[str, Any]] = field(
        default_factory=lambda: _DEFAULT_ORGANELLE_CLIENT.fetch_organelle_info
    )
    longest_scaffold_fetcher: Callable[[str], Any] = field(
        default_factory=lambda: (
            lambda accession: _DEFAULT_CHROMOSOME_ANALYZER.get_longest_scaffold(
                _DEFAULT_SEQUENCE_REPORT_CLIENT.fetch_reports(accession)
            )
        )
    )

    def build_context(
        self,
        assembly_selection: AssemblySelection,
    ) -> AssemblyDatasetsInfo:
        if assembly_selection.assemblies_type == "prim_alt":
            return self._build_primary_context(assembly_selection)
        if assembly_selection.assemblies_type == "hap_asm":
            return self._build_haplotype_context(assembly_selection)
        return AssemblyDatasetsInfo(assemblies_type=assembly_selection.assemblies_type)

    def _build_primary_context(self, assembly_selection: AssemblySelection) -> AssemblyDatasetsInfo:
        if assembly_selection.primary is None:
            return AssemblyDatasetsInfo(assemblies_type="prim_alt")

        prim_accession = assembly_selection.primary.accession
        primary_fields = self.primary_info_fetcher(prim_accession) or {}
        shared_fields: dict[str, Any] = {
            "organelle_data": self.organelle_template_fetcher(prim_accession),
        }
        try:
            shared_fields.update(self.organelle_info_fetcher(prim_accession))
        except Exception as exc:
            logger.warning("Organelle fetch failed for %s: %s", prim_accession, exc)
            shared_fields["organelle_error"] = str(exc)
        primary_fields["longest_scaffold_length"] = self.longest_scaffold_fetcher(prim_accession)
        return AssemblyDatasetsInfo(
            assemblies_type="prim_alt",
            primary=AssemblyDatasetRecord.from_mapping(primary_fields),
            shared_fields=shared_fields,
        )

    def _build_haplotype_context(self, assembly_selection: AssemblySelection) -> AssemblyDatasetsInfo:
        if assembly_selection.hap1 is None or assembly_selection.hap2 is None:
            return AssemblyDatasetsInfo(assemblies_type="hap_asm")

        hap1_accession = assembly_selection.hap1.accession
        hap2_accession = assembly_selection.hap2.accession

        combined_fields = self.haplotype_info_fetcher(hap1_accession, hap2_accession) or {}
        shared_fields: dict[str, Any] = {
            "organelle_data": self.organelle_template_fetcher(hap1_accession),
        }
        try:
            shared_fields.update(self.organelle_info_fetcher(hap1_accession))
        except Exception as exc:
            logger.warning("Organelle fetch failed for %s: %s", hap1_accession, exc)
            shared_fields["organelle_error"] = str(exc)
        combined_fields["hap1_longest_scaffold_length"] = self.longest_scaffold_fetcher(hap1_accession)
        combined_fields["hap2_longest_scaffold_length"] = self.longest_scaffold_fetcher(hap2_accession)
        return AssemblyDatasetsInfo(
            assemblies_type="hap_asm",
            hap1=AssemblyDatasetRecord.from_mapping(combined_fields, prefix="hap1_"),
            hap2=AssemblyDatasetRecord.from_mapping(combined_fields, prefix="hap2_"),
            shared_fields={
                **shared_fields,
                **{
                    key: value
                    for key, value in combined_fields.items()
                    if not key.startswith("hap1_") and not key.startswith("hap2_")
                },
            },
        )
