from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CurationInfo:
    jira_ticket: str | None = None
    jira_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy_parts(
        cls,
        *,
        jira_ticket: str | None = None,
        jira_fields: dict[str, Any] | None = None,
    ) -> "CurationInfo":
        return cls(
            jira_ticket=jira_ticket,
            jira_fields=dict(jira_fields or {}),
        )

    def has_ticket(self) -> bool:
        return bool(self.jira_ticket)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        if self.jira_ticket:
            context["jira"] = self.jira_ticket
        context.update(self.jira_fields)
        return context


@dataclass(slots=True)
class ExtractionInfo:
    sequencing_date: Any = None
    platform: Any = None
    submission_id: Any = None
    submission_name: Any = None
    estimated_max_oplc: Any = None
    library_remaining: Any = None
    library_remaining_oplc: Any = None
    portion_of_cell: Any = None
    pacbio_run_count: Any = None
    sanger_sample_id: Any = None
    dna_yield_ng: Any = None
    volume_ul: Any = None
    qubit_ngul: Any = None
    ratio_260_280: Any = None
    ratio_260_230: Any = None
    nanodrop_concentration_ngul: Any = None
    extraction_date: Any = None
    fragment_size_kb: Any = None
    gqn: Any = None
    extraction_protocol: Any = None
    protocol: Any = None
    spri_type: Any = None
    disruption_method: Any = None
    extraction_mode: Any = None
    extraction_uid: Any = None
    tissue_weight_mg: Any = None
    tissue_weight_mg_calc: Any = None
    tissue_prep_uid: Any = None
    tissue_size_in_tube: Any = None
    tissue_remaining_weight: Any = None
    tissue_remaining_weight_calc: Any = None
    tissue_size: Any = None
    tissue_remaining: Any = None
    tissue_depleted: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "ExtractionInfo":
        data = data or {}
        field_names = {field.name for field in cls.__dataclass_fields__.values() if field.name != "extras"}
        return cls(
            **{name: data.get(name) for name in field_names},
            extras={key: value for key, value in data.items() if key not in field_names},
        )

    def to_context_dict(self) -> dict[str, Any]:
        context = {}
        for name, field_info in self.__dataclass_fields__.items():
            if name == "extras":
                continue
            value = getattr(self, name)
            if value is not None:
                context[name] = value
        context.update(self.extras)
        return context


@dataclass(slots=True)
class BarcodingInfo:
    sts_tremoved: Any = None
    barcode_hub: Any = None
    eln_id: Any = None
    sample_set_id: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "BarcodingInfo":
        data = data or {}
        field_names = {field.name for field in cls.__dataclass_fields__.values() if field.name != "extras"}
        return cls(
            **{name: data.get(name) for name in field_names},
            extras={key: value for key, value in data.items() if key not in field_names},
        )

    def to_context_dict(self) -> dict[str, Any]:
        context = {}
        for name, field_info in self.__dataclass_fields__.items():
            if name == "extras":
                continue
            value = getattr(self, name)
            if value is not None:
                context[name] = value
        context.update(self.extras)
        return context


@dataclass(slots=True)
class CurationBundle:
    local_metadata: CurationInfo = field(default_factory=CurationInfo)
    extraction: ExtractionInfo = field(default_factory=ExtractionInfo)
    barcoding: BarcodingInfo = field(default_factory=BarcodingInfo)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        context.update(self.local_metadata.to_context_dict())
        context.update(self.extraction.to_context_dict())
        context.update(self.barcoding.to_context_dict())
        return context
