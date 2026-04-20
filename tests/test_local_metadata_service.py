from __future__ import annotations

import unittest

from data_note.models import AssemblyRecord, AssemblySelection, CurationInfo
from data_note.services.local_metadata_service import LocalMetadataService


class _Provider:
    def __init__(self, jira_ticket: str | None) -> None:
        self.jira_ticket = jira_ticket
        self.calls: list[tuple[str | None, str | None, str | None]] = []

    def lookup_jira_ticket(
        self,
        accession: str | None,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        self.calls.append((accession, tolid, assembly_name))
        return self.jira_ticket


class LocalMetadataServiceTests(unittest.TestCase):
    def test_build_context_uses_primary_record_from_selection(self) -> None:
        provider = _Provider("GRIT-1000")
        service = LocalMetadataService(
            provider_factory=lambda: provider,
            jira_data_fetcher=lambda ticket: {"jira_summary": ticket},
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )

        curation = service.build_context(selection, tolid="ixFooBar1")
        context = curation.to_context_dict()

        self.assertIsInstance(curation, CurationInfo)
        self.assertEqual(provider.calls, [("GCA_1.1", "ixFooBar1", "ixFooBar1.1")])
        self.assertEqual(context["jira"], "GRIT-1000")
        self.assertEqual(context["jira_summary"], "GRIT-1000")

    def test_build_context_uses_hap1_record_from_selection(self) -> None:
        provider = _Provider("RC-2000")
        service = LocalMetadataService(
            provider_factory=lambda: provider,
            jira_data_fetcher=lambda ticket: {"jira_summary": ticket},
        )
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_h1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_h2", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        curation = service.build_context(selection, tolid="ixFooBar1")
        context = curation.to_context_dict()

        self.assertIsInstance(curation, CurationInfo)
        self.assertEqual(provider.calls, [("GCA_h1", "ixFooBar1", "ixFooBar1.hap1.1")])
        self.assertEqual(context["jira"], "RC-2000")
        self.assertEqual(context["jira_summary"], "RC-2000")

    def test_build_context_returns_empty_when_no_ticket_found(self) -> None:
        provider = _Provider(None)
        service = LocalMetadataService(
            provider_factory=lambda: provider,
            jira_data_fetcher=lambda ticket: {"jira_summary": ticket},
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )

        curation = service.build_context(selection, tolid="ixFooBar1")
        context = curation.to_context_dict()

        self.assertEqual(context, {})


if __name__ == "__main__":
    unittest.main()
