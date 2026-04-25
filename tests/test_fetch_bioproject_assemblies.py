from __future__ import annotations

import unittest
from unittest.mock import patch

from data_note.assembly_candidate_filter import AssemblyCandidateFilter
from data_note.assembly_mode_detector import AssemblyModeDetector
from data_note.assembly_pair_selector import AssemblyPairSelector
from data_note.assembly_selection_resolver import AssemblySelectionResolver
from data_note.bioproject_client import EnaPortalClient
from data_note.legacy_bioproject_assemblies import (
    extract_haplotype_assemblies as legacy_extract_haplotype_assemblies,
    extract_prim_alt_assemblies as legacy_extract_prim_alt_assemblies,
    fetch_and_update_assembly_details,
)
from data_note.models import AssemblyCandidate, AssemblySelectionInput
from data_note.fetch_ncbi_data import extract_linked_assemblies


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _MapperStub:
    def get_allowed_tax_ids(self, primary_tax_id):
        return {str(primary_tax_id), "alt-tax"}

    @staticmethod
    def should_exclude_by_name(assembly_name):
        return "wolbachia" in assembly_name.lower()


class EnaPortalClientTests(unittest.TestCase):
    def test_fetch_umbrella_project_prefers_exact_accession_match(self) -> None:
        def fake_get(url, params):
            self.assertEqual(url, "https://www.ebi.ac.uk/ena/portal/api/search")
            self.assertEqual(params["result"], "study")
            return _Response(
                200,
                [
                    {"study_accession": "PRJEB99999", "study_title": "Wrong"},
                    {"study_accession": "PRJEB12345", "study_title": "Exact"},
                ],
            )

        client = EnaPortalClient(session_get=fake_get)
        study = client.fetch_umbrella_project("PRJEB12345")

        self.assertEqual(study["study_accession"], "PRJEB12345")
        self.assertEqual(study["study_title"], "Exact")

    def test_fetch_child_accessions_filters_semicolon_delimited_parent_lists(self) -> None:
        def fake_get(url, params):
            self.assertEqual(params["query"], "parent_study_accession=PRJEB12345")
            return _Response(
                200,
                [
                    {"study_accession": "PRJEB_CHILD1", "parent_study_accession": "PRJEB12345"},
                    {"study_accession": "PRJEB_CHILD2", "parent_study_accession": "PRJEB_OTHER;PRJEB12345"},
                    {"study_accession": "PRJEB_CHILD3", "parent_study_accession": "PRJEB_OTHER"},
                ],
            )

        client = EnaPortalClient(session_get=fake_get)
        child_accessions = client.fetch_child_accessions({"study_accession": "PRJEB12345"})

        self.assertEqual(child_accessions, ["PRJEB_CHILD1", "PRJEB_CHILD2"])

    def test_fetch_and_update_assembly_details_updates_revision_and_name(self) -> None:
        def fake_get(url, params):
            self.assertEqual(params["result"], "assembly")
            return _Response(
                200,
                [
                    {
                        "assembly_set_accession": "GCA_000001.1",
                        "assembly_name": "ixExample1.1",
                        "tax_id": "1234",
                    }
                ],
            )

        client = EnaPortalClient(
            session_get=fake_get,
            revision_fetcher=lambda accession: ("GCA_000001.2", "ixExample1.2"),
        )
        assemblies = client.fetch_and_update_assembly_details("PRJEB12345")

        self.assertIsInstance(assemblies[0], AssemblyCandidate)
        self.assertEqual(assemblies[0].accession, "GCA_000001.2")
        self.assertEqual(assemblies[0].assembly_name, "ixExample1.2")

    def test_fetch_assembly_details_uses_accession_field_when_updating_revision(self) -> None:
        def fake_get(url, params):
            self.assertEqual(params["fields"], "accession,assembly_name,assembly_set_accession,tax_id")
            return _Response(
                200,
                [
                    {
                        "accession": "GCA_000010.1",
                        "assembly_set_accession": "GCA_000010.1",
                        "assembly_name": "ixExample2.1",
                        "tax_id": "1234",
                    }
                ],
            )

        client = EnaPortalClient(
            session_get=fake_get,
            revision_fetcher=lambda accession: ("GCA_000010.3", "ixExample2.3"),
        )
        assemblies = client.fetch_assembly_details("PRJEB12345")

        self.assertIsInstance(assemblies[0], AssemblyCandidate)
        self.assertEqual(assemblies[0].accession, "GCA_000010.3")
        self.assertEqual(assemblies[0].assembly_name, "ixExample2.1")

    def test_legacy_wrapper_returns_dicts_from_typed_client_results(self) -> None:
        candidate = AssemblyCandidate(
            accession="GCA_000001.2",
            assembly_name="ixExample1.2",
            tax_id="1234",
        )
        with patch("data_note.legacy_bioproject_assemblies._portal_client") as portal_client_factory:
            portal_client_factory.return_value.fetch_and_update_assembly_details.return_value = [candidate]

            assemblies = fetch_and_update_assembly_details("PRJEB12345")

        self.assertEqual(
            assemblies,
            [
                {
                    "assembly_set_accession": "GCA_000001.2",
                    "assembly_name": "ixExample1.2",
                    "tax_id": "1234",
                }
            ],
        )

    def test_legacy_extract_prim_alt_wrapper_returns_dicts_from_typed_selection(self) -> None:
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: {
                "GCA_PRIM_NEW.1": {
                    "assembly_level": "chromosome",
                    "scaffold_N50": 100.0,
                    "contig_N50": 8.0,
                },
                "GCA_ALT_NEW.1": {
                    "assembly_level": "chromosome",
                    "scaffold_N50": 90.0,
                    "contig_N50": 7.0,
                },
            }.get(accession, {}),
        )
        assembly_dicts = [
            {
                "assembly_name": "ixExample2.1 alternate haplotype",
                "assembly_set_accession": "GCA_ALT_NEW.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample2.1",
                "assembly_set_accession": "GCA_PRIM_NEW.1",
                "tax_id": "1234",
            },
        ]

        with patch("data_note.legacy_bioproject_assemblies._selection_resolver", return_value=resolver):
            primary, alternate = legacy_extract_prim_alt_assemblies(assembly_dicts, "1234")

        self.assertEqual(primary["prim_accession"], "GCA_PRIM_NEW.1")
        self.assertEqual(alternate["alt_accession"], "GCA_ALT_NEW.1")

    def test_legacy_extract_haplotype_wrapper_returns_dicts_from_typed_selection(self) -> None:
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: {
                "GCA_H1_NEW.1": {
                    "assembly_level": "chromosome",
                    "scaffold_N50": 120.0,
                    "contig_N50": 9.0,
                },
                "GCA_H2_NEW.1": {
                    "assembly_level": "chromosome",
                    "scaffold_N50": 110.0,
                    "contig_N50": 8.0,
                },
            }.get(accession, {}),
        )
        assembly_dicts = [
            {"assembly_name": "ixExample2.hap1.1", "assembly_set_accession": "GCA_H1_NEW.1", "tax_id": "1234"},
            {"assembly_name": "ixExample2.hap2.1", "assembly_set_accession": "GCA_H2_NEW.1", "tax_id": "1234"},
        ]

        with patch("data_note.legacy_bioproject_assemblies._selection_resolver", return_value=resolver):
            hap1, hap2 = legacy_extract_haplotype_assemblies(assembly_dicts, "1234")

        self.assertEqual(hap1["hap1_accession"], "GCA_H1_NEW.1")
        self.assertEqual(hap2["hap2_accession"], "GCA_H2_NEW.1")


