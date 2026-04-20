from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..fetch_jira_info import fetch_and_parse_jira_data
from ..local_metadata_provider import get_local_metadata_provider
from ..models import AssemblySelection, CurationInfo


@dataclass(slots=True)
class LocalMetadataService:
    provider_factory: Callable[[], Any] = get_local_metadata_provider
    jira_data_fetcher: Callable[[str], dict[str, Any]] = fetch_and_parse_jira_data

    def build_context(
        self,
        assembly_selection: AssemblySelection,
        tolid: str | None = None,
        *,
        species: str | None = None,
    ) -> CurationInfo:
        local_data_context = CurationInfo()

        accession, assembly_name = self._resolve_lookup_values(assembly_selection)
        if not accession:
            print("Error: No valid accession found for ToLA lookup.")
            return local_data_context

        provider = self.provider_factory()
        jira_ticket = provider.lookup_jira_ticket(
            accession,
            tolid=tolid,
            assembly_name=assembly_name,
        )

        if not jira_ticket:
            print(f"No Jira ticket found for {accession}; skipping local metadata enrichment.")
            return local_data_context

        print(f"Fetching Jira data for ticket: {jira_ticket}")
        local_data_context.jira_ticket = jira_ticket

        jira_dict = self.jira_data_fetcher(jira_ticket) or {}
        if jira_dict:
            local_data_context.jira_fields.update(jira_dict)
        else:
            print(f"Warning: No Jira data found for ticket {jira_ticket}.")

        return local_data_context

    @staticmethod
    def _resolve_lookup_values(
        assembly_selection: AssemblySelection,
    ) -> tuple[str | None, str | None]:
        return (
            assembly_selection.preferred_accession(),
            assembly_selection.preferred_assembly_name(),
        )
