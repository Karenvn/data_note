from __future__ import annotations

import unittest

from data_note.ncbi_datasets_client import NcbiDatasetsClient
from data_note.ncbi_organelle_client import NcbiOrganelleClient
from data_note.ncbi_taxonomy_client import NcbiTaxonomyClient


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.content = payload if isinstance(payload, (bytes, str)) else b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class NcbiTaxonomyClientTests(unittest.TestCase):
    def test_fetch_lineage_and_ranks_uses_datasets_taxonomy_report(self) -> None:
        def parent_report(tax_id: int, rank: str, name: str):
            return {
                "taxonomy": {
                    "tax_id": tax_id,
                    "rank": rank,
                    "current_scientific_name": {"name": name},
                }
            }

        calls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            self.assertEqual(headers, {"accept": "application/json"})
            self.assertEqual(timeout, 30)
            calls.append((url, params))
            if url == "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/9606/dataset_report":
                self.assertEqual(params, {"returned_content": "METADATA"})
                return _Response(
                    200,
                    {
                        "reports": [
                            {
                                "taxonomy": {
                                    "tax_id": 9606,
                                    "rank": "SPECIES",
                                    "current_scientific_name": {
                                        "name": "Homo sapiens",
                                        "authority": "Linnaeus, 1758",
                                    },
                                    "curator_common_name": "human",
                                    "group_name": "primates",
                                    "parents": [
                                        1,
                                        131567,
                                        2759,
                                        33154,
                                        33208,
                                        7711,
                                        40674,
                                        9443,
                                        9604,
                                        207598,
                                        9605,
                                    ],
                                    "classification": {
                                        "domain": {"name": "Eukaryota", "id": 2759},
                                        "kingdom": {"name": "Metazoa", "id": 33208},
                                        "phylum": {"name": "Chordata", "id": 7711},
                                        "class": {"name": "Mammalia", "id": 40674},
                                        "order": {"name": "Primates", "id": 9443},
                                        "family": {"name": "Hominidae", "id": 9604},
                                        "genus": {"name": "Homo", "id": 9605},
                                        "species": {"name": "Homo sapiens", "id": 9606},
                                    },
                                }
                            }
                        ]
                    },
                )
            if (
                url
                == "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/"
                "2759,33154,33208,7711,40674,9443,9604,207598,9605/dataset_report"
            ):
                self.assertEqual(params, {"returned_content": "METADATA", "page_size": 9})
                return _Response(
                    200,
                    {
                        "reports": [
                            parent_report(9605, "GENUS", "Homo"),
                            parent_report(33154, "CLADE", "Opisthokonta"),
                            parent_report(2759, "DOMAIN", "Eukaryota"),
                            parent_report(207598, "SUBFAMILY", "Homininae"),
                            parent_report(9604, "FAMILY", "Hominidae"),
                            parent_report(33208, "KINGDOM", "Metazoa"),
                            parent_report(7711, "PHYLUM", "Chordata"),
                            parent_report(40674, "CLASS", "Mammalia"),
                            parent_report(9443, "ORDER", "Primates"),
                        ]
                    },
                )
            raise AssertionError(f"unexpected URL {url}")

        client = NcbiTaxonomyClient(session_get=fake_get)
        taxonomy = client.fetch_lineage_and_ranks("9606")

        self.assertEqual(len(calls), 2)
        self.assertEqual(taxonomy["tax_id"], "9606")
        self.assertEqual(taxonomy["species"], "Homo sapiens")
        self.assertEqual(taxonomy["genus"], "Homo")
        self.assertEqual(taxonomy["family"], "Hominidae")
        self.assertEqual(
            taxonomy["lineage"],
            (
                "Eukaryota; Opisthokonta; Metazoa; Chordata; Mammalia; Primates; "
                "Hominidae; Homininae; *Homo*; *Homo sapiens*"
            ),
        )
        self.assertEqual(taxonomy["lineage_source"], "ncbi_datasets_parents")
        self.assertEqual(taxonomy["tax_auth_ncbi"], "Linnaeus, 1758")
        self.assertEqual(taxonomy["common_name_ncbi"], "human")

    def test_parse_taxonomy_report_adds_brackets_when_basionym_genus_differs(self) -> None:
        taxonomy = NcbiTaxonomyClient.parse_taxonomy_report(
            {
                "taxonomy": {
                    "tax_id": 3698974,
                    "current_scientific_name": {
                        "name": "Maea johnstoni",
                        "authority": "Fiege, Licher & Mackie, 2000",
                        "basionym": {
                            "name": "Magelona johnstoni",
                            "authority": "Fiege, Licher & Mackie, 2000",
                        },
                    },
                    "classification": {
                        "family": {"name": "Magelonidae", "id": 2700},
                        "genus": {"name": "Maea", "id": 1},
                        "species": {"name": "Maea johnstoni", "id": 3698974},
                    },
                }
            }
        )

        self.assertEqual(taxonomy["tax_auth_ncbi"], "(Fiege, Licher & Mackie, 2000)")
        self.assertEqual(taxonomy["original_combination_ncbi"], "Magelona johnstoni")
        self.assertEqual(taxonomy["tax_auth_ncbi_verification"], "SOURCE_MISSING_BRACKETS")
        self.assertEqual(taxonomy["tax_auth_ncbi_raw"], "Fiege, Licher & Mackie, 2000")

    def test_parse_taxonomy_report_removes_brackets_when_basionym_genus_matches(self) -> None:
        taxonomy = NcbiTaxonomyClient.parse_taxonomy_report(
            {
                "taxonomy": {
                    "tax_id": 12345,
                    "current_scientific_name": {
                        "name": "Example species",
                        "authority": "(Author, 1900)",
                        "basionym": {
                            "name": "Example species",
                            "authority": "Author, 1900",
                        },
                    },
                    "classification": {
                        "genus": {"name": "Example", "id": 1},
                        "species": {"name": "Example species", "id": 12345},
                    },
                }
            }
        )

        self.assertEqual(taxonomy["tax_auth_ncbi"], "Author, 1900")
        self.assertEqual(taxonomy["tax_auth_ncbi_verification"], "SOURCE_UNNEEDED_BRACKETS")
        self.assertEqual(taxonomy["tax_auth_ncbi_raw"], "(Author, 1900)")

    def test_parse_taxonomy_report_falls_back_to_classification_lineage(self) -> None:
        taxonomy = NcbiTaxonomyClient.parse_taxonomy_report(
            {
                "taxonomy": {
                    "tax_id": 9606,
                    "current_scientific_name": {"name": "Homo sapiens"},
                    "classification": {
                        "domain": {"name": "Eukaryota", "id": 2759},
                        "kingdom": {"name": "Metazoa", "id": 33208},
                        "phylum": {"name": "Chordata", "id": 7711},
                        "class": {"name": "Mammalia", "id": 40674},
                        "order": {"name": "Primates", "id": 9443},
                        "family": {"name": "Hominidae", "id": 9604},
                        "genus": {"name": "Homo", "id": 9605},
                        "species": {"name": "Homo sapiens", "id": 9606},
                    },
                }
            }
        )

        self.assertEqual(
            taxonomy["lineage"],
            (
                "Eukaryota; Metazoa; Chordata; Mammalia; Primates; "
                "Hominidae; *Homo*; *Homo sapiens*"
            ),
        )
        self.assertEqual(taxonomy["lineage_source"], "ncbi_datasets_classification")

    def test_parse_taxonomy_report_italicises_subgenus_from_parent_lineage(self) -> None:
        taxonomy = NcbiTaxonomyClient.parse_taxonomy_report(
            {
                "taxonomy": {
                    "tax_id": 373668,
                    "current_scientific_name": {"name": "Tipula scripta"},
                    "classification": {
                        "genus": {"name": "Tipula", "id": 4000},
                        "species": {"name": "Tipula scripta", "id": 373668},
                    },
                }
            },
            lineage_records=[
                {"tax_id": "4000", "rank": "GENUS", "name": "Tipula"},
                {"tax_id": "4001", "rank": "SUBGENUS", "name": "Vestiplex"},
                {"tax_id": "373668", "rank": "SPECIES", "name": "Tipula scripta"},
            ],
        )

        self.assertEqual(
            taxonomy["lineage"],
            "*Tipula*; *Vestiplex*; *Tipula scripta*",
        )
        self.assertEqual(taxonomy["lineage_source"], "ncbi_datasets_parents")

    def test_parse_taxonomy_report_includes_and_italicises_subgenus_from_classification(self) -> None:
        taxonomy = NcbiTaxonomyClient.parse_taxonomy_report(
            {
                "taxonomy": {
                    "tax_id": 373668,
                    "current_scientific_name": {"name": "Tipula scripta"},
                    "classification": {
                        "genus": {"name": "Tipula", "id": 4000},
                        "subgenus": {"name": "Vestiplex", "id": 4001},
                        "species": {"name": "Tipula scripta", "id": 373668},
                    },
                }
            }
        )

        self.assertEqual(
            taxonomy["lineage"],
            "*Tipula*; *Vestiplex*; *Tipula scripta*",
        )
        self.assertEqual(taxonomy["lineage_source"], "ncbi_datasets_classification")

    def test_fetch_lineage_and_ranks_returns_empty_dict_when_report_missing(self) -> None:
        client = NcbiTaxonomyClient(
            session_get=lambda url, headers=None, params=None, timeout=None: _Response(200, {"reports": []})
        )
        self.assertEqual(client.fetch_lineage_and_ranks("9606"), {})


