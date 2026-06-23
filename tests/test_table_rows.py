from __future__ import annotations

import unittest

from data_note.table_rows import (
    flatten_cell,
    make_table1_rows,
    make_table2_rows,
    make_table3_rows,
    make_table4_rows,
    make_table5_rows,
)


class TableRowsTests(unittest.TestCase):
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

    def test_make_table1_rows_flags_read_pair_units_when_present(self) -> None:
        context = {
            "species": "Example species",
            "bioproject": "PRJEB1",
            "tolid": "ixExample1",
            "hic_tolid": "ixExample1",
            "pacbio_reads_millions": "10",
            "pacbio_read_count_unit": "reads",
            "hic_reads_millions": "20",
            "hic_read_count_unit": "read pairs",
            "pacbio_bases_gb": "30",
            "hic_bases_gb": "40",
        }

        table = make_table1_rows(context)

        read_count_row = next(row for row in table["native_rows"] if row[0] == "**Read count total**")
        self.assertEqual(read_count_row[1], "10 million reads")
        self.assertEqual(read_count_row[2], "20 million read pairs")

    def test_make_table1_rows_includes_chromium_column_when_present(self) -> None:
        context = {
            "species": "Filipendula ulmaria",
            "bioproject": "PRJEB46853",
            "tolid": "drFilUlma1",
            "hic_tolid": "drFilUlma1",
            "chromium_tolid": "drFilUlma1",
            "pacbio_sample_accession": "SAMEA7522118",
            "hic_sample_accession": "SAMEA7522118",
            "chromium_sample_accession": "SAMEA7522118",
            "pacbio_instrument": "Sequel II",
            "hic_instrument": "Illumina NovaSeq 6000",
            "chromium_instrument": "Illumina NovaSeq 6000",
            "pacbio_run_accessions": "ERR6939255; ERR6939256",
            "hic_run_accessions": "ERR6688645",
            "chromium_run_accessions": "ERR6688646; ERR6688647; ERR6688648; ERR6688649",
            "pacbio_reads_millions": "1.04",
            "hic_reads_millions": "353.21",
            "chromium_reads_millions": "267.52",
            "hic_read_count_unit": "read pairs",
            "chromium_read_count_unit": "read pairs",
            "pacbio_bases_gb": "14.46",
            "hic_bases_gb": "106.67",
            "chromium_bases_gb": "80.79",
        }

        table = make_table1_rows(context)

        self.assertIn("**10X Chromium**", table["native_headers"])
        self.assertEqual(table["alignment"], "LLLL")
        self.assertEqual(table["width"], [0.25, 0.25, 0.25, 0.25])
        read_count_row = next(row for row in table["native_rows"] if row[0] == "**Read count total**")
        self.assertEqual(read_count_row[3], "267.52 million read pairs")
        run_row = next(row for row in table["native_rows"] if row[0] == "**Run accessions**")
        self.assertEqual(run_row[3], "ERR6688646; ERR6688647; ERR6688648; ERR6688649")

    def test_flatten_cell_unbolds_plain_somatic_tissue_terms(self) -> None:
        self.assertEqual(flatten_cell("**other somatic animal tissue**"), "other somatic animal tissue")
        self.assertEqual(flatten_cell("other somatic **body** tissue"), "other somatic body tissue")
        self.assertEqual(flatten_cell("<strong>other somatic animal tissue</strong>"), "other somatic animal tissue")

    def test_make_table1_rows_unbolds_somatic_tissue_terms(self) -> None:
        context = {
            "species": "Tytthaspis sedecimpunctata",
            "bioproject": "PRJEB73900",
            "tolid": "icTytSede3",
            "hic_tolid": "icTytSede6",
            "rna_tolid": "icTytSede4",
            "pacbio_organism_part": "whole organism",
            "hic_organism_part": "whole organism",
            "rna_sample_accession": "SAMEA11025073",
            "rna_organism_part": "**other somatic animal tissue**",
            "pacbio_reads_millions": "2.19",
            "hic_reads_millions": "952.49",
            "rna_reads_millions": "84.29",
            "pacbio_bases_gb": "24.66",
            "hic_bases_gb": "287.65",
            "rna_bases_gb": "25.45",
        }

        table = make_table1_rows(context)

        tissue_row = next(row for row in table["native_rows"] if row[0] == "**Tissue**")
        self.assertEqual(tissue_row[-1], "other somatic animal tissue")

    def test_make_table5_rows_includes_legacy_10x_software_versions(self) -> None:
        table = make_table5_rows(
            {
                "species": "Filipendula ulmaria",
                "hifiasm_version": "0.14-r312",
                "purge_dups_version": "1.2.3",
                "longranger_version": "2.2.2",
                "freebayes_version": "v1.3.1-17-gaa2ace8",
                "salsa_version": "v2.2",
            }
        )

        versions = {row[0]: row[1] for row in table["native_rows"]}

        self.assertEqual(versions["Hifiasm"], "0.14-r312")
        self.assertEqual(versions["purge_dups"], "1.2.3")
        self.assertEqual(versions["Long Ranger"], "2.2.2")
        self.assertEqual(versions["freebayes"], "v1.3.1-17-gaa2ace8")
        self.assertEqual(versions["SALSA2"], "v2.2")

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

    def test_make_table2_rows_excludes_sex_chromosomes_row_when_absent_for_primary(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Example species",
            "assembly_name": "exSpec1.1",
            "prim_accession": "GCA_123.1",
            "alt_accession": "GCA_124.1",
            "assembly_level": "chromosome",
            "total_length": "1000",
            "chromosome_count": "10",
            "num_contigs": "100",
            "contig_N50": "5",
            "num_scaffolds": "20",
            "scaffold_N50": "50",
            "sex_chromosomes": "",
        }

        table = make_table2_rows(context)

        self.assertFalse(any(row[0] == "**Sex chromosomes**" for row in table["native_rows"]))

    def test_make_table2_rows_excludes_sex_chromosomes_row_when_absent_for_haplotypes(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "species": "Example species",
            "hap1_assembly_name": "exSpec1.hap1.1",
            "hap2_assembly_name": "exSpec1.hap2.1",
            "hap1_accession": "GCA_123.1",
            "hap2_accession": "GCA_124.1",
            "hap1_assembly_level": "chromosome",
            "hap2_assembly_level": "chromosome",
            "hap1_total_length": "500",
            "hap2_total_length": "490",
            "hap1_chromosome_count": "10",
            "hap2_chromosome_count": "10",
            "hap1_num_contigs": "100",
            "hap2_num_contigs": "100",
            "hap1_contig_N50": "5",
            "hap2_contig_N50": "5",
            "hap1_num_scaffolds": "20",
            "hap2_num_scaffolds": "20",
            "hap1_scaffold_N50": "50",
            "hap2_scaffold_N50": "50",
            "hap1_longest_scaffold_length": "60",
            "hap2_longest_scaffold_length": "59",
            "hap1_sex_chromosomes": "",
            "hap2_sex_chromosomes": "",
        }

        table = make_table2_rows(context)

        self.assertFalse(any(row[0] == "**Sex chromosomes**" for row in table["native_rows"]))

    def test_make_table2_rows_includes_plastid_and_uses_mitochondrial_genome_label(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Example plant",
            "assembly_name": "exPlant1.1",
            "prim_accession": "GCA_123.1",
            "alt_accession": "GCA_124.1",
            "assembly_level": "chromosome",
            "total_length": "1000",
            "chromosome_count": "10",
            "num_contigs": "100",
            "contig_N50": "5",
            "num_scaffolds": "20",
            "scaffold_N50": "50",
            "sex_chromosomes": "",
            "mitochondria": [{"length_kb": 16.0, "accession": "CMITO1"}],
            "plastids": [{"length_kb": 151.0, "accession": "CPLAST1"}],
        }

        table = make_table2_rows(context)

        self.assertTrue(
            any(
                row[0] == "**Organelles**"
                and row[1] == "Mitochondrial genome: 16 kb; Plastid genome: 151 kb"
                for row in table["native_rows"]
            )
        )

    def test_make_table2_rows_uses_plural_mitochondrial_genomes_for_multiple_entries(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Example species",
            "assembly_name": "exSpec1.1",
            "prim_accession": "GCA_123.1",
            "alt_accession": "GCA_124.1",
            "assembly_level": "chromosome",
            "total_length": "1000",
            "chromosome_count": "10",
            "num_contigs": "100",
            "contig_N50": "5",
            "num_scaffolds": "20",
            "scaffold_N50": "50",
            "sex_chromosomes": "",
            "mitochondria": [
                {"length_kb": 123.62, "accession": "CMITO1"},
                {"length_kb": 107.73, "accession": "CMITO2"},
            ],
        }

        table = make_table2_rows(context)

        self.assertTrue(
            any(
                row[0] == "**Organelles**"
                and row[1] == "Mitochondrial genomes: 123.62 and 107.73 kb"
                for row in table["native_rows"]
            )
        )

    def test_make_table2_rows_uses_haploid_assembly_header_and_omits_alternate_row(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Bryoerythrophyllum caledonicum",
            "assembly_name": "cbBryCale10.1",
            "prim_accession": "GCA_963971425.1",
            "assembly_level": "chromosome",
            "total_length": "319.4",
            "chromosome_count": "13",
            "num_contigs": "173",
            "contig_N50": "7.8",
            "num_scaffolds": "13",
            "scaffold_N50": "25.6",
            "is_haploid": True,
        }

        table = make_table2_rows(context)

        self.assertEqual(table["native_headers"][1], "**Haploid assembly**")
        self.assertFalse(any(row[0] == "**Alternate haplotype accession**" for row in table["native_rows"]))

    def test_make_table2_rows_infers_haploid_header_for_single_assembly_moss(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "group_name_ncbi": "mosses",
            "species": "Neckera pumila",
            "assembly_name": "cbNecPumi1.1",
            "prim_accession": "GCA_963969595.1",
            "assembly_level": "chromosome",
            "total_length": "339.34",
            "chromosome_count": "11",
            "num_contigs": "165",
            "contig_N50": "3.72",
            "num_scaffolds": "44",
            "scaffold_N50": "31.05",
        }

        table = make_table2_rows(context)

        self.assertEqual(table["native_headers"][1], "**Haploid assembly**")
        self.assertFalse(any(row[0] == "**Alternate haplotype accession**" for row in table["native_rows"]))

    def test_make_table2_rows_infers_haploid_header_for_single_assembly_male_hymenopteran(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "order": "Hymenoptera",
            "observed_sex": "male",
            "species": "Example hymenopteran",
            "assembly_name": "ihExample1.1",
            "prim_accession": "GCA_000000001.1",
            "assembly_level": "chromosome",
            "total_length": "210.4",
            "chromosome_count": "16",
            "num_contigs": "92",
            "contig_N50": "6.1",
            "num_scaffolds": "16",
            "scaffold_N50": "14.8",
        }

        table = make_table2_rows(context)

        self.assertEqual(table["native_headers"][1], "**Haploid assembly**")
        self.assertFalse(any(row[0] == "**Alternate haplotype accession**" for row in table["native_rows"]))

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

        table = make_table3_rows(context)

        self.assertEqual(len(table["native_rows"]), 1)
        self.assertEqual(table["native_rows"][0][1], "1")

    def test_make_table3_rows_uses_haploid_caption_for_haploid_notes(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Bryoerythrophyllum caledonicum",
            "tolid": "cbBryCale10",
            "is_haploid": True,
            "chromosome_data": [
                {"INSDC": "OX000001.1", "molecule": "1", "length": "45.1", "GC": "39.8"},
            ],
        }

        table = make_table3_rows(context)

        self.assertIn("haploid genome assembly", table["caption"])

    def test_make_table4_rows_includes_hap2_busco_when_available(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "species": "Example species",
            "ebp_metric": "7.C.Q40",
            "hap1_contig_N50": "15.0",
            "hap1_scaffold_N50": "76.17",
            "hap1_QV": "65.6",
            "hap2_QV": "66.5",
            "combined_QV": "66.0",
            "hap1_kmer_completeness": "84.92",
            "hap2_kmer_completeness": "90.38",
            "combined_kmer_completeness": "98.78",
            "hap1_BUSCO_string": "C:92.7% [S:81.3%, D:11.4%], F:0.9%, M:6.4%, n:2 326",
            "hap2_BUSCO_string": "C:93.1% [S:82.0%, D:11.1%], F:0.8%, M:6.1%, n:2 326",
            "hap1_perc_assembled": "93.98",
        }

        table = make_table4_rows(context)

        self.assertTrue(
            any(
                row["measure"] == "BUSCO"
                and row["value"]
                == "Haplotype 1: C:92.7% [S:81.3%, D:11.4%], F:0.9%, M:6.4%, n:2 326; Haplotype 2: C:93.1% [S:82.0%, D:11.1%], F:0.8%, M:6.1%, n:2 326"
                for row in table["native_rows"]
            )
        )

    def test_make_table4_rows_uses_single_assembly_metrics_for_haploid_notes(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Bryoerythrophyllum caledonicum",
            "ebp_metric": "6.C.Q47",
            "contig_N50": "7.8",
            "scaffold_N50": "25.6",
            "prim_QV": "47.0",
            "alt_QV": "46.5",
            "combined_QV": "47.2",
            "prim_kmer_completeness": "98.2",
            "alt_kmer_completeness": "97.9",
            "combined_kmer_completeness": "98.5",
            "BUSCO_string": "C:95.0% [S:94.2%, D:0.8%], F:1.5%, M:3.5%, n:425",
            "perc_assembled": "94.3",
            "is_haploid": True,
        }

        table = make_table4_rows(context)

        self.assertTrue(
            any(
                row["measure"] == "Consensus quality (QV)" and row["value"] == "Haploid assembly: 47.0"
                for row in table["native_rows"]
            )
        )
        self.assertTrue(
            any(
                row["measure"] == "*k*-mer completeness" and row["value"] == "Haploid assembly: 98.2%"
                for row in table["native_rows"]
            )
        )

    def test_make_table4_rows_renders_missing_chromosome_assignment_as_missing(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "species": "Example species",
            "ebp_metric": "6.?.Q47",
            "contig_N50": "7.8",
            "scaffold_N50": "25.6",
            "prim_QV": "47.0",
            "prim_kmer_completeness": "98.2",
            "BUSCO_string": "C:95.0% [S:94.2%, D:0.8%], F:1.5%, M:3.5%, n:425",
            "perc_assembled": None,
            "is_haploid": True,
        }

        table = make_table4_rows(context)

        self.assertTrue(
            any(
                row["measure"] == "Percentage of assembly assigned to chromosomes"
                and row["value"] == r"\-"
                for row in table["native_rows"]
            )
        )

    def test_make_table4_rows_uses_selected_ebp_reference_standard(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "species": "Example species",
            "ebp_metric": "5.C.Q61",
            "ebp_reference_standard": "5.C.Q40",
            "ebp_contig_n50_benchmark_label": "≥ 0.1 Mb",
            "hap1_contig_N50": "0.71",
            "hap1_scaffold_N50": "38.88",
            "hap1_QV": "61.0",
            "hap2_QV": "60.5",
            "combined_QV": "60.9",
            "hap1_kmer_completeness": "98.2",
            "hap2_kmer_completeness": "97.9",
            "combined_kmer_completeness": "98.5",
            "hap1_BUSCO_string": "C:95.0% [S:94.2%, D:0.8%], F:1.5%, M:3.5%, n:425",
            "hap2_BUSCO_string": "C:95.1% [S:94.3%, D:0.8%], F:1.4%, M:3.5%, n:425",
            "hap1_perc_assembled": "99.48",
        }

        table = make_table4_rows(context)

        self.assertTrue(
            any(
                row["measure"] == "EBP summary (haplotype 1)"
                and row["benchmark"] == "5.C.Q40"
                for row in table["native_rows"]
            )
        )
        self.assertTrue(
            any(
                row["measure"] == "Contig N50 length"
                and row["benchmark"] == "≥ 0.1 Mb"
                for row in table["native_rows"]
            )
        )


if __name__ == "__main__":
    unittest.main()
