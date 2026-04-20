from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RunRecord:
    read_accession: str | None = None
    sample_accession: str | None = None
    fastq_bytes: Any = None
    submitted_bytes: Any = None
    read_count: Any = None
    instrument_model: str | None = None
    base_count_gb: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RunRecord":
        consumed = {
            "read_accession",
            "sample_accession",
            "fastq_bytes",
            "submitted_bytes",
            "read_count",
            "instrument_model",
            "base_count_gb",
        }
        return cls(
            read_accession=data.get("read_accession"),
            sample_accession=data.get("sample_accession"),
            fastq_bytes=data.get("fastq_bytes"),
            submitted_bytes=data.get("submitted_bytes"),
            read_count=data.get("read_count"),
            instrument_model=data.get("instrument_model"),
            base_count_gb=data.get("base_count_gb"),
            extras={key: value for key, value in data.items() if key not in consumed},
        )

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}

        def set_if_present(field_name: str, value: Any) -> None:
            if value is not None:
                context[field_name] = value

        set_if_present("read_accession", self.read_accession)
        set_if_present("sample_accession", self.sample_accession)
        set_if_present("fastq_bytes", self.fastq_bytes)
        set_if_present("submitted_bytes", self.submitted_bytes)
        set_if_present("read_count", self.read_count)
        set_if_present("instrument_model", self.instrument_model)
        set_if_present("base_count_gb", self.base_count_gb)
        context.update(self.extras)
        return context


@dataclass(slots=True)
class RunGroup:
    name: str
    runs: list[RunRecord] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, name: str, rows: list[dict[str, Any]]) -> "RunGroup":
        return cls(name=name, runs=[RunRecord.from_mapping(row) for row in rows])

    def to_context_rows(self) -> list[dict[str, Any]]:
        return [run.to_context_dict() for run in self.runs]


@dataclass(slots=True)
class TechnologyRecord:
    name: str
    sample_accession: str | None = None
    instrument_model: str | None = None
    library_construction_protocol: str | None = None
    library_name: str | None = None
    base_count_gb: Any = None
    read_count_millions: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, name: str, data: dict[str, Any]) -> "TechnologyRecord":
        prefix = f"{name}_"

        def get(field_name: str) -> Any:
            return data.get(f"{prefix}{field_name}")

        consumed = {
            f"{prefix}sample_accession",
            f"{prefix}instrument_model",
            f"{prefix}library_construction_protocol",
            f"{prefix}library_name",
            f"{prefix}base_count_gb",
            f"{prefix}read_count_millions",
        }

        return cls(
            name=name,
            sample_accession=get("sample_accession"),
            instrument_model=get("instrument_model"),
            library_construction_protocol=get("library_construction_protocol"),
            library_name=get("library_name"),
            base_count_gb=get("base_count_gb"),
            read_count_millions=get("read_count_millions"),
            extras={key: value for key, value in data.items() if key not in consumed},
        )

    def to_context_dict(self) -> dict[str, Any]:
        prefix = f"{self.name}_"
        context: dict[str, Any] = {}

        def set_if_present(field_name: str, value: Any) -> None:
            if value is not None:
                context[f"{prefix}{field_name}"] = value

        set_if_present("sample_accession", self.sample_accession)
        set_if_present("instrument_model", self.instrument_model)
        set_if_present("library_construction_protocol", self.library_construction_protocol)
        set_if_present("library_name", self.library_name)
        set_if_present("base_count_gb", self.base_count_gb)
        set_if_present("read_count_millions", self.read_count_millions)
        context.update(self.extras)
        return context


