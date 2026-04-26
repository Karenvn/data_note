from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from data_note.ensembl_endpoint_config import EnsemblEndpointConfig
from data_note.ensembl_graphql_client import EnsemblGraphqlClient


class EnsemblComponentTests(unittest.TestCase):
    def test_select_matching_genome_prefers_exact_accession(self) -> None:
        genomes = [
            {"assembly_accession": "GCA_000001405.14", "genome_id": "old"},
            {"assembly_accession": "GCA_000001405.29", "genome_id": "target"},
        ]

        selected = EnsemblGraphqlClient.select_matching_genome(genomes, "GCA_000001405.29")

        self.assertEqual(selected, genomes[1])

    def test_select_matching_genome_falls_back_to_base_accession(self) -> None:
        genomes = [
            {"assembly_accession": "GCA_000001405.14", "genome_id": "fallback"},
            {"assembly_accession": "GCA_999999999.1", "genome_id": "other"},
        ]

        selected = EnsemblGraphqlClient.select_matching_genome(genomes, "GCA_000001405.29")

        self.assertEqual(selected, genomes[0])

    @patch("data_note.ensembl_graphql_client.requests.post")
    def test_fetch_beta_metadata_prefers_exact_accession_match(self, mock_post: Mock) -> None:
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "data": {
                        "genomes": [
                            {"assembly_accession": "GCA_000001405.14", "genome_id": "old"},
                            {"assembly_accession": "GCA_000001405.29", "genome_id": "target"},
                        ]
                    }
                }
            ),
        )

        client = EnsemblGraphqlClient(request_post=mock_post)
        result = client.fetch_beta_metadata("9606", "GCA_000001405.29")

        self.assertEqual(result["annot_accession"], "GCA_000001405.29")
        self.assertEqual(result["annot_url"], "https://beta.ensembl.org/species/target")

    def test_endpoint_config_from_env_respects_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GN_ENSEMBL_GRAPHQL_URL": "https://example.org/graphql/",
                "GN_ENSEMBL_ORGANISMS_BASE": "https://example.org/organisms",
            },
            clear=False,
        ):
            config = EnsemblEndpointConfig.from_env()

        self.assertEqual(config.beta_graphql_url, "https://example.org/graphql")
        self.assertEqual(config.organisms_base, "https://example.org/organisms/")


if __name__ == "__main__":
    unittest.main()
