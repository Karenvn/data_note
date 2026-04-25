from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


AssemblyMode = Literal["prim_alt", "hap_asm", "multiple_primary"]
AssemblyRole = Literal["primary", "alternate", "hap1", "hap2"]


@dataclass(slots=True)
class AssemblyCandidate:
    accession: str
    assembly_name: str
    tax_id: str = ""
    study_accession: str = ""
    accession_field: str = "assembly_set_accession"
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        accession_key: str = "assembly_set_accession",
    ) -> "AssemblyCandidate":
        consumed = {
            accession_key,
            "assembly_name",
            "tax_id",
            "study_accession",
        }
        return cls(
            accession=str(data.get(accession_key) or ""),
            assembly_name=str(data.get("assembly_name") or ""),
            tax_id=str(data.get("tax_id") or ""),
            study_accession=str(data.get("study_accession") or ""),
            accession_field=accession_key,
            extras={key: value for key, value in data.items() if key not in consumed},
        )

    def to_mapping(self) -> dict[str, Any]:
        mapping = dict(self.extras)
        mapping[self.accession_field] = self.accession
        mapping["assembly_name"] = self.assembly_name
        if self.tax_id:
            mapping["tax_id"] = self.tax_id
        if self.study_accession:
            mapping["study_accession"] = self.study_accession
        return mapping

    def to_record(self, role: AssemblyRole, *, assembly_name: str | None = None) -> "AssemblyRecord":
        return AssemblyRecord(
            accession=self.accession,
            assembly_name=assembly_name if assembly_name is not None else self.assembly_name,
            role=role,
        )


@dataclass(slots=True)
class AssemblyRecord:
    accession: str
    assembly_name: str
    role: AssemblyRole

    def validate(self) -> None:
        if not self.accession:
            raise ValueError(f"{self.role} assembly is missing an accession")
        if not self.assembly_name:
            raise ValueError(f"{self.role} assembly is missing an assembly name")


@dataclass(slots=True)
class AssemblySelection:
    assemblies_type: AssemblyMode
    primary: AssemblyRecord | None = None
    alternate: AssemblyRecord | None = None
    hap1: AssemblyRecord | None = None
    hap2: AssemblyRecord | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.assemblies_type == "prim_alt":
            if self.primary is not None:
                self.primary.validate()
            if self.alternate is not None:
                self.alternate.validate()
        elif self.assemblies_type == "hap_asm":
            if self.hap1 is not None:
                self.hap1.validate()
            if self.hap2 is not None:
                self.hap2.validate()

    def to_context_dict(self) -> dict[str, Any]:
        context = {"assemblies_type": self.assemblies_type, **self.extras}
        if self.primary is not None:
            context["prim_accession"] = self.primary.accession
            context["prim_assembly_name"] = self.primary.assembly_name
        if self.alternate is not None:
            context["alt_accession"] = self.alternate.accession
            context["alt_assembly_name"] = self.alternate.assembly_name
        if self.hap1 is not None:
            context["hap1_accession"] = self.hap1.accession
            context["hap1_assembly_name"] = self.hap1.assembly_name
        if self.hap2 is not None:
            context["hap2_accession"] = self.hap2.accession
            context["hap2_assembly_name"] = self.hap2.assembly_name
        return context

    def assembly_accessions(self) -> dict[str, str | None]:
        return {
            "prim_accession": self.primary.accession if self.primary is not None else None,
            "hap1_accession": self.hap1.accession if self.hap1 is not None else None,
            "hap2_accession": self.hap2.accession if self.hap2 is not None else None,
        }

    def preferred_record(self) -> AssemblyRecord | None:
        if self.assemblies_type == "prim_alt":
            return self.primary
        if self.assemblies_type == "hap_asm":
            return self.hap1
        return self.primary or self.hap1

    def preferred_accession(self) -> str | None:
        record = self.preferred_record()
        return record.accession if record is not None else None

    def preferred_assembly_name(self) -> str | None:
        record = self.preferred_record()
        return record.assembly_name if record is not None else None