class NcbiDatasetsClientTests(unittest.TestCase):
    def test_fetch_primary_assembly_info_parses_dataset_report(self) -> None:
        def fake_get(url, headers=None, params=None, timeout=None):
            self.assertEqual(
                url,
                "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/GCA_123456789.1/dataset_report",
            )
            self.assertEqual(headers["accept"], "application/json")
            self.assertEqual(timeout, 30)
            return _Response(
                200,
                {
                    "reports": [
                        {
                            "assembly_info": {
                                "assembly_level": "Chromosome",
                                "biosample": {
                                    "attributes": [
                                        {"name": "tolid", "value": "ixExample1"},
                                    ]
                                },
                                "linked_assemblies": [
                                    {"linked_assembly": "GCA_987654321.1"},
                                ],
                            },
                            "assembly_stats": {
                                "total_sequence_length": 123456789,
                                "number_of_contigs": 22,
                                "contig_n50": 1200000,
                                "number_of_scaffolds": 10,
                                "scaffold_n50": 5600000,
                                "total_number_of_chromosomes": 8,
                                "genome_coverage": "45x",
                            },
                            "wgs_info": {
                                "wgs_project_accession": "JABC01",
                            },
                        }
                    ]
                },
            )

        client = NcbiDatasetsClient(request_get=fake_get)
        info = client.fetch_primary_assembly_info("GCA_123456789.1")

        self.assertEqual(info["assembly_level"], "chromosome")
        self.assertEqual(info["total_length"], "123.46")
        self.assertEqual(info["num_contigs"], "22")
        self.assertEqual(info["contig_N50"], 1.2)
        self.assertEqual(info["num_scaffolds"], "10")
        self.assertEqual(info["scaffold_N50"], 5.6)
        self.assertEqual(info["chromosome_count"], 8)
        self.assertEqual(info["genome_length_unrounded"], 123456789.0)
        self.assertEqual(info["coverage"], "45x")
        self.assertEqual(info["tolid"], "ixExample1")
        self.assertEqual(info["wgs_project_accession"], "JABC01")
        self.assertEqual(info["linked_assemblies"], ["GCA_987654321.1"])

    def test_fetch_haplotype_assembly_info_prefixes_each_haplotype(self) -> None:
        class _StubClient(NcbiDatasetsClient):
            def fetch_primary_assembly_info(self, accession: str) -> dict[str, str]:
                return {
                    "assembly_level": "chromosome",
                    "tolid": "ixExample1",
                    "wgs_project_accession": "JABC01",
                    "coverage": accession,
                }

        client = _StubClient()

        combined = client.fetch_haplotype_assembly_info("GCA_H1.1", "GCA_H2.1")

        self.assertEqual(combined["hap1_coverage"], "GCA_H1.1")
        self.assertEqual(combined["hap2_coverage"], "GCA_H2.1")
        self.assertEqual(combined["tolid"], "ixExample1")
        self.assertEqual(combined["wgs_project_accession"], "JABC01")

