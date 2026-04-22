from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .author import AuthorInfo
from .assembly import AssemblyBundle
from .base_note import BaseNoteInfo
from .curation import CurationBundle
from .flow_cytometry import FlowCytometryInfo
from .metadata import AnnotationInfo, TaxonomyInfo
from .quality import QualityMetrics
from .sampling import SamplingInfo
from .sequencing import SequencingSummary


@dataclass(slots=True)
class NoteData:
    base: BaseNoteInfo = field(default_factory=BaseNoteInfo)
    taxonomy: TaxonomyInfo | None = None
    assembly: AssemblyBundle | None = None
    sequencing: SequencingSummary | None = None
    flow_cytometry: FlowCytometryInfo | None = None
    curation: CurationBundle | None = None
    sampling: SamplingInfo | None = None
    quality: QualityMetrics | None = None
    annotation: AnnotationInfo | None = None
    author: AuthorInfo | None = None
    extra_sections: list[Any] = field(default_factory=list)

    def context_sections(self) -> tuple[Any, ...]:
        sections: list[Any] = [self.base]
        if self.taxonomy is not None:
            sections.append(self.taxonomy)
        if self.assembly is not None:
            sections.append(self.assembly)
        if self.sequencing is not None:
            sections.append(self.sequencing)
        if self.flow_cytometry is not None:
            sections.append(self.flow_cytometry)
        if self.curation is not None:
            sections.append(self.curation)
        if self.sampling is not None:
            sections.append(self.sampling)
        if self.quality is not None:
            sections.append(self.quality)
        if self.annotation is not None:
            sections.append(self.annotation)
        if self.author is not None:
            sections.append(self.author)
        sections.extend(self.extra_sections)
        return tuple(sections)
