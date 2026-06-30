from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class LocalMetadataProvider(Protocol):
    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        ...

    def lookup_project_provenance(
        self,
        bioproject: str,
        *,
        tolid: str | None = None,
        species: str | None = None,
    ) -> Mapping[str, Any] | None:
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

    def lookup_project_provenance(
        self,
        bioproject: str,
        *,
        tolid: str | None = None,
        species: str | None = None,
    ) -> Mapping[str, Any] | None:
        return None
