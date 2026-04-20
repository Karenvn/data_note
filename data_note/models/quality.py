from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GenomeScopeSummary:
    size_mb: Any = None
    heterozygosity_percent: Any = None
    repeat_percent: Any = None
    error_rate_percent: Any = None
    unique_percent: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "GenomeScopeSummary":
        consumed = {
            "gscope_size",
            "gscope_het",
            "gscope_repeat",
            "gscope_error",
            "gscope_unique",
        }
        return cls(
            size_mb=data.get("gscope_size"),
            heterozygosity_percent=data.get("gscope_het"),
            repeat_percent=data.get("gscope_repeat"),
            error_rate_percent=data.get("gscope_error"),
            unique_percent=data.get("gscope_unique"),
            extras={key: value for key, value in data.items() if key not in consumed},
        )

    def to_context_dict(self) -> dict[str, Any]:
        context = {
            "gscope_size": self.size_mb,
            "gscope_het": self.heterozygosity_percent,
            "gscope_repeat": self.repeat_percent,
            "gscope_error": self.error_rate_percent,
            "gscope_unique": self.unique_percent,
        }
        context.update(self.extras)
        return context


@dataclass(slots=True)
class MerquryRecord:
    name: str
    qv: Any = None
    kmer_completeness_percent: Any = None


@dataclass(slots=True)
class MerqurySummary:
    records: dict[str, MerquryRecord] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "MerqurySummary":
        known_names = ("prim", "alt", "hap1", "hap2", "combined")
        records: dict[str, MerquryRecord] = {}
        consumed: set[str] = set()
        for name in known_names:
            qv_key = f"{name}_QV"
            completeness_key = f"{name}_kmer_completeness"
            if qv_key in data or completeness_key in data:
                records[name] = MerquryRecord(
                    name=name,
                    qv=data.get(qv_key),
                    kmer_completeness_percent=data.get(completeness_key),
                )
                consumed.add(qv_key)
                consumed.add(completeness_key)
        return cls(records=records, extras={key: value for key, value in data.items() if key not in consumed})

    def record(self, name: str) -> MerquryRecord | None:
        return self.records.get(name)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for name, record in self.records.items():
            context[f"{name}_QV"] = record.qv
            context[f"{name}_kmer_completeness"] = record.kmer_completeness_percent
        context.update(self.extras)
        return context


@dataclass(slots=True)
class QualityMetrics:
    genomescope: GenomeScopeSummary = field(default_factory=GenomeScopeSummary)
    merqury: MerqurySummary = field(default_factory=MerqurySummary)

    @classmethod
    def from_legacy_parts(
        cls,
        *,
        genomescope: dict[str, Any],
        merqury: dict[str, Any],
    ) -> "QualityMetrics":
        return cls(
            genomescope=GenomeScopeSummary.from_mapping(genomescope or {}),
            merqury=MerqurySummary.from_mapping(merqury or {}),
        )

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        context.update(self.genomescope.to_context_dict())
        context.update(self.merqury.to_context_dict())
        return context
