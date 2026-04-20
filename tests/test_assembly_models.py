from __future__ import annotations

import unittest

from data_note.models import (
    AssemblyBundle,
    AssemblyCoverageInput,
    AssemblyDatasetRecord,
    AssemblyDatasetsInfo,
    AssemblyRecord,
    AssemblySelection,
    BtkAssemblyRecord,
    BtkSummary,
    ChromosomeSummary,
)


class AssemblyModelTests(unittest.TestCase):
    def test_primary_alternate_to_context_dict(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
            alternate=AssemblyRecord(accession="GCA_2.1", assembly_name="ixFooBar1.1 alternate haplotype", role="alternate"),
        )

        self.assertEqual(
            selection.to_context_dict(),
            {
                "assemblies_type": "prim_alt",
                "prim_accession": "GCA_1.1",
                "prim_assembly_name": "ixFooBar1.1",
                "alt_accession": "GCA_2.1",
                "alt_assembly_name": "ixFooBar1.1 alternate haplotype",
            },
        )

    def test_haplotype_to_context_dict(self) -> None:
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_3.1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_4.1", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        self.assertEqual(selection.assembly_accessions()["hap1_accession"], "GCA_3.1")
        self.assertEqual(selection.assembly_accessions()["hap2_accession"], "GCA_4.1")

    def test_preferred_helpers_follow_primary_or_hap1(self) -> None:
        primary_selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )
        hap_selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_3.1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_4.1", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        self.assertEqual(primary_selection.preferred_accession(), "GCA_1.1")
        self.assertEqual(primary_selection.preferred_assembly_name(), "ixFooBar1.1")
        self.assertEqual(hap_selection.preferred_accession(), "GCA_3.1")
        self.assertEqual(hap_selection.preferred_assembly_name(), "ixFooBar1.hap1.1")

    def test_validation_rejects_missing_accession(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="", assembly_name="ixFooBar1.1", role="primary"),
        )
        with self.assertRaises(ValueError):
            selection.validate()

    def test_coverage_input_from_primary_selection_and_context(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )

        coverage = AssemblyCoverageInput.from_selection_and_context(
            selection,
            {"genome_length_unrounded": "123456789"},
        )

        self.assertEqual(coverage.primary_accession, "GCA_1.1")
        self.assertEqual(coverage.genome_length_unrounded, 123456789.0)

    def test_coverage_input_from_haplotype_selection_and_context(self) -> None:
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_h1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_h2", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        coverage = AssemblyCoverageInput.from_selection_and_context(
            selection,
            {
                "hap1_genome_length_unrounded": "111",
                "hap2_genome_length_unrounded": "222",
            },
        )

        self.assertEqual(coverage.hap1_accession, "GCA_h1")
        self.assertEqual(coverage.hap2_accession, "GCA_h2")
        self.assertEqual(coverage.hap1_genome_length_unrounded, 111.0)
        self.assertEqual(coverage.hap2_genome_length_unrounded, 222.0)

    def test_assembly_bundle_flattens_all_assembly_components(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )
        bundle = AssemblyBundle(
            selection=selection,
            datasets=AssemblyDatasetsInfo(
                assemblies_type="prim_alt",
                primary=AssemblyDatasetRecord(assembly_level="chromosome", total_length="100"),
            ),
            chromosomes=ChromosomeSummary(sex_chromosomes="X", supernumerary_chromosomes="B1"),
            btk=BtkSummary(
                assemblies_type="prim_alt",
                primary=BtkAssemblyRecord(summary_fields={"BUSCO_string": "C:99.0%"}),
                shared_fields={"blobtoolkit_version": "2.0"},
            ),
            coverage_fields={"percent_chr": 98.5},
        )

        context = bundle.to_context_dict()

        self.assertEqual(context["prim_accession"], "GCA_1.1")
        self.assertEqual(context["assembly_level"], "chromosome")
        self.assertEqual(context["sex_chromosomes"], "X")
        self.assertEqual(context["supernumerary_chromosomes"], "B1")
        self.assertEqual(context["BUSCO_string"], "C:99.0%")
        self.assertEqual(context["blobtoolkit_version"], "2.0")
        self.assertEqual(context["percent_chr"], 98.5)


if __name__ == "__main__":
    unittest.main()
