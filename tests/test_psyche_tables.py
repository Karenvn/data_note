from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from data_note.tables.psyche import make_table1_rows, make_table3_rows, make_table5_rows


class PsycheTableTests(unittest.TestCase):
    def test_make_table1_rows_includes_isoseq_column_when_present(self) -> None:
        context = {
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

        table = make_table1_rows(context)

        self.assertIn("**Iso-Seq**", table["rows"][0])
        self.assertEqual(table["alignment"], "LLLL")
        self.assertEqual(table["width"], [0.25, 0.25, 0.25, 0.25])
        self.assertEqual(table["native_headers"][-1], "**Iso-Seq**")

    def test_make_table3_rows_uses_hap1_only_and_merian_column_for_dual_haplotype_case(self) -> None:
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

        with patch("data_note.tables.psyche.merian_dict", return_value={"OZ220647.2": "M1;M19"}):
            table = make_table3_rows(context)

        self.assertIn("haplotype 2 also at chromosome level", table["caption"])
        self.assertEqual(table["native_headers"][-1], "**Assigned Merian elements**")
        self.assertEqual(len(table["native_rows"]), 1)
        self.assertEqual(table["native_rows"][0][0], "OZ220647.2")
        self.assertEqual(table["native_rows"][0][-1], "M1;M19")

    def test_make_table3_rows_matches_unversioned_merian_accessions(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Example species",
            "tolid": "ixExample1",
            "chromosome_data": [
                {"INSDC": "OZ220647.2", "molecule": "1", "length": "45.1", "GC": "39.8"},
            ],
        }

        with patch("data_note.tables.psyche.merian_dict", return_value={"OZ220647": "M1;M19"}):
            table = make_table3_rows(context)

        self.assertEqual(table["native_rows"][0][-1], "M1;M19")

    def test_make_table3_rows_derives_merian_assignments_from_busco_when_location_table_missing(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "species": "Caloptilia hemidactylella",
            "tolid": "ilCalHemi2",
            "hap1_assembly_level": "chromosome",
            "hap2_assembly_level": "chromosome",
            "chromosome_data": [
                {
                    "hap1_INSDC": "OZ253990.1",
                    "hap1_molecule": "1",
                    "hap1_length": "12.35",
                    "hap1_GC": "38.50",
                    "hap2_INSDC": "OZ253961.1",
                    "hap2_molecule": "1",
                    "hap2_length": "12.19",
                    "hap2_GC": "38.50",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            busco_dir = root / "busco" / "ilCalHemi2"
            busco_dir.mkdir(parents=True)
            (root / "Merian_elements_full_table.tsv").write_text(
                "\n".join(f"{i}at7088\tComplete\tM8\t0\t1" for i in range(5)) + "\n"
            )
            (busco_dir / "full_table.tsv").write_text(
                "# Busco id\tStatus\tSequence\tGene Start\tGene End\n"
                + "\n".join(
                    f"{i}at7088\tComplete\tOZ253990.1\t{100 + i}\t{200 + i}"
                    for i in range(5)
                )
                + "\n"
            )

            with patch("data_note.tables.psyche.GN_ASSETS_ROOT", root):
                table = make_table3_rows(context)

        self.assertEqual(table["native_rows"][0][-1], "M8")

    def test_make_table3_rows_uses_ncbi_chromosome_alias_when_merian_accessions_changed(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "species": "Erebia flavofasciata",
            "tolid": "ilEreFlav1",
            "hap1_assembly_level": "chromosome",
            "hap2_assembly_level": "scaffold",
            "hap1_chromosome_data": [
                {"INSDC": "OZ321319.1", "molecule": "1", "length": "43.03", "GC": "37.50"},
            ],
        }

        with (
            patch("data_note.tables.psyche.merian_dict", return_value={"OZ182127.1": "M12;M17;M20"}),
            patch("data_note.tables.psyche._ncbi_chromosome_aliases", return_value={"OZ182127.1": "1"}),
        ):
            table = make_table3_rows(context)

        self.assertEqual(table["native_rows"][0][-1], "M12;M17;M20")

    def test_make_table3_rows_excludes_primary_sex_chromosome_when_not_reported(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Example species",
            "tolid": "ixExample1",
            "sex_chromosomes": None,
            "chromosome_data": [
                {"INSDC": "OX000001.1", "molecule": "1", "length": "45.1", "GC": "39.8"},
                {"INSDC": "OX000099.1", "molecule": "X", "length": "12.3", "GC": "40.1"},
            ],
        }

        with patch("data_note.tables.psyche.merian_dict", return_value={}):
            table = make_table3_rows(context)

        self.assertEqual(len(table["native_rows"]), 1)
        self.assertEqual(table["native_rows"][0][1], "1")

    def test_make_table5_rows_includes_psyche_specific_software(self) -> None:
        table = make_table5_rows({"species": "Example species"})

        joined_rows = "\n".join(table["rows"])
        self.assertNotIn("BEDTools,2.30.0", joined_rows)
        self.assertNotIn("Cooler,0.8.11", joined_rows)
        self.assertIn("merian-busco-painter,v1.0.0", joined_rows)


if __name__ == "__main__":
    unittest.main()
