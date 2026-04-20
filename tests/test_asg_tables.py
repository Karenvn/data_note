from __future__ import annotations

import unittest

from data_note.tables.asg import make_table1_rows, make_table5_rows, make_table6_rows


class AsgTableTests(unittest.TestCase):
    def test_make_table1_rows_includes_isoseq_column_when_present(self) -> None:
        table = make_table1_rows(
            {
                "species": "Example species",
                "bioproject": "PRJEB1",
                "tolid": "ixExample1",
                "hic_tolid": "ixExample1",
                "pacbio_specimen_id": "SP1",
                "hic_specimen_id": "SP1",
                "pacbio_sample_derived_from": "SAMEA0",
                "hic_sample_derived_from": "SAMEA0",
                "pacbio_sample_accession": "SAMEA1",
                "hic_sample_accession": "SAMEA2",
                "pacbio_organism_part": "whole organism",
                "hic_organism_part": "whole organism",
                "pacbio_instrument": "Sequel IIe",
                "hic_instrument": "NovaSeq",
                "pacbio_run_accessions": "ERR1",
                "hic_run_accessions": "ERR2",
                "pacbio_reads_millions": "10",
                "hic_reads_millions": "20",
                "pacbio_bases_gb": "30",
                "hic_bases_gb": "40",
                "isoseq_tolid": "ixExample1",
                "isoseq_specimen_id": "SP1",
                "isoseq_sample_derived_from": "SAMEA0",
                "isoseq_sample_accession": "SAMEA3",
                "isoseq_organism_part": "thorax",
                "isoseq_instrument": "Sequel IIe",
                "isoseq_run_accessions": "ERR3",
                "isoseq_reads_millions": "5",
                "isoseq_bases_gb": "6",
            }
        )

        self.assertIn("**Iso-Seq**", table["rows"][0])
        self.assertEqual(table["native_headers"][-1], "**Iso-Seq**")

    def test_make_table5_rows_is_omitted_without_metagenome(self) -> None:
        self.assertIsNone(make_table5_rows({"species": "Example species"}))

    def test_make_table5_rows_builds_from_metagenome_rows(self) -> None:
        table = make_table5_rows(
            {
                "species": "Example species",
                "has_metagenome": True,
                "metagenome_table_headers": [
                    "**Bin**",
                    "**Taxon**",
                    "**Completeness (%)**",
                ],
                "metagenome_table_rows": [
                    ["bin-01", "Gammaproteobacteria", "97.4"],
                    ["bin-02", "Bacteroidia", "91.0"],
                ],
            }
        )

        self.assertIsNotNone(table)
        assert table is not None
        self.assertEqual(table["label"], "tbl:table5")
        self.assertEqual(table["native_headers"][0], "**Bin**")
        self.assertEqual(table["native_rows"][0][0], "bin-01")

    def test_make_table6_rows_uses_software_table_numbering(self) -> None:
        table = make_table6_rows({"species": "Example species"})

        self.assertEqual(table["label"], "tbl:table6")
        self.assertEqual(table["native_headers"], ["**Software**", "**Version**", "**Source**"])


if __name__ == "__main__":
    unittest.main()
