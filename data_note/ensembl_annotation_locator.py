from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable

import requests

from .ensembl_endpoint_config import EnsemblEndpointConfig


@dataclass(slots=True)
class EnsemblAnnotationLocation:
    annotation_file_url: str
    method: str
    source: str
    resolved_assembly: str


@dataclass(slots=True)
class EnsemblAnnotationLocator:
    config: EnsemblEndpointConfig = field(default_factory=EnsemblEndpointConfig.from_env)
    request_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def locate(self, assembly: str, species: str) -> EnsemblAnnotationLocation | None:
        organisms_result = self.search_ensembl_organisms(assembly, species)
        if organisms_result is not None:
            return organisms_result
        return self.search_ensembl_main(assembly, species)

    def search_ensembl_organisms(self, assembly: str, species: str) -> EnsemblAnnotationLocation | None:
        for variant in self.get_species_variants(species):
            base_url = f"{self.config.organisms_base}{variant}/{assembly}/"
            for method, method_name in (("braker", "BRAKER"), ("ensembl", "Ensembl Genebuild")):
                test_url = f"{base_url}{method}/geneset/"
                self.config.debug_print(f"Testing {method_name}: {test_url}")
                response = self.request_get(test_url, headers=self.config.headers, timeout=self.timeout)
                if response.status_code != 200:
                    continue

                self.config.debug_print(f"Found {method_name} geneset directory")
                dirs = re.findall(r'href="(\d{4}_\d{2})/"', response.text)
                if not dirs:
                    continue

                latest = sorted(dirs)[-1]
                final_url = f"{test_url}{latest}/"
                self.config.debug_print(f"Trying version {latest}: {final_url}")
                annotation_file_url = self.find_annotation_file(final_url)
                if annotation_file_url:
                    return EnsemblAnnotationLocation(
                        annotation_file_url=annotation_file_url,
                        method=method_name,
                        source="ensembl_organisms",
                        resolved_assembly=self.extract_assembly_from_url(annotation_file_url) or assembly,
                    )
        return None

    def search_ensembl_main(self, assembly: str, species: str) -> EnsemblAnnotationLocation | None:
        self.config.debug_print(f"Searching main Ensembl for {species}")
        for base_url in (self.config.main_gtf_base, self.config.main_gff3_base):
            for variant in self.get_species_variants(species):
                species_url = f"{base_url}{variant}/"
                html = self.http_text(species_url)
                if not html:
                    continue
                latest_version = self.find_latest_version_dir(species_url)
                if not latest_version:
                    continue
                annotation_url = self.find_annotation_file(f"{species_url}{latest_version}/")
                if annotation_url:
                    return EnsemblAnnotationLocation(
                        annotation_file_url=annotation_url,
                        method="Ensembl Genebuild",
                        source="ensembl_main",
                        resolved_assembly=self.extract_assembly_from_url(annotation_url) or assembly,
                    )
        return None

    def http_text(self, url: str) -> str | None:
        try:
            self.config.debug_print(f"Fetching: {url}")
            response = self.request_get(url, timeout=self.timeout, headers=self.config.headers)
            if response.status_code == 200:
                return response.text
            self.config.debug_print(f"HTTP {response.status_code} for {url}")
            return None
        except requests.RequestException as exc:
            self.config.debug_print(f"Request failed for {url}: {exc}")
            return None

    def find_latest_version_dir(self, base_url: str) -> str | None:
        html = self.http_text(base_url)
        if not html:
            return None

        date_dirs = re.findall(r'href="(\d{4}_\d{2})/"', html)
        if date_dirs:
            latest = sorted(date_dirs)[-1]
            self.config.debug_print(f"Found latest version: {latest}")
            return latest

        numbered_dirs = re.findall(r'href="(\d+)/"', html)
        if numbered_dirs:
            latest = sorted(numbered_dirs, key=int)[-1]
            self.config.debug_print(f"Found latest numbered version: {latest}")
            return latest

        return None

    def find_annotation_file(self, dir_url: str) -> str | None:
        html = self.http_text(dir_url)
        if not html:
            return None

        files = re.findall(r'href="([^"]+\.(gtf|gff3?)(\.gz)?)"', html, re.IGNORECASE)
        if not files:
            self.config.debug_print(f"No annotation files in {dir_url}")
            return None

        self.config.debug_print(f"Found files: {[file_info[0] for file_info in files]}")
        for pattern in (r"genes\.gtf", r"genes\.gff3?", r"\.gtf", r"\.gff3?"):
            for file_info in files:
                filename = file_info[0]
                if re.search(pattern, filename, re.IGNORECASE):
                    return dir_url + filename
        return None

    @staticmethod
    def get_species_variants(species: str) -> list[str]:
        parts = species.strip().split()
        if len(parts) >= 2:
            genus, specific = parts[0], parts[1]
            return [
                f"{genus.capitalize()}_{specific.lower()}",
                f"{genus.lower()}_{specific.lower()}",
            ]
        return [species.replace(" ", "_")]

    @staticmethod
    def extract_assembly_from_url(url: str) -> str | None:
        match = re.search(r"(GC[AF]_\d+\.\d+)", url)
        return match.group(1) if match else None


__all__ = ["EnsemblAnnotationLocation", "EnsemblAnnotationLocator"]