@dataclass(slots=True)
class SequencingTotals:
    pacbio_total_reads: Any = None
    pacbio_total_bases: Any = None
    pacbio_reads_millions: Any = None
    pacbio_bases_gb: Any = None
    pacbio_sample_accession: str | None = None
    pacbio_instrument: str | None = None
    hic_total_reads: Any = None
    hic_total_bases: Any = None
    hic_reads_millions: Any = None
    hic_bases_gb: Any = None
    hic_sample_accession: str | None = None
    hic_instrument: str | None = None
    rna_total_reads: Any = None
    rna_total_bases: Any = None
    rna_reads_millions: Any = None
    rna_bases_gb: Any = None
    rna_sample_accession: str | None = None
    rna_instrument: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "SequencingTotals":
        consumed = {
            "pacbio_total_reads",
            "pacbio_total_bases",
            "pacbio_reads_millions",
            "pacbio_bases_gb",
            "pacbio_sample_accession",
            "pacbio_instrument",
            "hic_total_reads",
            "hic_total_bases",
            "hic_reads_millions",
            "hic_bases_gb",
            "hic_sample_accession",
            "hic_instrument",
            "rna_total_reads",
            "rna_total_bases",
            "rna_reads_millions",
            "rna_bases_gb",
            "rna_sample_accession",
            "rna_instrument",
        }
        return cls(
            pacbio_total_reads=data.get("pacbio_total_reads"),
            pacbio_total_bases=data.get("pacbio_total_bases"),
            pacbio_reads_millions=data.get("pacbio_reads_millions"),
            pacbio_bases_gb=data.get("pacbio_bases_gb"),
            pacbio_sample_accession=data.get("pacbio_sample_accession"),
            pacbio_instrument=data.get("pacbio_instrument"),
            hic_total_reads=data.get("hic_total_reads"),
            hic_total_bases=data.get("hic_total_bases"),
            hic_reads_millions=data.get("hic_reads_millions"),
            hic_bases_gb=data.get("hic_bases_gb"),
            hic_sample_accession=data.get("hic_sample_accession"),
            hic_instrument=data.get("hic_instrument"),
            rna_total_reads=data.get("rna_total_reads"),
            rna_total_bases=data.get("rna_total_bases"),
            rna_reads_millions=data.get("rna_reads_millions"),
            rna_bases_gb=data.get("rna_bases_gb"),
            rna_sample_accession=data.get("rna_sample_accession"),
            rna_instrument=data.get("rna_instrument"),
            extras={key: value for key, value in data.items() if key not in consumed},
        )

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for field_name in (
            "pacbio_total_reads",
            "pacbio_total_bases",
            "pacbio_reads_millions",
            "pacbio_bases_gb",
            "pacbio_sample_accession",
            "pacbio_instrument",
            "hic_total_reads",
            "hic_total_bases",
            "hic_reads_millions",
            "hic_bases_gb",
            "hic_sample_accession",
            "hic_instrument",
            "rna_total_reads",
            "rna_total_bases",
            "rna_reads_millions",
            "rna_bases_gb",
            "rna_sample_accession",
            "rna_instrument",
        ):
            value = getattr(self, field_name)
            if value is not None:
                context[field_name] = value
        context.update(self.extras)
        return context


@dataclass(slots=True)
class SequencingSummary:
    technology_records: dict[str, TechnologyRecord] = field(default_factory=dict)
    run_groups: dict[str, RunGroup] = field(default_factory=dict)
    totals: SequencingTotals = field(default_factory=SequencingTotals)
    pacbio_protocols: list[str] = field(default_factory=list)
    run_accessions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_legacy_parts(
        cls,
        *,
        technology_data: dict[str, Any],
        seq_data: dict[str, Any],
        totals: dict[str, Any],
        pacbio_protocols: list[str],
        run_accessions: dict[str, str],
    ) -> "SequencingSummary":
        return cls(
            technology_records={
                name: TechnologyRecord.from_mapping(name, values or {})
                for name, values in technology_data.items()
            },
            run_groups={
                name: RunGroup.from_mapping(name, rows or [])
                for name, rows in seq_data.items()
            },
            totals=SequencingTotals.from_mapping(totals or {}),
            pacbio_protocols=pacbio_protocols,
            run_accessions=run_accessions,
        )

    @property
    def technology_data(self) -> dict[str, Any]:
        return {
            name: record.to_context_dict()
            for name, record in self.technology_records.items()
        }

    def technology(self, name: str) -> TechnologyRecord | None:
        return self.technology_records.get(name)

    @property
    def seq_data(self) -> dict[str, Any]:
        return {
            name: group.to_context_rows()
            for name, group in self.run_groups.items()
        }

    def run_group(self, name: str) -> RunGroup | None:
        return self.run_groups.get(name)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {
            "technology_data": self.technology_data,
            "seq_data": self.seq_data,
            **self.totals.to_context_dict(),
            "pacbio_protocols": self.pacbio_protocols,
            **self.run_accessions,
        }
        return context

    def pacbio_library_name(self) -> str | None:
        pacbio = self.technology("pacbio")
        library_name = pacbio.library_name if pacbio is not None else None
        if library_name in (None, ""):
            return None
        return str(library_name)
