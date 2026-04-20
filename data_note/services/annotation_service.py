from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_ensembl_info import create_ensembl_dict
from ..models import AnnotationInfo


@dataclass(slots=True)
class AnnotationService:
    annotation_fetcher: Callable[[str, str, str | int], dict[str, Any]] = create_ensembl_dict

    def build_context(
        self,
        assembly_accession: str | None,
        species: str,
        tax_id: str | int | None,
    ) -> AnnotationInfo:
        if not assembly_accession:
            return AnnotationInfo()
        return AnnotationInfo.from_mapping(self.annotation_fetcher(assembly_accession, species, tax_id))
