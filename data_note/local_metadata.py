from __future__ import annotations

from typing import Protocol


class LocalMetadataProvider(Protocol):
    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        ...


class NullLocalMetadataProvider:
    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        return None
