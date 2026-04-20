from __future__ import annotations

import unittest

from data_note.table_rows import make_table2_rows, make_table3_rows


class TableRowsTests(unittest.TestCase):
    def test_make_table2_rows_includes_supernumerary_row_only_when_present(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Denticollis linearis",
            "assembly_name": "icDenLine1.1",
            "prim_accession": "GCA_123.1",
            "alt_accession": "GCA_124.1",
            "assembly_level": "chromosome",
            "total_length": "1000",
            "chromosome_count": "10",
            "num_contigs": "100",
            "contig_N50": "5",
            "num_scaffolds": "20",
            "scaffold_N50": "50",
            "sex_chromosomes": "X",
            "supernumerary_chromosomes": "B1 and B2",
            "organelle_data": {},
        }

        table = make_table2_rows(context)

        self.assertTrue(
            any(row[0] == "**Supernumerary chromosomes**" and row[1] == "B1 and B2" for row in table["native_rows"])
        )

    def test_make_table3_rows_uses_grouped_header_for_dual_chromosome_haplotypes(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "species": "Myotis emarginatus",
            "tolid": "mMyoEma1",
            "hap1_assembly_level": "chromosome",
            "hap2_assembly_level": "chromosome",
            "chromosome_data": [
                {
                    "hap1_INSDC": "OZ220647.2",
                    "hap1_molecule": "1",
                    "hap1_length": "228.73",
                    "hap1_GC": "41.50",
                    "hap2_INSDC": "OZ251378.1",
                    "hap2_molecule": "1",
                    "hap2_length": "229.98",
                    "hap2_GC": "41.50",
                }
            ],
        }

        table = make_table3_rows(context)

        self.assertEqual(table["native_headers"][:5], ["**Haplotype 1**", "", "", "", "**Haplotype 2**"])
        self.assertEqual(
            table["native_rows"][0],
            [
                "**INSDC accession**",
                "**Name**",
                "**Length (Mb)**",
                "**GC%**",
                "**INSDC accession**",
                "**Name**",
                "**Length (Mb)**",
                "**GC%**",
            ],
        )
        self.assertEqual(table["native_rows"][1][0], "OZ220647.2")
        self.assertEqual(table["native_rows"][1][4], "OZ251378.1")


if __name__ == "__main__":
    unittest.main()
