from __future__ import annotations

import unittest

from data_note.chromosome_analyzer import ChromosomeAnalyzer
from data_note.models import (
    AssemblyDatasetsInfo,
    AssemblyRecord,
    AssemblySelection,
    BtkSummary,
    ChromosomeSummary,
)
from data_note.services.btk_service import BtkService
from data_note.services.chromosome_service import ChromosomeService
from data_note.services.ncbi_datasets_service import NcbiDatasetsService


class NcbiDatasetsServiceTests(unittest.TestCase):
    def test_build_context_uses_primary_record_from_selection(self) -> None:
        service = NcbiDatasetsService(
            primary_info_fetcher=lambda accession: {"assembly_info_accession": accession},
            organelle_template_fetcher=lambda accession: f"template:{accession}",
            organelle_info_fetcher=lambda accession: {"organelle_accession": accession},
            longest_scaffold_fetcher=lambda accession: f"longest:{accession}",
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )

        datasets_info = service.build_context(selection)
        context = datasets_info.to_context_dict()

        self.assertIsInstance(datasets_info, AssemblyDatasetsInfo)
        self.assertEqual(context["assembly_info_accession"], "GCA_1.1")
        self.assertEqual(context["organelle_data"], "template:GCA_1.1")
        self.assertEqual(context["organelle_accession"], "GCA_1.1")
        self.assertEqual(context["longest_scaffold_length"], "longest:GCA_1.1")

    def test_build_context_uses_haplotype_records_from_selection(self) -> None:
        service = NcbiDatasetsService(
            haplotype_info_fetcher=lambda hap1, hap2: {"pair": (hap1, hap2)},
            organelle_template_fetcher=lambda accession: f"template:{accession}",
            organelle_info_fetcher=lambda accession: {"organelle_accession": accession},
            longest_scaffold_fetcher=lambda accession: f"longest:{accession}",
        )
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_h1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_h2", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        datasets_info = service.build_context(selection)
        context = datasets_info.to_context_dict()

        self.assertIsInstance(datasets_info, AssemblyDatasetsInfo)
        self.assertEqual(context["pair"], ("GCA_h1", "GCA_h2"))
        self.assertEqual(context["organelle_data"], "template:GCA_h1")
        self.assertEqual(context["hap1_longest_scaffold_length"], "longest:GCA_h1")
        self.assertEqual(context["hap2_longest_scaffold_length"], "longest:GCA_h2")


class ChromosomeServiceTests(unittest.TestCase):
    def test_identify_sex_chromosomes_excludes_supernumerary_b_chromosomes(self) -> None:
        rows = [{"molecule": "X"}, {"molecule": "B"}, {"molecule": "B2"}, {"molecule": "Z"}]
        self.assertEqual(ChromosomeAnalyzer.identify_sex_chromosomes(rows), ["X", "Z"])
        self.assertEqual(ChromosomeAnalyzer.identify_supernumerary_chromosomes(rows), ["B", "B2"])

    def test_build_context_uses_primary_record_from_selection(self) -> None:
        service = ChromosomeService(
            primary_table_fetcher=lambda accession: [{"molecule": "X"}, {"molecule": "B1"}],
            supernumerary_chromosome_identifier=lambda rows: [row["molecule"] for row in rows if row["molecule"].startswith("B")],
            sex_chromosome_formatter=lambda labels: ",".join(labels) if labels else None,
            supernumerary_chromosome_formatter=lambda labels: ",".join(labels) if labels else None,
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )

        summary = service.build_context(selection, {})
        context = summary.to_context_dict()

        self.assertIsInstance(summary, ChromosomeSummary)
        self.assertEqual(context["chromosome_data"], [{"molecule": "X"}, {"molecule": "B1"}])
        self.assertEqual(context["sex_chromosomes"], "X")
        self.assertEqual(context["supernumerary_chromosomes"], "B1")

    def test_build_context_uses_haplotype_records_from_selection(self) -> None:
        service = ChromosomeService(
            haplotype_table_combiner=lambda hap1, hap2: [
                {"hap1_molecule": "X", "hap2_molecule": "Y"},
                {"hap1_molecule": "B2", "hap2_molecule": "B1"},
            ],
            supernumerary_chromosome_identifier=lambda rows: [row["molecule"] for row in rows if row["molecule"].startswith("B")],
            sex_chromosome_formatter=lambda labels: ",".join(labels) if labels else None,
            supernumerary_chromosome_formatter=lambda labels: ",".join(labels) if labels else None,
        )
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_h1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_h2", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        summary = service.build_context(
            selection,
            {"hap1_assembly_level": "chromosome", "hap2_assembly_level": "chromosome"},
        )
        context = summary.to_context_dict()

        self.assertIsInstance(summary, ChromosomeSummary)
        self.assertEqual(
            context["chromosome_data"],
            [
                {"hap1_molecule": "X", "hap2_molecule": "Y"},
                {"hap1_molecule": "B2", "hap2_molecule": "B1"},
            ],
        )
        self.assertEqual(context["hap1_sex_chromosomes"], "X")
        self.assertEqual(context["hap2_sex_chromosomes"], "Y")
        self.assertEqual(context["all_sex_chromosomes"], "X,Y")
        self.assertEqual(context["hap1_supernumerary_chromosomes"], "B2")
        self.assertEqual(context["hap2_supernumerary_chromosomes"], "B1")
        self.assertEqual(context["all_supernumerary_chromosomes"], "B1,B2")


