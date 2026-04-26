from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TaxonomyInfo:
    tax_id: str | None = None
    species: str | None = None
    lineage: str | None = None
    phylum: str | None = None
    class_name: str | None = None
    order: str | None = None
    family: str | None = None
    genus: str | None = None
    tax_auth: str | None = None
    common_name: str | None = None
    gbif_url: str | None = None
    gbif_usage_key: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy_parts(
        cls,
        *,
        tax_id: str | None = None,
        lineage_data: dict[str, Any] | None = None,
        gbif_data: dict[str, Any] | None = None,
    ) -> "TaxonomyInfo":
        lineage_data = lineage_data or {}
        gbif_data = gbif_data or {}
        consumed = {
            "species",
            "lineage",
            "phylum",
            "class",
            "order",
            "family",
            "genus",
            "tax_auth",
            "common_name",
            "gbif_url",
            "gbif_usage_key",
        }
        extras = {
            key: value
            for source in (lineage_data, gbif_data)
            for key, value in source.items()
            if key not in consumed
        }
        return cls(
            tax_id=str(tax_id) if tax_id is not None else lineage_data.get("tax_id"),
            species=lineage_data.get("species"),
            lineage=lineage_data.get("lineage"),
            phylum=lineage_data.get("phylum"),
            class_name=lineage_data.get("class"),
            order=lineage_data.get("order"),
            family=lineage_data.get("family"),
            genus=lineage_data.get("genus"),
            tax_auth=gbif_data.get("tax_auth"),
            common_name=gbif_data.get("common_name"),
            gbif_url=gbif_data.get("gbif_url"),
            gbif_usage_key=gbif_data.get("gbif_usage_key"),
            extras=extras,
        )

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        if self.tax_id is not None:
            context["tax_id"] = self.tax_id
        mappings = {
            "species": self.species,
            "lineage": self.lineage,
            "phylum": self.phylum,
            "class": self.class_name,
            "order": self.order,
            "family": self.family,
            "genus": self.genus,
            "tax_auth": self.tax_auth,
            "common_name": self.common_name,
            "gbif_url": self.gbif_url,
            "gbif_usage_key": self.gbif_usage_key,
        }
        for key, value in mappings.items():
            if value is not None:
                context[key] = value
        context.update(self.extras)
        return context


@dataclass(slots=True)
class AnnotationInfo:
    annot_url: str | None = None
    annot_accession: str | None = None
    source: str | None = None
    prot_genes: Any = None
    pseudogenes: Any = None
    non_coding: Any = None
    genes: Any = None
    transcripts: Any = None
    av_transc: Any = None
    av_exon: Any = None
    av_gene_length: Any = None
    av_transcript_length: Any = None
    av_exon_length: Any = None
    av_intron_length: Any = None
    av_cds_length: Any = None
    ensembl_annotation_url: str | None = None
    ensembl_annotation_file_url: str | None = None
    ensembl_source: str | None = None
    ensembl_species: str | None = None
    ensembl_search_strategy: str | None = None
    annot_method: str | None = None
    download_error: str | None = None
    processing_error: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "AnnotationInfo":
        data = data or {}
        field_names = {field.name for field in cls.__dataclass_fields__.values() if field.name != "extras"}
        return cls(
            **{name: data.get(name) for name in field_names},
            extras={key: value for key, value in data.items() if key not in field_names},
        )

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            if name == "extras":
                continue
            value = getattr(self, name)
            if value is not None:
                context[name] = value
        context.update(self.extras)
        return context
