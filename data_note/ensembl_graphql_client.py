from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .ensembl_endpoint_config import EnsemblEndpointConfig


@dataclass(slots=True)
class EnsemblGraphqlClient:
    config: EnsemblEndpointConfig = field(default_factory=EnsemblEndpointConfig.from_env)
    request_post: Callable[..., Any] = requests.post
    timeout: int = 30

    @staticmethod
    def select_matching_genome(
        genomes: list[dict[str, Any]],
        target_accession: str | None,
    ) -> dict[str, Any] | None:
        if not genomes:
            return None
        if not target_accession:
            return genomes[0]

        target_accession = target_accession.strip()
        for genome in genomes:
            if genome.get("assembly_accession") == target_accession:
                return genome

        target_base = target_accession.split(".")[0]
        for genome in genomes:
            accession = genome.get("assembly_accession")
            if accession and str(accession).split(".")[0] == target_base:
                return genome

        return genomes[0]

    def fetch_beta_metadata(
        self,
        taxon_id: str | int,
        target_accession: str | None = None,
    ) -> dict[str, str]:
        query = """
        query Annotation($taxon: String) {
            genomes(by_keyword: {species_taxonomy_id: $taxon }) {
                assembly_accession
                genome_id
            }
        }
        """
        variables = {"taxon": str(taxon_id)}

        try:
            response = self.request_post(
                url=self.config.beta_graphql_url,
                json={"query": query, "variables": variables},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                genomes = data.get("data", {}).get("genomes", [])
                if genomes:
                    selected = self.select_matching_genome(genomes, target_accession)
                    if selected and selected.get("assembly_accession") and selected.get("genome_id"):
                        accession = str(selected["assembly_accession"])
                        genome_id = str(selected["genome_id"])
                        return {
                            "annot_accession": accession,
                            "annot_url": f"https://beta.ensembl.org/species/{genome_id}",
                        }

            if target_accession:
                fallback = self._query_by_accession(target_accession)
                if fallback:
                    return fallback

            self.config.debug_print(f"GraphQL query failed or returned no results for taxon {taxon_id}")
            return {}
        except Exception as exc:
            self.config.debug_print(f"Error querying beta metadata: {exc}")
            if target_accession:
                return self._query_by_accession(target_accession)
            return {}

    def _query_by_accession(self, accession: str) -> dict[str, str]:
        if not accession:
            return {}

        for key in ("assembly_accession", "assembly"):
            query = f"""
            query Annotation($acc: String) {{
                genomes(by_keyword: {{{key}: $acc }}) {{
                    assembly_accession
                    genome_id
                }}
            }}
            """
            try:
                response = self.request_post(
                    url=self.config.beta_graphql_url,
                    json={"query": query, "variables": {"acc": accession}},
                    timeout=self.timeout,
                )
                if response.status_code != 200:
                    continue
                data = response.json()
                if "errors" in data:
                    continue
                genomes = data.get("data", {}).get("genomes", [])
                if genomes:
                    genome = genomes[0]
                    if genome.get("assembly_accession") and genome.get("genome_id"):
                        genome_id = str(genome["genome_id"])
                        return {
                            "annot_accession": str(genome["assembly_accession"]),
                            "annot_url": f"https://beta.ensembl.org/species/{genome_id}",
                        }
            except Exception:
                continue
        return {}


__all__ = ["EnsemblGraphqlClient"]
