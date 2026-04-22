from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FlowCytometryInfo:
    flow_pg: float | None = None
    flow_mb: str = ""
    flow_buffer: str = ""
    buffer_desc: str = ""
    standard_desc: str = ""
    flow_project: str | None = None
    flow_dtol_specimen_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_context_dict(self) -> dict[str, Any]:
        context: dict[str, Any] = {
            "flow_pg": self.flow_pg,
            "flow_mb": self.flow_mb,
            "flow_buffer": self.flow_buffer,
            "buffer_desc": self.buffer_desc,
            "standard_desc": self.standard_desc,
        }
        if self.flow_project:
            context["flow_project"] = self.flow_project
        if self.flow_dtol_specimen_id:
            context["flow_dtol_specimen_id"] = self.flow_dtol_specimen_id
        context.update(self.extras)
        return context
