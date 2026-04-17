from __future__ import annotations

import unittest

from data_note.table_rows import make_table3_rows


class TableRowsTests(unittest.TestCase):
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
