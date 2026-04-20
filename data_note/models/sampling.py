from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SampleMetadataRecord:
    name: str
    collector: str | None = None
    collector_institute: str | None = None
    gal_name: str | None = None
    coll_date: str | None = None
    coll_location: str | None = None
    coll_lat: Any = None
    coll_long: Any = None
    identifier: str | None = None
    identifier_affiliation: str | None = None
    identified_how: str | None = None
    sample_derived_from: str | None = None
    sex: str | None = None
    lifestage: str | None = None
    specimen_id: str | None = None
    organism_part: str | None = None
    coll_method: str | None = None
    preserv_method: str | None = None
    preservative_solution: str | None = None
    species: str | None = None
    elevation_m: Any = None
    tolid: str | None = None

    @classmethod
    def from_mapping(cls, name: str, data: dict[str, Any]) -> "SampleMetadataRecord":
        prefix = f"{name}_"

        def get(field_name: str) -> Any:
            return data.get(f"{prefix}{field_name}")

        return cls(
            name=name,
            collector=get("collector"),
            collector_institute=get("collector_institute"),
            gal_name=get("gal_name"),
            coll_date=get("coll_date"),
            coll_location=get("coll_location"),
            coll_lat=get("coll_lat"),
            coll_long=get("coll_long"),
            identifier=get("identifier"),
            identifier_affiliation=get("identifier_affiliation"),
            identified_how=get("identified_how"),
            sample_derived_from=get("sample_derived_from"),
            sex=get("sex"),
            lifestage=get("lifestage"),
            specimen_id=get("specimen_id"),
            organism_part=get("organism_part"),
            coll_method=get("coll_method"),
            preserv_method=get("preserv_method"),
            preservative_solution=get("preservative_solution"),
            species=get("species"),
            elevation_m=get("elevation_m"),
            tolid=get("tolid"),
        )

    def to_context_dict(self) -> dict[str, Any]:
        prefix = f"{self.name}_"
        context: dict[str, Any] = {}

        for field_name in (
            "collector",
            "collector_institute",
            "gal_name",
            "coll_date",
            "coll_location",
            "coll_lat",
            "coll_long",
            "identifier",
            "identifier_affiliation",
            "identified_how",
            "sample_derived_from",
            "sex",
            "lifestage",
            "specimen_id",
            "organism_part",
            "coll_method",
            "preserv_method",
            "preservative_solution",
            "species",
            "elevation_m",
            "tolid",
        ):
            value = getattr(self, field_name)
            if value is not None:
                context[f"{prefix}{field_name}"] = value

        return context


@dataclass(slots=True)
class SamplingInfo:
    pacbio: SampleMetadataRecord | None = None
    rna: SampleMetadataRecord | None = None
    hic: SampleMetadataRecord | None = None
    isoseq: SampleMetadataRecord | None = None

    @classmethod
    def from_legacy_dicts(
        cls,
        *,
        pacbio: dict[str, Any] | None = None,
        rna: dict[str, Any] | None = None,
        hic: dict[str, Any] | None = None,
        isoseq: dict[str, Any] | None = None,
    ) -> "SamplingInfo":
        return cls(
            pacbio=SampleMetadataRecord.from_mapping("pacbio", pacbio or {}) if pacbio else None,
            rna=SampleMetadataRecord.from_mapping("rna", rna or {}) if rna else None,
            hic=SampleMetadataRecord.from_mapping("hic", hic or {}) if hic else None,
            isoseq=SampleMetadataRecord.from_mapping("isoseq", isoseq or {}) if isoseq else None,
        )

    def record(self, name: str) -> SampleMetadataRecord | None:
        return getattr(self, name, None)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for record in (self.pacbio, self.rna, self.hic, self.isoseq):
            if record is not None:
                context.update(record.to_context_dict())
        return context
