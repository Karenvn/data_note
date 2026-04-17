from __future__ import annotations

import unittest

from data_note.models import AssemblyRecord, AssemblySelection


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

    def test_validation_rejects_missing_accession(self) -> None:
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="", assembly_name="ixFooBar1.1", role="primary"),
        )
        with self.assertRaises(ValueError):
            selection.validate()


if __name__ == "__main__":
    unittest.main()
