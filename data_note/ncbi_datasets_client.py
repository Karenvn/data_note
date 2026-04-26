from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

from Bio import Entrez
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .formatting_utils import format_with_nbsp

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
)
def safe_ncbi_request(
    url: str,
    headers: dict[str, str],
    *,
    request_get: Callable[..., Any] = requests.get,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
):
    response = request_get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code in RETRY_STATUS_CODES:
        logger.warning("Retryable HTTP error %s, will retry...", response.status_code)
        raise requests.exceptions.RequestException(f"Status: {response.status_code}")
    response.raise_for_status()
    return response


@dataclass(slots=True)
class NcbiDatasetsClient:
    request_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def fetch_primary_assembly_info(self, accession: str) -> dict[str, Any] | None:
        report = self.fetch_dataset_report(accession)
        if report is None:
            return None
        return self.parse_assembly_report(report)

    def fetch_haplotype_assembly_info(self, hap1_accession: str, hap2_accession: str) -> dict[str, Any]:
        hap1_info = self.fetch_primary_assembly_info(hap1_accession) or {}
        hap2_info = self.fetch_primary_assembly_info(hap2_accession) or {}

        combined_info: dict[str, Any] = {}
        for key, value in hap1_info.items():
            combined_info[f"hap1_{key}"] = value
        for key, value in hap2_info.items():
            combined_info[f"hap2_{key}"] = value

        combined_info["tolid"] = hap1_info.get("tolid", "N/A")
        combined_info["wgs_project_accession"] = hap1_info.get("wgs_project_accession", "N/A")
        return combined_info

    def fetch_dataset_report(self, accession: str) -> dict[str, Any] | None:
        api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/dataset_report"
        response = safe_ncbi_request(
            api_url,
            self._headers(),
            request_get=self.request_get,
            params=self.get_datasets_params(),
            timeout=self.timeout,
        )
        data = response.json()
        reports = data.get("reports", []) if data else []
        if not reports:
            logger.warning("No valid report data found for %s", accession)
            return None
        return reports[0]

    def fetch_taxon_reports(self, taxid: int | str, *, page_size: int = 1000) -> list[dict[str, Any]]:
        api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report"
        response = safe_ncbi_request(
            api_url,
            self._headers(),
            request_get=self.request_get,
            params={"page_size": page_size, **self.get_datasets_params()},
            timeout=max(self.timeout, 60),
        )
        data = response.json() or {}
        return data.get("reports", [])

    @staticmethod
    def parse_assembly_report(report: dict[str, Any]) -> dict[str, Any]:
        parsed_assembly_data: dict[str, Any] = {}
        try:
            assembly_stats = report["assembly_stats"]
            assembly_info = report["assembly_info"]
            parsed_assembly_data["assembly_level"] = str(assembly_info["assembly_level"]).lower()
            parsed_assembly_data["total_length"] = format_with_nbsp(
                round(float(assembly_stats.get("total_sequence_length", 0)) / 1e6, 2)
            )
            parsed_assembly_data["num_contigs"] = format_with_nbsp(
                int(assembly_stats.get("number_of_contigs", 0)),
                as_int=True,
            )
            parsed_assembly_data["contig_N50"] = round(float(assembly_stats.get("contig_n50", 0)) / 1e6, 2)
            parsed_assembly_data["num_scaffolds"] = format_with_nbsp(
                int(assembly_stats.get("number_of_scaffolds", 0)),
                as_int=True,
            )
            parsed_assembly_data["scaffold_N50"] = round(float(assembly_stats.get("scaffold_n50", 0)) / 1e6, 2)
            parsed_assembly_data["chromosome_count"] = int(assembly_stats.get("total_number_of_chromosomes", 0))
            parsed_assembly_data["genome_length_unrounded"] = float(
                assembly_stats.get("total_sequence_length", 0)
            )
            parsed_assembly_data["coverage"] = assembly_stats.get("genome_coverage")
        except KeyError as exc:
            logger.warning("Missing key in response data for assembly report: %s", exc)

        biosample = report.get("assembly_info", {}).get("biosample", {})
        for attribute in biosample.get("attributes", []) or []:
            if attribute.get("name") == "tolid":
                parsed_assembly_data["tolid"] = attribute.get("value")
                break

        wgs_info = report.get("wgs_info", {})
        parsed_assembly_data["wgs_project_accession"] = wgs_info.get("wgs_project_accession", "N/A")
        parsed_assembly_data["linked_assemblies"] = NcbiDatasetsClient.extract_linked_assemblies(report)
        return parsed_assembly_data

    @staticmethod
    def extract_linked_assemblies(report: dict[str, Any]) -> list[str]:
        linked = []
        for item in report.get("assembly_info", {}).get("linked_assemblies", []) or []:
            accession = item.get("linked_assembly")
            if accession:
                linked.append(str(accession))
        return linked

    @staticmethod
    def get_datasets_params() -> dict[str, str]:
        api_key = Entrez.api_key
        if api_key and api_key != "default_api_key":
            return {"api_key": api_key}
        return {}

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "accept": "application/json",
            "User-Agent": f"Python script; {Entrez.email}",
        }


__all__ = [
    "NcbiDatasetsClient",
    "RETRY_STATUS_CODES",
    "safe_ncbi_request",
]
