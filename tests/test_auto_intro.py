from __future__ import annotations

import unittest
from unittest.mock import patch

from data_note.auto_intro import _normalise_assembly_input, summarise_genomes
from data_note.models import AssemblyRecord, AssemblySelection


class AutoIntroTests(unittest.TestCase):
    def test_normalise_assembly_input_accepts_assembly_selection(self) -> None:
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_2.1", assembly_name="ixExample.hap2.1", role="hap2"),
        )

        context = _normalise_assembly_input(selection)

        self.assertEqual(context["assemblies_type"], "hap_asm")
        self.assertEqual(context["hap1_accession"], "GCA_1.1")
        self.assertEqual(context["hap2_accession"], "GCA_2.1")

    @patch("data_note.auto_intro.fetch_taxon_report")
    @patch("data_note.auto_intro.acc_info")
    @patch("data_note.auto_intro.get_lineage")
    def test_summarise_genomes_accepts_assembly_selection(
        self,
        mock_get_lineage,
        mock_acc_info,
        mock_fetch_taxon_report,
    ) -> None:
        mock_get_lineage.return_value = {
            "species": "Example species",
            "genus": "Examplegenus",
            "genus_taxid": 101,
            "family": "Exampleidae",
            "family_taxid": 202,
        }
        mock_acc_info.return_value = ("Example species", "Example Submitter", "representative genome")
        mock_fetch_taxon_report.side_effect = [
            [
                {
                    "accession": "GCA_1.1",
                    "assembly_name": "ixExample1.1",
                    "assembly_info": {"assembly_level": "chromosome"},
                }
            ],
            [
                {
                    "accession": "GCA_1.1",
                    "assembly_name": "ixExample1.1",
                    "assembly_info": {"assembly_level": "chromosome"},
                }
            ],
        ]
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )

        sentence = summarise_genomes(12345, selection, tolid="ixExample1", show_tables=False)

        self.assertIn("first high‑quality genome for the genus", sentence)
        self.assertIn("RefSeq representative assembly", sentence)

    @patch("data_note.auto_intro.fetch_taxon_report")
    @patch("data_note.auto_intro.acc_info")
    @patch("data_note.auto_intro.get_lineage")
    def test_summarise_genomes_still_accepts_mapping_input(
        self,
        mock_get_lineage,
        mock_acc_info,
        mock_fetch_taxon_report,
    ) -> None:
        mock_get_lineage.return_value = {
            "species": "Example species",
            "genus": "Examplegenus",
            "genus_taxid": 101,
            "family": "Exampleidae",
            "family_taxid": 202,
        }
        mock_acc_info.return_value = ("Example species", "Example Submitter", "na")
        mock_fetch_taxon_report.side_effect = [[], []]

        sentence = summarise_genomes(
            12345,
            {"assemblies_type": "prim_alt", "prim_accession": "GCA_1.1"},
            tolid="ixExample1",
            show_tables=False,
        )

        self.assertIsInstance(sentence, str)


if __name__ == "__main__":
    unittest.main()
