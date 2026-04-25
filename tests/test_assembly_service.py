from __future__ import annotations

import unittest

from data_note.assembly_override_resolver import AssemblyOverrideResolver
from data_note.models import AssemblyCandidate, AssemblyRecord, AssemblySelection, AssemblySelectionInput
from data_note.services.assembly_service import AssemblyService


class _BioprojectClientStub:
    def __init__(self) -> None:
        self.child_calls = []
        self.assembly_calls = []

    def fetch_child_accessions(self, umbrella_data):
        self.child_calls.append(umbrella_data)
        return ["PRJEB_CHILD1", "PRJEB_CHILD2"]

    def fetch_assemblies_for_bioprojects(self, bioproject_ids):
        self.assembly_calls.append(list(bioproject_ids))
        return [
            AssemblyCandidate(accession="GCA_1.1", assembly_name="ixExample1.1", tax_id="9606"),
            AssemblyCandidate(
                accession="GCA_1.2",
                assembly_name="ixExample1.1 alternate haplotype",
                tax_id="9606",
            ),
        ]


class _SelectionResolverStub:
    def __init__(self) -> None:
        self.taxonomy_mapper_module = None
        self.calls = []

    def build_selection(self, assembly_dicts, tax_id, selection_input=None):
        self.calls.append((assembly_dicts, tax_id, selection_input))
        return AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
            alternate=AssemblyRecord(
                accession="GCA_1.2",
                assembly_name="ixExample1.1 alternate haplotype",
                role="alternate",
            ),
        )


class _MapperStub:
    @staticmethod
    def has_assembly_override(bioproject_id):
        return bioproject_id in {"PRJEB_OVERRIDE", "PRJEB_HAP_OVERRIDE"}

    @staticmethod
    def get_assembly_override(bioproject_id):
        if bioproject_id == "PRJEB_OVERRIDE":
            return {
                "primary": {"accession": "GCA_OVERRIDE.1", "name": "ixOverride1.1"},
                "alternate": {"accession": "GCA_OVERRIDE.2", "name": "ixOverride1.1 alternate haplotype"},
                "reason": "manual override",
            }
        if bioproject_id == "PRJEB_HAP_OVERRIDE":
            return {
                "hap1": {"accession": "GCA_HAP_OVERRIDE.1", "name": "ixOverride1.hap1.1"},
                "hap2": {"accession": "GCA_HAP_OVERRIDE.2", "name": "ixOverride1.hap2.1"},
                "reason": "manual haplotype override",
            }
        return {}


class AssemblyOverrideResolverTests(unittest.TestCase):
    def test_build_selection_supports_haplotype_overrides(self) -> None:
        resolver = AssemblyOverrideResolver(taxonomy_mapper_module=_MapperStub())

        selection = resolver.build_selection("PRJEB_HAP_OVERRIDE")

        self.assertEqual(selection.assemblies_type, "hap_asm")
        self.assertEqual(selection.hap1.accession, "GCA_HAP_OVERRIDE.1")
        self.assertEqual(selection.hap2.accession, "GCA_HAP_OVERRIDE.2")

    def test_resolve_uses_runtime_selection_input_when_present(self) -> None:
        resolver = AssemblyOverrideResolver(
            taxonomy_mapper_module=_MapperStub(),
            selection_input=AssemblySelectionInput(assembly_accession="GCA_1.1"),
        )
        selection_resolver = _SelectionResolverStub()
        assembly_candidates = _BioprojectClientStub().fetch_assemblies_for_bioprojects(["PRJEB_CHILD1"])

        selection = resolver.resolve(
            bioproject_id="PRJEB_OVERRIDE",
            assembly_candidates=assembly_candidates,
            tax_id="9606",
            selection_resolver=selection_resolver,
        )

        self.assertEqual(selection.primary.accession, "GCA_1.1")
        self.assertEqual(selection_resolver.calls[0][2].assembly_accession, "GCA_1.1")


class AssemblyServiceTests(unittest.TestCase):
    def test_build_context_uses_bioproject_client_and_selection_resolver_objects(self) -> None:
        bioproject_client = _BioprojectClientStub()
        selection_resolver = _SelectionResolverStub()
        mapper = _MapperStub()
        service = AssemblyService(
            bioproject_client=bioproject_client,
            selection_resolver=selection_resolver,
            taxonomy_mapper_module=mapper,
        )

        selection = service.build_context({"study_accession": "PRJEB1"}, "9606")

        self.assertEqual(bioproject_client.child_calls, [{"study_accession": "PRJEB1"}])
        self.assertEqual(bioproject_client.assembly_calls, [["PRJEB_CHILD1", "PRJEB_CHILD2"]])
        self.assertEqual(len(selection_resolver.calls), 1)
        self.assertEqual(selection_resolver.calls[0][1], "9606")
        self.assertIsInstance(selection_resolver.calls[0][0][0], AssemblyCandidate)
        self.assertIsNone(selection_resolver.calls[0][2])
        self.assertIsNotNone(selection.primary)
        self.assertEqual(selection.primary.accession, "GCA_1.1")
        self.assertIs(selection_resolver.taxonomy_mapper_module, mapper)

    def test_build_context_respects_manual_override_before_client_fetch(self) -> None:
        bioproject_client = _BioprojectClientStub()
        selection_resolver = _SelectionResolverStub()
        mapper = _MapperStub()
        service = AssemblyService(
            bioproject_client=bioproject_client,
            selection_resolver=selection_resolver,
            taxonomy_mapper_module=mapper,
        )

        selection = service.build_context({"study_accession": "PRJEB_OVERRIDE"}, "9606")

        self.assertEqual(bioproject_client.child_calls, [])
        self.assertEqual(selection_resolver.calls, [])
        self.assertEqual(selection.primary.accession, "GCA_OVERRIDE.1")
        self.assertEqual(selection.alternate.accession, "GCA_OVERRIDE.2")

    def test_build_context_passes_runtime_selection_input_to_resolver(self) -> None:
        bioproject_client = _BioprojectClientStub()
        selection_resolver = _SelectionResolverStub()
        mapper = _MapperStub()
        service = AssemblyService(
            bioproject_client=bioproject_client,
            selection_resolver=selection_resolver,
            taxonomy_mapper_module=mapper,
            selection_input=AssemblySelectionInput(assembly_accession="GCA_1.1"),
        )

        selection = service.build_context({"study_accession": "PRJEB1"}, "9606")

        self.assertEqual(selection.primary.accession, "GCA_1.1")
        self.assertEqual(selection_resolver.calls[0][2].assembly_accession, "GCA_1.1")


if __name__ == "__main__":
    unittest.main()
