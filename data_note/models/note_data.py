from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AssemblyBundle
from .curation import CurationBundle
from .quality import QualityMetrics
from .sampling import SamplingInfo
from .sequencing import SequencingSummary


@dataclass(slots=True)
class NoteData:
    base_context: dict[str, Any] = field(default_factory=dict)
    assembly: AssemblyBundle | None = None
    sequencing: SequencingSummary | None = None
    curation: CurationBundle | None = None
    sampling: SamplingInfo | None = None
    quality: QualityMetrics | None = None
    annotation_context: dict[str, Any] = field(default_factory=dict)
    author_context: dict[str, Any] = field(default_factory=dict)
    extra_sections: list[Any] = field(default_factory=list)

    def context_sections(self) -> tuple[Any, ...]:
        sections: list[Any] = [self.base_context]
        if self.assembly is not None:
            sections.append(self.assembly)
        if self.sequencing is not None:
            sections.append(self.sequencing)
        if self.curation is not None:
            sections.append(self.curation)
        if self.sampling is not None:
            sections.append(self.sampling)
        if self.annotation_context:
            sections.append(self.annotation_context)
        if self.author_context:
            sections.append(self.author_context)
        if self.quality is not None:
            sections.append(self.quality)
        sections.extend(self.extra_sections)
        return tuple(sections)