class NcbiOrganelleClientTests(unittest.TestCase):
    def test_fetch_organelle_info_groups_mitochondria_and_plastids(self) -> None:
        class _StubClient(NcbiOrganelleClient):
            def fetch_sequence_reports(self, accession: str) -> list[dict[str, object]]:
                return [
                    {
                        "role": "assembled-molecule",
                        "assigned_molecule_location_type": "Mitochondrion",
                        "chr_name": "MT",
                        "length": 16000,
                        "genbank_accession": "CMITO1",
                        "refseq_accession": "N/A",
                        "gc_percent": 43.5,
                    },
                    {
                        "role": "assembled-molecule",
                        "assigned_molecule_location_type": "Chloroplast",
                        "chr_name": "CP",
                        "length": 151000,
                        "genbank_accession": "CPLAST1",
                        "refseq_accession": "N/A",
                        "gc_percent": 37.2,
                    },
                ]

        client = _StubClient()

        organelles = client.fetch_organelle_info("GCA_123456789.1")

        self.assertIn("mitochondria", organelles)
        self.assertIn("plastids", organelles)
        self.assertEqual(organelles["mito_accession"], "CMITO1")
        self.assertEqual(organelles["plastid_accession"], "CPLAST1")
        self.assertEqual(organelles["length_mito_kb"], "16.0")
        self.assertEqual(organelles["length_plastid_kb"], "151.0")

    def test_fetch_organelle_template_data_formats_display_strings(self) -> None:
        class _StubClient(NcbiOrganelleClient):
            def fetch_organelle_info(self, accession: str) -> dict[str, object]:
                return {
                    "mitochondria": [{"length_kb": 16.0, "accession": "CMITO1"}],
                    "plastids": [{"length_kb": 151.0, "accession": "CPLAST1"}],
                }

        client = _StubClient()
        template_data = client.fetch_organelle_template_data("GCA_123456789.1")

        self.assertTrue(template_data["has_mitochondria"])
        self.assertTrue(template_data["has_plastids"])
        self.assertEqual(template_data["mito_display"], "length 16.0 kb (CMITO1)")
        self.assertEqual(template_data["mito_lengths_display"], "16.0")
        self.assertEqual(template_data["plastid_display"], "length 151.0 kb (CPLAST1)")
        self.assertEqual(template_data["plastid_lengths_display"], "151.0")

    def test_fetch_organelle_template_data_uses_and_for_multiple_display_strings(self) -> None:
        class _StubClient(NcbiOrganelleClient):
            def fetch_organelle_info(self, accession: str) -> dict[str, object]:
                return {
                    "mitochondria": [
                        {"length_kb": 913.22, "accession": "CMITO1"},
                        {"length_kb": 326.74, "accession": "CMITO2"},
                        {"length_kb": 225.31, "accession": "CMITO3"},
                    ],
                    "plastids": [
                        {"length_kb": 151.0, "accession": "CPLAST1"},
                        {"length_kb": 149.5, "accession": "CPLAST2"},
                    ],
                }

        client = _StubClient()
        template_data = client.fetch_organelle_template_data("GCA_123456789.1")

        self.assertEqual(
            template_data["mito_display"],
            "lengths 913.22 kb (CMITO1), 326.74 kb (CMITO2) and 225.31 kb (CMITO3)",
        )
        self.assertEqual(
            template_data["mito_lengths_display"],
            "913.22, 326.74 and 225.31",
        )
        self.assertEqual(
            template_data["plastid_display"],
            "lengths 151.0 kb (CPLAST1) and 149.5 kb (CPLAST2)",
        )
        self.assertEqual(
            template_data["plastid_lengths_display"],
            "151.0 and 149.5",
        )


if __name__ == "__main__":
    unittest.main()