@dataclass(slots=True)
class AssemblySelectionInput:
    assembly_accession: str | None = None
    alternate_accession: str | None = None
    hap1_accession: str | None = None
    hap2_accession: str | None = None

    def has_any(self) -> bool:
        return any(
            [
                self.assembly_accession,
                self.alternate_accession,
                self.hap1_accession,
                self.hap2_accession,
            ]
        )

    def validate(self) -> None:
        if self.assembly_accession and (self.hap1_accession or self.hap2_accession):
            raise ValueError(
                "Use either assembly/alternate assembly inputs or hap1/hap2 assembly inputs, not both"
            )
        if self.alternate_accession and not self.assembly_accession:
            raise ValueError("An alternate assembly input requires an assembly input")
        if self.hap2_accession and not self.hap1_accession:
            raise ValueError("A hap2 assembly input requires a hap1 assembly input")


@dataclass(slots=True)
class AssemblyCoverageInput:
    assemblies_type: AssemblyMode
    primary_accession: str | None = None
    hap1_accession: str | None = None
    hap2_accession: str | None = None
    genome_length_unrounded: float | None = None
    hap1_genome_length_unrounded: float | None = None
    hap2_genome_length_unrounded: float | None = None

    @classmethod
    def from_selection_and_context(
        cls,
        selection: AssemblySelection,
        context: Mapping[str, Any],
    ) -> "AssemblyCoverageInput":
        if selection.assemblies_type == "prim_alt":
            return cls(
                assemblies_type="prim_alt",
                primary_accession=selection.primary.accession if selection.primary is not None else None,
                genome_length_unrounded=_as_float(context.get("genome_length_unrounded")),
            )
        if selection.assemblies_type == "hap_asm":
            return cls(
                assemblies_type="hap_asm",
                hap1_accession=selection.hap1.accession if selection.hap1 is not None else None,
                hap2_accession=selection.hap2.accession if selection.hap2 is not None else None,
                hap1_genome_length_unrounded=_as_float(context.get("hap1_genome_length_unrounded")),
                hap2_genome_length_unrounded=_as_float(context.get("hap2_genome_length_unrounded")),
            )
        return cls(assemblies_type=selection.assemblies_type)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "AssemblyCoverageInput":
        return cls(
            assemblies_type=str(data.get("assemblies_type") or "prim_alt"),
            primary_accession=data.get("prim_accession"),
            hap1_accession=data.get("hap1_accession"),
            hap2_accession=data.get("hap2_accession"),
            genome_length_unrounded=_as_float(data.get("genome_length_unrounded")),
            hap1_genome_length_unrounded=_as_float(data.get("hap1_genome_length_unrounded")),
            hap2_genome_length_unrounded=_as_float(data.get("hap2_genome_length_unrounded")),
        )

    def validate(self) -> None:
        if self.assemblies_type == "prim_alt" and not self.primary_accession:
            raise ValueError("Primary assembly coverage input requires a primary accession")
        if self.assemblies_type == "hap_asm":
            if not self.hap1_accession:
                raise ValueError("Haplotype coverage input requires hap1 accession")
            if not self.hap2_accession:
                raise ValueError("Haplotype coverage input requires hap2 accession")


@dataclass(slots=True)
class AssemblyDatasetRecord:
    assembly_level: str | None = None
    total_length: Any = None
    num_contigs: Any = None
    contig_N50: Any = None
    num_scaffolds: Any = None
    scaffold_N50: Any = None
    chromosome_count: Any = None
    genome_length_unrounded: float | None = None
    coverage: Any = None
    longest_scaffold_length: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        prefix: str = "",
    ) -> "AssemblyDatasetRecord":
        def get(key: str) -> Any:
            return data.get(f"{prefix}{key}")

        consumed = {
            f"{prefix}assembly_level",
            f"{prefix}total_length",
            f"{prefix}num_contigs",
            f"{prefix}contig_N50",
            f"{prefix}num_scaffolds",
            f"{prefix}scaffold_N50",
            f"{prefix}chromosome_count",
            f"{prefix}genome_length_unrounded",
            f"{prefix}coverage",
            f"{prefix}longest_scaffold_length",
        }

        return cls(
            assembly_level=get("assembly_level"),
            total_length=get("total_length"),
            num_contigs=get("num_contigs"),
            contig_N50=get("contig_N50"),
            num_scaffolds=get("num_scaffolds"),
            scaffold_N50=get("scaffold_N50"),
            chromosome_count=get("chromosome_count"),
            genome_length_unrounded=_as_float(get("genome_length_unrounded")),
            coverage=get("coverage"),
            longest_scaffold_length=get("longest_scaffold_length"),
            extras={k: v for k, v in data.items() if k not in consumed},
        )

    def to_context_dict(self, *, prefix: str = "") -> dict[str, Any]:
        context: dict[str, Any] = {}

        def set_if_present(key: str, value: Any) -> None:
            if value is not None:
                context[f"{prefix}{key}"] = value

        set_if_present("assembly_level", self.assembly_level)
        set_if_present("total_length", self.total_length)
        set_if_present("num_contigs", self.num_contigs)
        set_if_present("contig_N50", self.contig_N50)
        set_if_present("num_scaffolds", self.num_scaffolds)
        set_if_present("scaffold_N50", self.scaffold_N50)
        set_if_present("chromosome_count", self.chromosome_count)
        set_if_present("genome_length_unrounded", self.genome_length_unrounded)
        set_if_present("coverage", self.coverage)
        set_if_present("longest_scaffold_length", self.longest_scaffold_length)
        for key, value in self.extras.items():
            context[key] = value
        return context


