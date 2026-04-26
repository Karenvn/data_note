from __future__ import annotations

from dataclasses import dataclass, field

from ..ensembl_annotation_fetcher import EnsemblAnnotationFetcher
from ..models import AnnotationInfo


@dataclass(slots=True)
class AnnotationService:
    annotation_fetcher: EnsemblAnnotationFetcher = field(default_factory=EnsemblAnnotationFetcher)

    def build_context(
        self,
        assembly_accession: str | None,
        species: str,
        tax_id: str | int | None,
    ) -> AnnotationInfo:
        if not assembly_accession:
            return AnnotationInfo()
        return AnnotationInfo.from_mapping(
            self.annotation_fetcher.fetch_annotation(assembly_accession, species, tax_id)
        )