class BtkServiceTests(unittest.TestCase):
    def test_build_context_uses_primary_record_from_selection(self) -> None:
        service = BtkService(
            summary_fetcher=lambda accession, prefix="": {f"{prefix}summary_accession": accession},
            software_versions_fetcher=lambda accession: {"software_accession": accession},
            url_builder=lambda accession, prefix="": (
                {f"{prefix}view_url": f"view:{accession}"},
                {f"{prefix}download_url": f"download:{accession}"},
            ),
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixFooBar1.1", role="primary"),
        )

        summary = service.build_context(selection)
        context = summary.to_context_dict()

        self.assertIsInstance(summary, BtkSummary)
        self.assertEqual(context["summary_accession"], "GCA_1.1")
        self.assertEqual(context["software_accession"], "GCA_1.1")
        self.assertEqual(context["view_url"], "view:GCA_1.1")
        self.assertEqual(context["download_url"], "download:GCA_1.1")

    def test_build_context_uses_haplotype_records_from_selection(self) -> None:
        service = BtkService(
            summary_fetcher=lambda accession, prefix="": {f"{prefix}summary_accession": accession},
            software_versions_fetcher=lambda accession: {"software_accession": accession},
            url_builder=lambda accession, prefix="": (
                {f"{prefix}view_url": f"view:{accession}"},
                {f"{prefix}download_url": f"download:{accession}"},
            ),
        )
        selection = AssemblySelection(
            assemblies_type="hap_asm",
            hap1=AssemblyRecord(accession="GCA_h1", assembly_name="ixFooBar1.hap1.1", role="hap1"),
            hap2=AssemblyRecord(accession="GCA_h2", assembly_name="ixFooBar1.hap2.1", role="hap2"),
        )

        summary = service.build_context(selection)
        context = summary.to_context_dict()

        self.assertIsInstance(summary, BtkSummary)
        self.assertEqual(context["hap1_summary_accession"], "GCA_h1")
        self.assertEqual(context["software_accession"], "GCA_h1")
        self.assertEqual(context["hap1_view_url"], "view:GCA_h1")
        self.assertEqual(context["hap1_download_url"], "download:GCA_h1")
        self.assertEqual(context["hap2_summary_accession"], "GCA_h2")
        self.assertEqual(context["hap2_view_url"], "view:GCA_h2")
        self.assertEqual(context["hap2_download_url"], "download:GCA_h2")


if __name__ == "__main__":
    unittest.main()
