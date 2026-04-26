from __future__ import annotations

from dataclasses import dataclass, field
import os
import tempfile
from typing import Any, Callable

import requests

from .ensembl_annotation_locator import EnsemblAnnotationLocator
from .ensembl_graphql_client import EnsemblGraphqlClient
from .gtf_stats_parser import GtfStatsParser


@dataclass(slots=True)
class EnsemblAnnotationFetcher:
    locator: EnsemblAnnotationLocator = field(default_factory=EnsemblAnnotationLocator)
    graphql_client: EnsemblGraphqlClient = field(default_factory=EnsemblGraphqlClient)
    parser: GtfStatsParser = field(default_factory=GtfStatsParser)
    request_get: Callable[..., Any] = requests.get
    download_timeout: int = 120

    def fetch_annotation(
        self,
        assembly: str,
        species: str,
        tax_id: str | int | None,
    ) -> dict[str, Any]:
        assembly = assembly.strip().rstrip("/")
        species = species.strip()
        self.locator.config.debug_print(f"Starting search for {species} ({assembly})")

        location = self.locator.locate(assembly, species)
        if location is None:
            self.locator.config.debug_print(f"No annotation found for {species} ({assembly})")
            return {}

        self.locator.config.debug_print(
            f"SUCCESS: Found annotation at {location.annotation_file_url} using {location.method}"
        )

        beta_metadata: dict[str, str] = {}
        if tax_id:
            self.locator.config.debug_print(f"Fetching beta metadata for tax_id: {tax_id}")
            beta_metadata = self.graphql_client.fetch_beta_metadata(tax_id, location.resolved_assembly)
            if beta_metadata:
                self.locator.config.debug_print(f"Got beta metadata: {beta_metadata['annot_url']}")

        reader_annotation_url = beta_metadata.get("annot_url", location.annotation_file_url)
        return self._download_and_parse(
            annotation_file_url=location.annotation_file_url,
            reader_annotation_url=reader_annotation_url,
            resolved_assembly=location.resolved_assembly,
            species=species,
            source=location.source,
            method=location.method,
            beta_metadata=beta_metadata,
        )

    def _download_and_parse(
        self,
        *,
        annotation_file_url: str,
        reader_annotation_url: str,
        resolved_assembly: str,
        species: str,
        source: str,
        method: str,
        beta_metadata: dict[str, str],
    ) -> dict[str, Any]:
        try:
            self.locator.config.debug_print("Downloading and processing GTF file...")
            with tempfile.TemporaryDirectory() as tempdirname:
                local_name = os.path.basename(annotation_file_url.rstrip("/")) or "annotation.gtf.gz"
                annotation_path = os.path.join(tempdirname, local_name)

                response = self.request_get(annotation_file_url, timeout=self.download_timeout)
                if response.status_code == 200:
                    with open(annotation_path, "wb") as handle:
                        handle.write(response.content)

                    result = self.parser.parse(annotation_path)
                    result.update(
                        self._base_metadata(
                            reader_annotation_url=reader_annotation_url,
                            annotation_file_url=annotation_file_url,
                            source=source,
                            species=species,
                            method=method,
                        )
                    )
                    self._apply_template_compatibility_fields(result, beta_metadata, reader_annotation_url, resolved_assembly)
                    self.locator.config.debug_print("GTF processing completed successfully")
                    return result

                result = self._base_metadata(
                    reader_annotation_url=reader_annotation_url,
                    annotation_file_url=annotation_file_url,
                    source=source,
                    species=species,
                    method=method,
                )
                result["download_error"] = f"HTTP {response.status_code}"
                self._apply_template_compatibility_fields(result, beta_metadata, reader_annotation_url, resolved_assembly)
                return result
        except Exception as exc:
            self.locator.config.debug_print(f"Error processing GTF file: {exc}")
            result = self._base_metadata(
                reader_annotation_url=reader_annotation_url,
                annotation_file_url=annotation_file_url,
                source=source,
                species=species,
                method=method,
            )
            result["processing_error"] = str(exc)
            self._apply_template_compatibility_fields(result, beta_metadata, reader_annotation_url, resolved_assembly)
            return result

    @staticmethod
    def _base_metadata(
        *,
        reader_annotation_url: str,
        annotation_file_url: str,
        source: str,
        species: str,
        method: str,
    ) -> dict[str, Any]:
        return {
            "ensembl_annotation_url": reader_annotation_url,
            "ensembl_annotation_file_url": annotation_file_url,
            "ensembl_source": source,
            "ensembl_species": species,
            "ensembl_search_strategy": (
                "Ensembl Organisms" if source == "ensembl_organisms" else "Ensembl Main Site"
            ),
            "annot_method": method,
        }

    @staticmethod
    def _apply_template_compatibility_fields(
        result: dict[str, Any],
        beta_metadata: dict[str, str],
        reader_annotation_url: str,
        resolved_assembly: str,
    ) -> None:
        if beta_metadata:
            result["annot_url"] = beta_metadata["annot_url"]
            result["annot_accession"] = beta_metadata["annot_accession"]
            result["source"] = "beta"
            return

        result["annot_url"] = reader_annotation_url
        result["annot_accession"] = resolved_assembly
        result["source"] = "ensembl_ftp"


__all__ = ["EnsemblAnnotationFetcher"]