class AssemblySelectionResolverTests(unittest.TestCase):
    def test_determine_assembly_type_uses_haplotype_name_heuristic(self) -> None:
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: {},
        )
        assembly_dicts = [
            {"assembly_name": "ixExample1.hap1.1", "assembly_set_accession": "GCA_1.1", "tax_id": "1234"},
            {"assembly_name": "ixExample1.hap2.1", "assembly_set_accession": "GCA_1.2", "tax_id": "1234"},
        ]

        self.assertEqual(resolver.determine_assembly_type(assembly_dicts, "1234"), "hap_asm")

    def test_build_selection_prefers_highest_contiguity_primary_after_tax_filter(self) -> None:
        metrics = {
            "GCA_ALT_OLD.1": {"assembly_level": "chromosome", "scaffold_N50": 60.0, "contig_N50": 5.0},
            "GCA_ALT_NEW.1": {"assembly_level": "chromosome", "scaffold_N50": 90.0, "contig_N50": 7.0},
            "GCA_PRIM_OLD.1": {"assembly_level": "chromosome", "scaffold_N50": 70.0, "contig_N50": 6.0},
            "GCA_PRIM_NEW.1": {"assembly_level": "chromosome", "scaffold_N50": 100.0, "contig_N50": 8.0},
            "GCA_PRIM_WRONG.1": {"assembly_level": "complete genome", "scaffold_N50": 999.0, "contig_N50": 999.0},
        }
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: metrics.get(accession, {}),
        )
        assembly_dicts = [
            {
                "assembly_name": "ixExample1.1 alternate haplotype",
                "assembly_set_accession": "GCA_ALT_OLD.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample1.1",
                "assembly_set_accession": "GCA_PRIM_OLD.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample2.1 alternate haplotype",
                "assembly_set_accession": "GCA_ALT_NEW.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample2.1",
                "assembly_set_accession": "GCA_PRIM_NEW.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixWrongTax.1",
                "assembly_set_accession": "GCA_PRIM_WRONG.1",
                "tax_id": "wrong-tax",
            },
        ]

        selection = resolver.build_selection(assembly_dicts, "1234")

        self.assertEqual(selection.primary.accession, "GCA_PRIM_NEW.1")
        self.assertEqual(selection.alternate.accession, "GCA_ALT_NEW.1")

    def test_build_selection_prefers_highest_contiguity_hap1_and_matching_hap2(self) -> None:
        metrics = {
            "GCA_H1_OLD.1": {"assembly_level": "chromosome", "scaffold_N50": 80.0, "contig_N50": 5.0},
            "GCA_H2_OLD.1": {"assembly_level": "chromosome", "scaffold_N50": 75.0, "contig_N50": 4.0},
            "GCA_H1_NEW.1": {"assembly_level": "chromosome", "scaffold_N50": 120.0, "contig_N50": 9.0},
            "GCA_H2_NEW.1": {"assembly_level": "chromosome", "scaffold_N50": 110.0, "contig_N50": 8.0},
            "GCA_WRONG.1": {"assembly_level": "complete genome", "scaffold_N50": 999.0, "contig_N50": 999.0},
        }
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: metrics.get(accession, {}),
        )
        assembly_dicts = [
            {"assembly_name": "ixExample1.hap1.1", "assembly_set_accession": "GCA_H1_OLD.1", "tax_id": "1234"},
            {"assembly_name": "ixExample1.hap2.1", "assembly_set_accession": "GCA_H2_OLD.1", "tax_id": "1234"},
            {"assembly_name": "ixExample2.hap1.1", "assembly_set_accession": "GCA_H1_NEW.1", "tax_id": "1234"},
            {"assembly_name": "ixExample2.hap2.1", "assembly_set_accession": "GCA_H2_NEW.1", "tax_id": "1234"},
            {"assembly_name": "ixWrongTax.hap1.1", "assembly_set_accession": "GCA_WRONG.1", "tax_id": "wrong-tax"},
        ]

        selection = resolver.build_selection(assembly_dicts, "1234")

        self.assertEqual(selection.hap1.accession, "GCA_H1_NEW.1")
        self.assertEqual(selection.hap2.accession, "GCA_H2_NEW.1")

    def test_build_selection_prefers_ncbi_linked_alternate_when_available(self) -> None:
        metrics = {
            "GCA_PRIM_BEST.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 100.0,
                "contig_N50": 10.0,
                "linked_assemblies": ["GCA_ALT_LINKED.1"],
            },
            "GCA_ALT_LINKED.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 80.0,
                "contig_N50": 7.0,
                "linked_assemblies": ["GCA_PRIM_BEST.1"],
            },
            "GCA_ALT_NAME_MATCH.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 95.0,
                "contig_N50": 9.0,
                "linked_assemblies": [],
            },
        }
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: metrics.get(accession, {}),
        )
        assembly_dicts = [
            {"assembly_name": "ixExample2.1", "assembly_set_accession": "GCA_PRIM_BEST.1", "tax_id": "1234"},
            {
                "assembly_name": "ixExample2.1 alternate haplotype",
                "assembly_set_accession": "GCA_ALT_NAME_MATCH.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "odd assembly alternate haplotype",
                "assembly_set_accession": "GCA_ALT_LINKED.1",
                "tax_id": "1234",
            },
        ]

        selection = resolver.build_selection(assembly_dicts, "1234")

        self.assertEqual(selection.primary.accession, "GCA_PRIM_BEST.1")
        self.assertEqual(selection.alternate.accession, "GCA_ALT_LINKED.1")

    def test_build_selection_prefers_ncbi_linked_hap2_when_available(self) -> None:
        metrics = {
            "GCA_H1_BEST.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 120.0,
                "contig_N50": 10.0,
                "linked_assemblies": ["GCA_H2_LINKED.1"],
            },
            "GCA_H2_LINKED.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 100.0,
                "contig_N50": 8.0,
                "linked_assemblies": ["GCA_H1_BEST.1"],
            },
            "GCA_H2_NAME_MATCH.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 110.0,
                "contig_N50": 9.0,
                "linked_assemblies": [],
            },
        }
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: metrics.get(accession, {}),
        )
        assembly_dicts = [
            {"assembly_name": "ixExample2.hap1.1", "assembly_set_accession": "GCA_H1_BEST.1", "tax_id": "1234"},
            {"assembly_name": "ixExample2.hap2.1", "assembly_set_accession": "GCA_H2_NAME_MATCH.1", "tax_id": "1234"},
            {"assembly_name": "odd_pair.hap2.1", "assembly_set_accession": "GCA_H2_LINKED.1", "tax_id": "1234"},
        ]

        selection = resolver.build_selection(assembly_dicts, "1234")

        self.assertEqual(selection.hap1.accession, "GCA_H1_BEST.1")
        self.assertEqual(selection.hap2.accession, "GCA_H2_LINKED.1")

    def test_filter_relevant_assemblies_applies_tax_id_and_name_filters(self) -> None:
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: {},
        )
        assembly_dicts = [
            {"assembly_name": "ixExample1.1", "assembly_set_accession": "GCA_KEEP.1", "tax_id": "1234"},
            {"assembly_name": "Wolbachia assembly", "assembly_set_accession": "GCA_DROP.1", "tax_id": "1234"},
            {"assembly_name": "ixExample1.alt", "assembly_set_accession": "GCA_OTHER.1", "tax_id": "wrong-tax"},
        ]

        relevant = resolver.filter_relevant_assemblies(assembly_dicts, "1234")

        self.assertEqual(len(relevant), 1)
        self.assertEqual(relevant[0].accession, "GCA_KEEP.1")
        self.assertEqual(relevant[0].assembly_name, "ixExample1.1")

    def test_build_selection_honours_requested_primary_assembly_input(self) -> None:
        metrics = {
            "GCA_ALT_OLD.1": {"assembly_level": "chromosome", "scaffold_N50": 60.0, "contig_N50": 5.0},
            "GCA_ALT_NEW.1": {"assembly_level": "chromosome", "scaffold_N50": 90.0, "contig_N50": 7.0},
            "GCA_PRIM_OLD.1": {"assembly_level": "chromosome", "scaffold_N50": 70.0, "contig_N50": 6.0},
            "GCA_PRIM_NEW.1": {"assembly_level": "chromosome", "scaffold_N50": 100.0, "contig_N50": 8.0},
        }
        resolver = AssemblySelectionResolver(
            taxonomy_mapper_module=_MapperStub(),
            contiguity_fetcher=lambda accession: metrics.get(accession, {}),
        )
        assembly_dicts = [
            {
                "assembly_name": "ixExample1.1 alternate haplotype",
                "assembly_set_accession": "GCA_ALT_OLD.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample1.1",
                "assembly_set_accession": "GCA_PRIM_OLD.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample2.1 alternate haplotype",
                "assembly_set_accession": "GCA_ALT_NEW.1",
                "tax_id": "1234",
            },
            {
                "assembly_name": "ixExample2.1",
                "assembly_set_accession": "GCA_PRIM_NEW.1",
                "tax_id": "1234",
            },
        ]

        selection = resolver.build_selection(
            assembly_dicts,
            "1234",
            selection_input=AssemblySelectionInput(assembly_accession="GCA_PRIM_OLD.1"),
        )

        self.assertEqual(selection.primary.accession, "GCA_PRIM_OLD.1")
        self.assertEqual(selection.alternate.accession, "GCA_ALT_OLD.1")


