from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable

from ..fetch_extraction_data import (
    fallback_fetch_from_lr_sample_prep,
    fetch_barcoding_info,
    get_sequencing_and_extraction_metadata,
)
from ..models import (
    AssemblySelection,
    BarcodingInfo,
    CurationBundle,
    CurationInfo,
    ExtractionInfo,
)
from .local_metadata_service import LocalMetadataService

logger = logging.getLogger(__name__)

_ZERO_PLACEHOLDER_FIELDS = {"tissue_weight_mg"}


@dataclass(slots=True)
class CurationService:
    local_metadata_service: LocalMetadataService = field(default_factory=LocalMetadataService)
    sequencing_extraction_fetcher: Callable[[str], tuple[dict[str, Any], dict[str, Any]]] = (
        get_sequencing_and_extraction_metadata
    )
    extraction_fallback_fetcher: Callable[[str], dict[str, Any]] = fallback_fetch_from_lr_sample_prep
    barcoding_fetcher: Callable[[str], dict[str, Any]] = fetch_barcoding_info

    def build_context(
        self,
        assembly_selection: AssemblySelection,
        *,
        species: str | None,
        tolid: str | None,
        extraction_lookup_id: str | None,
    ) -> CurationBundle:
        return CurationBundle(
            local_metadata=self.build_local_metadata(assembly_selection, species=species, tolid=tolid),
            extraction=self.build_extraction(extraction_lookup_id),
            barcoding=self.build_barcoding(tolid),
        )

    def build_local_metadata(
        self,
        assembly_selection: AssemblySelection,
        *,
        species: str | None,
        tolid: str | None,
    ) -> CurationInfo:
        return self.local_metadata_service.build_context(assembly_selection, tolid=tolid, species=species)

    def build_extraction(self, library_name: str | None) -> ExtractionInfo:
        extraction_context: dict[str, Any] = {}
        lookup_id = str(library_name).strip() if library_name is not None else ""
        if not lookup_id:
            return ExtractionInfo()

        seq_attrs, extraction_attrs = self.sequencing_extraction_fetcher(lookup_id)
        if seq_attrs:
            extraction_context.update({key: value for key, value in seq_attrs.items()})

        important_fields = [
            "dna_yield_ng",
            "qubit_ngul",
            "volume_ul",
            "ratio_260_280",
            "ratio_260_230",
            "fragment_size_kb",
            "extraction_date",
        ]

        needs_fallback = False
        if not extraction_attrs:
            needs_fallback = True
        else:
            missing = [key for key in important_fields if extraction_attrs.get(key) in (None, "", float("nan"))]
            if len(missing) >= len(important_fields) - 1:
                needs_fallback = True

        if extraction_attrs:
            extraction_context.update({key: value for key, value in extraction_attrs.items()})

        def _is_missing(value: Any) -> bool:
            if value is None or value == "":
                return True
            try:
                return value != value
            except Exception:
                return False

        def _should_backfill(key: str, current_value: Any, fallback_value: Any) -> bool:
            if _is_missing(current_value):
                return True
            if key not in _ZERO_PLACEHOLDER_FIELDS:
                return False
            if current_value not in (0, 0.0, "0", "0.0"):
                return False
            return not _is_missing(fallback_value) and fallback_value not in (0, 0.0, "0", "0.0")

        def _fallback_lookup_ids() -> list[str]:
            lookup_ids = [lookup_id]
            for candidate in (
                extraction_context.get("sanger_sample_id"),
                extraction_context.get("submission_id"),
            ):
                candidate_str = str(candidate).strip() if candidate is not None else ""
                if candidate_str and candidate_str not in lookup_ids:
                    lookup_ids.append(candidate_str)
            return lookup_ids

        fallback_attrs: dict[str, Any] = {}

        if needs_fallback:
            logger.info("Extraction info incomplete or missing. Falling back to local LR_sample_prep.tsv.")
            for fallback_lookup_id in _fallback_lookup_ids():
                fallback_attrs = self.extraction_fallback_fetcher(fallback_lookup_id)
                if fallback_attrs:
                    for key, value in fallback_attrs.items():
                        if _should_backfill(key, extraction_context.get(key), value):
                            extraction_context[key] = value
                    break
            if not fallback_attrs:
                logger.warning("No fallback extraction info found for %s.", lookup_id)
        else:
            for fallback_lookup_id in _fallback_lookup_ids():
                fallback_attrs = self.extraction_fallback_fetcher(fallback_lookup_id)
                if fallback_attrs:
                    for key, value in fallback_attrs.items():
                        if _should_backfill(key, extraction_context.get(key), value):
                            extraction_context[key] = value
                    break

        extraction_protocol = extraction_context.get("extraction_protocol")
        legacy_protocol = extraction_context.get("protocol")
        if _is_missing(extraction_protocol) and not _is_missing(legacy_protocol):
            extraction_context["extraction_protocol"] = legacy_protocol
        elif _is_missing(legacy_protocol) and not _is_missing(extraction_protocol):
            extraction_context["protocol"] = extraction_protocol

        if _is_missing(extraction_context.get("sanger_sample_id")):
            extraction_context["sanger_sample_id"] = lookup_id

        return ExtractionInfo.from_mapping(extraction_context)

    def build_barcoding(self, tolid: str | None) -> BarcodingInfo:
        if not tolid:
            return BarcodingInfo()
        return BarcodingInfo.from_mapping(self.barcoding_fetcher(tolid))
