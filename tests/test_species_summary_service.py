from __future__ import annotations

import unittest
from unittest.mock import patch

from data_note.gbif_occurrence_client import GbifOccurrenceClient
from data_note.models import AssemblyRecord, AssemblySelection
from data_note.species_summary_models import GbifDistributionSummary, SpeciesSummary
from data_note.species_summary_service import SpeciesSummaryService, _normalise_assembly_input


class _StubTaxonomyClient:
    def fetch_lineage_and_ranks(self, taxid: str) -> dict[str, object]:
        return {
            "species": "Example species",
            "genus": "Examplegenus",
            "genus_taxid": 101,
            "family": "Exampleidae",
            "family_taxid": 202,
        }


class _StubDatasetsClient:
    def fetch_taxon_reports(self, taxid: int | str, *, page_size: int = 1000) -> list[dict[str, object]]:
        del page_size
        if str(taxid) == "101":
            return [
                {
                    "accession": "GCA_1.1",
                    "assembly_name": "ixExample1.1",
                    "organism": {"organism_name": "Example species"},
                    "assembly_info": {
                        "assembly_name": "ixExample1.1",
                        "assembly_level": "chromosome",
                        "submitter": "example institute",
                        "refseq_category": "representative genome",
                    },
                },
                {
                    "accession": "GCF_1.1",
                    "assembly_name": "ixExample1.1",
                    "organism": {"organism_name": "Example species"},
                    "assembly_info": {
                        "assembly_name": "ixExample1.1",
                        "assembly_level": "chromosome",
                        "submitter": "example institute",
                    },
                },
                {
                    "accession": "GCA_2.1",
                    "assembly_name": "OtherSpeciesBuild.1",
                    "organism": {"organism_name": "Example species"},
                    "assembly_info": {
                        "assembly_name": "OtherSpeciesBuild.1",
                        "assembly_level": "scaffold",
                        "submitter": "other consortium",
                    },
                },
                {
                    "accession": "GCA_3.1",
                    "assembly_name": "Othergenus.1",
                    "organism": {"organism_name": "Other species"},
                    "assembly_info": {
                        "assembly_name": "Othergenus.1",
                        "assembly_level": "chromosome",
                        "submitter": "other consortium",
                    },
                },
            ]
        return [
            {
                "accession": "GCA_1.1",
                "assembly_name": "ixExample1.1",
                "organism": {"organism_name": "Example species"},
                "assembly_info": {
                    "assembly_name": "ixExample1.1",
                    "assembly_level": "chromosome",
                    "submitter": "example institute",
                    "refseq_category": "representative genome",
                },
            },
            {
                "accession": "GCA_3.1",
                "assembly_name": "Othergenus.1",
                "organism": {"organism_name": "Other species"},
                "assembly_info": {
                    "assembly_name": "Othergenus.1",
                    "assembly_level": "chromosome",
                    "submitter": "other consortium",
                },
            },
            {
                "accession": "GCA_4.1",
                "assembly_name": "AnotherFamilyBuild.1",
                "organism": {"organism_name": "Family neighbour"},
                "assembly_info": {
                    "assembly_name": "AnotherFamilyBuild.1",
                    "assembly_level": "contig",
                    "submitter": "family project",
                },
            },
        ]


class _StubGbifOccurrenceClient(GbifOccurrenceClient):
    def __init__(self) -> None:
        pass

    def fetch_distribution_summary(
        self,
        usage_key: int | str,
        *,
        facet_limit: int = 20,
    ) -> GbifDistributionSummary:
        del facet_limit
        return GbifDistributionSummary(
            usage_key=str(usage_key),
            record_count=12,
            species_url=f"https://www.gbif.org/species/{usage_key}",
        )

    def render_distribution_summary(self, summary: GbifDistributionSummary) -> str:
        return f"Distribution for {summary.usage_key}"


class SpeciesSummaryServiceTests(unittest.TestCase):
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

    def test_summarise_genomes_returns_intro_text_from_build_summary(self) -> None:
        summary = SpeciesSummary(
            species_taxid="12345",
            species="Example species",
            genus="Examplegenus",
            family="Exampleidae",
            intro_text="Example automatic summary.",
        )
        service = SpeciesSummaryService(
            taxonomy_client=_StubTaxonomyClient(),
            datasets_client=_StubDatasetsClient(),
            gbif_fetcher=lambda species, tax_id: {},
            gbif_occurrence_client=_StubGbifOccurrenceClient(),
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )

        with patch.object(SpeciesSummaryService, "build_summary", return_value=summary) as mock_build_summary:
            text = service.summarise_genomes(12345, selection, tolid="ixExample1")

        self.assertEqual(text, "Example automatic summary.")
        mock_build_summary.assert_called_once_with(
            12345,
            selection,
            tolid="ixExample1",
            include_distribution=False,
        )

    def test_build_summary_uses_dataset_reports_directly(self) -> None:
        service = SpeciesSummaryService(
            taxonomy_client=_StubTaxonomyClient(),
            datasets_client=_StubDatasetsClient(),
            gbif_fetcher=lambda species, tax_id: {"gbif_usage_key": "999"} if species == "Example species" and str(tax_id) == "12345" else {},
            gbif_occurrence_client=_StubGbifOccurrenceClient(),
        )
        selection = AssemblySelection(
            assemblies_type="prim_alt",
            primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
        )

        summary = service.build_summary(12345, selection, tolid="ixExample1", include_distribution=True)

        self.assertIsInstance(summary, SpeciesSummary)
        self.assertEqual(summary.genus_genome_count, 3)
        self.assertEqual(summary.family_genome_count, 3)
        self.assertEqual(len(summary.other_species_assemblies), 1)
        self.assertIn("GCA_2.1", summary.intro_text)
        self.assertIn("RefSeq representative assembly", summary.intro_text)
        self.assertEqual(summary.gbif_usage_key, "999")
        self.assertEqual(summary.distribution_text, "Distribution for 999")


if __name__ == "__main__":
    unittest.main()