class AssemblyModeDetectorTests(unittest.TestCase):
    def test_detect_returns_haplotype_mode_when_labels_present(self) -> None:
        detector = AssemblyModeDetector()
        candidates = [
            AssemblyCandidate(accession="GCA_1.1", assembly_name="ixExample1.hap1.1"),
            AssemblyCandidate(accession="GCA_1.2", assembly_name="ixExample1.hap2.1"),
        ]

        self.assertEqual(detector.detect(candidates), "hap_asm")


class AssemblyCandidateFilterTests(unittest.TestCase):
    def test_filter_relevant_assemblies_coerces_mappings_and_filters_by_tax_id_and_name(self) -> None:
        candidate_filter = AssemblyCandidateFilter(taxonomy_mapper_module=_MapperStub())
        assembly_dicts = [
            {"assembly_name": "ixExample1.1", "assembly_set_accession": "GCA_KEEP.1", "tax_id": "1234"},
            AssemblyCandidate(accession="GCA_KEEP_TOO.1", assembly_name="ixExample2.1", tax_id="alt-tax"),
            {"assembly_name": "Wolbachia assembly", "assembly_set_accession": "GCA_DROP.1", "tax_id": "1234"},
            {"assembly_name": "ixExample1.alt", "assembly_set_accession": "GCA_OTHER.1", "tax_id": "wrong-tax"},
        ]

        relevant = candidate_filter.filter_relevant_assemblies(assembly_dicts, "1234")

        self.assertEqual([assembly.accession for assembly in relevant], ["GCA_KEEP.1", "GCA_KEEP_TOO.1"])