@dataclass(slots=True)
class AssemblyDatasetsInfo:
    assemblies_type: AssemblyMode
    primary: AssemblyDatasetRecord | None = None
    hap1: AssemblyDatasetRecord | None = None
    hap2: AssemblyDatasetRecord | None = None
    shared_fields: dict[str, Any] = field(default_factory=dict)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = dict(self.shared_fields)
        if self.primary is not None:
            context.update(self.primary.to_context_dict())
        if self.hap1 is not None:
            context.update(self.hap1.to_context_dict(prefix="hap1_"))
        if self.hap2 is not None:
            context.update(self.hap2.to_context_dict(prefix="hap2_"))
        return context


@dataclass(slots=True)
class ChromosomeSummary:
    chromosome_data: list[dict[str, Any]] | None = None
    hap1_chromosome_data: list[dict[str, Any]] | None = None
    sex_chromosomes: str | None = None
    hap1_sex_chromosomes: str | None = None
    hap2_sex_chromosomes: str | None = None
    all_sex_chromosomes: str | None = None
    supernumerary_chromosomes: str | None = None
    hap1_supernumerary_chromosomes: str | None = None
    hap2_supernumerary_chromosomes: str | None = None
    all_supernumerary_chromosomes: str | None = None

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for key in (
            "chromosome_data",
            "hap1_chromosome_data",
            "sex_chromosomes",
            "hap1_sex_chromosomes",
            "hap2_sex_chromosomes",
            "all_sex_chromosomes",
            "supernumerary_chromosomes",
            "hap1_supernumerary_chromosomes",
            "hap2_supernumerary_chromosomes",
            "all_supernumerary_chromosomes",
        ):
            value = getattr(self, key)
            if value is not None:
                context[key] = value
        return context


@dataclass(slots=True)
class BtkAssemblyRecord:
    summary_fields: dict[str, Any] = field(default_factory=dict)
    view_urls: dict[str, Any] = field(default_factory=dict)
    download_urls: dict[str, Any] = field(default_factory=dict)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        context.update(self.summary_fields)
        context.update(self.view_urls)
        context.update(self.download_urls)
        return context


@dataclass(slots=True)
class BtkSummary:
    assemblies_type: AssemblyMode
    primary: BtkAssemblyRecord | None = None
    hap1: BtkAssemblyRecord | None = None
    hap2: BtkAssemblyRecord | None = None
    shared_fields: dict[str, Any] = field(default_factory=dict)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = dict(self.shared_fields)
        if self.primary is not None:
            context.update(self.primary.to_context_dict())
        if self.hap1 is not None:
            context.update(self.hap1.to_context_dict())
        if self.hap2 is not None:
            context.update(self.hap2.to_context_dict())
        return context


@dataclass(slots=True)
class AssemblyBundle:
    selection: AssemblySelection
    datasets: AssemblyDatasetsInfo | None = None
    chromosomes: ChromosomeSummary | None = None
    btk: BtkSummary | None = None
    coverage_fields: dict[str, Any] = field(default_factory=dict)

    @property
    def assemblies_type(self) -> AssemblyMode:
        return self.selection.assemblies_type

    def preferred_accession(self) -> str | None:
        return self.selection.preferred_accession()

    def preferred_assembly_name(self) -> str | None:
        return self.selection.preferred_assembly_name()

    def to_context_dict(self) -> dict[str, Any]:
        context = self.selection.to_context_dict()
        if self.datasets is not None:
            context.update(self.datasets.to_context_dict())
        if self.chromosomes is not None:
            context.update(self.chromosomes.to_context_dict())
        if self.btk is not None:
            context.update(self.btk.to_context_dict())
        context.update(self.coverage_fields)
        return context


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