class AssemblyPairSelectorTests(unittest.TestCase):
    def test_select_prim_alt_records_prefers_linked_alternate_over_name_match(self) -> None:
        metrics = {
            "GCA_PRIM_BEST.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 100.0,
                "contig_N50": 10.0,
                "linked_assemblies": ["GCA_ALT_LINKED.1"],
            },
            "GCA_ALT_LINKED.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 80.0,
                "contig_N50": 7.0,
                "linked_assemblies": ["GCA_PRIM_BEST.1"],
            },
            "GCA_ALT_NAME_MATCH.1": {
                "assembly_level": "chromosome",
                "scaffold_N50": 95.0,
                "contig_N50": 9.0,
                "linked_assemblies": [],
            },
        }
        selector = AssemblyPairSelector(contiguity_fetcher=lambda accession: metrics.get(accession, {}))
        candidates = [
            AssemblyCandidate(accession="GCA_PRIM_BEST.1", assembly_name="ixExample2.1", tax_id="1234"),
            AssemblyCandidate(
                accession="GCA_ALT_NAME_MATCH.1",
                assembly_name="ixExample2.1 alternate haplotype",
                tax_id="1234",
            ),
            AssemblyCandidate(
                accession="GCA_ALT_LINKED.1",
                assembly_name="odd assembly alternate haplotype",
                tax_id="1234",
            ),
        ]

        primary, alternate = selector.select_prim_alt_records(candidates)

        self.assertEqual(primary.accession, "GCA_PRIM_BEST.1")
        self.assertEqual(alternate.accession, "GCA_ALT_LINKED.1")


class NcbiAssemblyParsingTests(unittest.TestCase):
    def test_extract_linked_assemblies_returns_accession_list(self) -> None:
        report = {
            "assembly_info": {
                "linked_assemblies": [
                    {"linked_assembly": "GCA_111111111.1"},
                    {"linked_assembly": "GCA_222222222.1"},
                    {"something_else": "ignored"},
                ]
            }
        }

        self.assertEqual(
            extract_linked_assemblies(report),
            ["GCA_111111111.1", "GCA_222222222.1"],
        )


if __name__ == "__main__":
    unittest.main()
