from __future__ import annotations

import csv
import io
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
import requests

logger = logging.getLogger(__name__)


READ_RUN_FIELDS = (
    "run_accession,run_alias,experiment_accession,experiment_alias,experiment_title,"
    "sample_accession,sample_alias,submitted_bytes,read_count,base_count,"
    "library_strategy,library_layout,library_name,library_construction_protocol,"
    "library_source,library_selection,nominal_length,nominal_sdev,"
    "instrument_platform,instrument_model,study_accession,secondary_study_accession,"
    "submitted_ftp,fastq_ftp"
)

ASSEMBLY_RUN_FIELDS = (
    "assembly_set_accession,assembly_accession,accession,assembly_name,run_accession"
)

ENA_AUGMENT_FIELDS = (
    "run_alias",
    "experiment_accession",
    "experiment_alias",
    "experiment_title",
    "sample_alias",
    "library_source",
    "library_selection",
    "nominal_length",
    "nominal_sdev",
    "submitted_ftp",
    "fastq_ftp",
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


@dataclass(slots=True)
class SequencingFetchResult:
    dataframe: pd.DataFrame
    source_accessions: list[str]


@dataclass(slots=True)
class SequencingFetchService:
    session_get: Callable[..., Any] = requests.get

    def fetch_rows_for_accession(self, accession: str) -> list[dict[str, Any]]:
        accession_rows = self.fetch_runinfo_rows_for_accession(accession)
        if accession_rows:
            ena_rows = self.fetch_read_runs_for_bioproject(accession)
            return self._augment_rows_from_ena(accession_rows, ena_rows)

        logger.debug("No SRA RunInfo rows found for %s; trying NCBI E-utilities summary.", accession)
        accession_rows = self.fetch_sra_summary_rows_for_accession(accession)
        if accession_rows:
            ena_rows = self.fetch_read_runs_for_bioproject(accession)
            return self._augment_rows_from_ena(accession_rows, ena_rows)

        logger.debug("No SRA summary rows found for %s; falling back to ENA filereport.", accession)
        accession_rows = self.fetch_read_runs_for_bioproject(accession)
        if accession_rows:
            return accession_rows

        logger.debug(
            "No read-run metadata found for %s across SRA RunInfo, NCBI E-utilities, or ENA filereport.",
            accession,
        )
        return []

    def fetch_read_runs_for_bioproject(self, bioproject: str) -> list[dict[str, Any]]:
        url = "https://www.ebi.ac.uk/ena/portal/api/filereport"
        params = {
            "accession": bioproject,
            "result": "read_run",
            "fields": READ_RUN_FIELDS,
            "format": "tsv",
            "limit": 0,
            "dataPortal": "ena",
        }
        try:
            response = self.session_get(url, params=params, timeout=30)
            if response.status_code != 200:
                logger.warning("ENA filereport failed for %s: HTTP %s", bioproject, response.status_code)
                return []
            if not response.text.strip():
                return []
            lines = response.text.strip().splitlines()
            if len(lines) < 2:
                return []
            rows = list(csv.DictReader(io.StringIO(response.text), delimiter="\t"))
            for row in rows:
                row.setdefault("metadata_source", "ena")
                row.setdefault("read_count_basis", "reads")
            return rows
        except Exception as exc:
            logger.warning("ENA filereport request failed for %s: %s", bioproject, exc)
            return []

    def fetch_runinfo_rows_for_accession(self, accession: str) -> list[dict[str, Any]]:
        url = "https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/runinfo"
        experiment_protocol_cache: dict[str, str] = {}
        try:
            response = self.session_get(url, params={"acc": accession}, timeout=30)
            if response.status_code != 200 or not response.text.strip():
                return []
            reader = csv.DictReader(io.StringIO(response.text))
            rows: list[dict[str, Any]] = []
            for row in reader:
                experiment_accession = row.get("Experiment", "")
                library_protocol = ""
                if experiment_accession:
                    if experiment_accession in experiment_protocol_cache:
                        library_protocol = experiment_protocol_cache[experiment_accession]
                    else:
                        library_protocol = self.fetch_experiment_protocol(experiment_accession)
                        experiment_protocol_cache[experiment_accession] = library_protocol
                size_mb = _safe_float(row.get("size_MB"), 0.0)
                rows.append(
                    {
                        "run_accession": row.get("Run", ""),
                        "sample_accession": row.get("BioSample", "") or row.get("Sample", ""),
                        "submitted_bytes": int(size_mb * 1_000_000),
                        "read_count": _safe_int(row.get("spots"), 0),
                        "base_count": _safe_int(row.get("bases"), 0),
                        "library_strategy": row.get("LibraryStrategy", ""),
                        "library_layout": row.get("LibraryLayout", ""),
                        "library_name": row.get("LibraryName", ""),
                        "library_construction_protocol": library_protocol,
                        "instrument_platform": row.get("Platform", ""),
                        "instrument_model": row.get("Model", ""),
                        "study_accession": row.get("BioProject", "") or accession,
                        "secondary_study_accession": row.get("SRAStudy", ""),
                        "submitted_ftp": "",
                        "fastq_ftp": "",
                        "metadata_source": "ncbi_runinfo",
                        "read_count_basis": "spots",
                    }
                )
            return rows
        except Exception as exc:
            logger.warning("SRA RunInfo request failed for %s: %s", accession, exc)
            return []

    def fetch_sra_summary_rows_for_accession(self, accession: str) -> list[dict[str, Any]]:
        esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        search_terms = [f"{accession}[BioProject]", accession]

        for term in search_terms:
            try:
                search_response = self.session_get(
                    esearch_url,
                    params=self._ncbi_eutils_params(
                        {
                            "db": "sra",
                            "term": term,
                            "retmode": "json",
                            "retmax": 500,
                        }
                    ),
                    timeout=30,
                )
                if search_response.status_code != 200:
                    continue

                search_data = search_response.json()
                id_list = search_data.get("esearchresult", {}).get("idlist", [])
                if not id_list:
                    continue

                summary_response = self.session_get(
                    esummary_url,
                    params=self._ncbi_eutils_params(
                        {
                            "db": "sra",
                            "id": ",".join(id_list),
                            "retmode": "json",
                        }
                    ),
                    timeout=30,
                )
                if summary_response.status_code != 200:
                    continue

                summary_data = summary_response.json().get("result", {})
                rows: list[dict[str, Any]] = []
                for uid in summary_data.get("uids", []):
                    rows.extend(self._parse_sra_summary_result(summary_data.get(uid, {})))
                if rows:
                    return rows
            except Exception as exc:
                logger.warning("SRA E-utilities request failed for %s (%s): %s", accession, term, exc)

        return []

    def fetch_for_bioprojects_with_sources(self, bioprojects: list[str]) -> SequencingFetchResult:
        rows: list[dict[str, Any]] = []
        source_accessions: list[str] = []
        for accession in bioprojects:
            accession_rows = self.fetch_rows_for_accession(accession)
            if accession_rows:
                source_accessions.append(accession)
            rows.extend(accession_rows)

        if not rows:
            logger.info(
                "No read-run metadata found across BioProjects: %s.",
                ", ".join(bioprojects),
            )
            return SequencingFetchResult(dataframe=pd.DataFrame(), source_accessions=[])

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            run_accession = row.get("run_accession")
            if run_accession and run_accession in seen:
                continue
            if run_accession:
                seen.add(run_accession)
            deduped.append(row)
        return SequencingFetchResult(
            dataframe=pd.DataFrame(deduped),
            source_accessions=source_accessions,
        )

    def fetch_for_bioprojects(self, bioprojects: list[str]) -> pd.DataFrame:
        return self.fetch_for_bioprojects_with_sources(bioprojects).dataframe

    def fetch_assembly_run_accessions(self, assembly_accessions: list[str]) -> set[str]:
        run_accessions: set[str] = set()
        for accession in assembly_accessions:
            normalised = str(accession or "").strip()
            if not normalised:
                continue
            for query in self._assembly_queries(normalised):
                rows = self._fetch_assembly_rows(query)
                if not rows:
                    continue
                for row in rows:
                    run_accessions.update(self._split_accessions(row.get("run_accession")))
                break
        return run_accessions

    @staticmethod
    def _augment_rows_from_ena(
        primary_rows: list[dict[str, Any]],
        ena_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not primary_rows or not ena_rows:
            return primary_rows

        ena_by_run = {
            row.get("run_accession"): row
            for row in ena_rows
            if row.get("run_accession")
        }
        augmented: list[dict[str, Any]] = []
        seen_runs: set[str] = set()

        for row in primary_rows:
            merged = dict(row)
            run_accession = merged.get("run_accession")
            if run_accession:
                seen_runs.add(run_accession)
            ena_row = ena_by_run.get(run_accession)
            if ena_row:
                for field_name in ENA_AUGMENT_FIELDS:
                    if not merged.get(field_name) and ena_row.get(field_name):
                        merged[field_name] = ena_row[field_name]
                merged["supplementary_metadata_source"] = "ena"
            augmented.append(merged)

        for ena_row in ena_rows:
            run_accession = ena_row.get("run_accession")
            if run_accession and run_accession in seen_runs:
                continue
            augmented.append(ena_row)

        return augmented

    def fetch_experiment_protocol(self, experiment_accession: str) -> str:
        url = "https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/exp"
        try:
            response = self.session_get(url, params={"acc": experiment_accession}, timeout=30)
            if response.status_code != 200 or not response.text.strip():
                return ""
            try:
                root = ET.fromstring(response.text)
            except ET.ParseError:
                return ""
            element = root.find(".//LIBRARY_CONSTRUCTION_PROTOCOL")
            if element is not None and element.text:
                return element.text.strip()
        except Exception as exc:
            logger.warning("Experiment protocol fetch failed for %s: %s", experiment_accession, exc)
        return ""

    def _fetch_assembly_rows(self, query: str) -> list[dict[str, Any]]:
        url = "https://www.ebi.ac.uk/ena/portal/api/search"
        try:
            response = self.session_get(
                url,
                params={
                    "result": "assembly",
                    "query": query,
                    "fields": ASSEMBLY_RUN_FIELDS,
                    "format": "json",
                },
                timeout=30,
            )
            if response.status_code != 200:
                logger.warning("ENA assembly lookup failed for %s: HTTP %s", query, response.status_code)
                return []
            data = response.json()
            if isinstance(data, list):
                return data
        except Exception as exc:
            logger.warning("ENA assembly lookup failed for %s: %s", query, exc)
        return []

    @staticmethod
    def _assembly_queries(accession: str) -> tuple[str, ...]:
        base_accession = accession.split(".", 1)[0]
        return (
            f'assembly_set_accession="{accession}"',
            f'accession="{base_accession}"',
        )

    @staticmethod
    def _split_accessions(value: Any) -> set[str]:
        text = str(value or "")
        return {
            part.strip()
            for part in text.split(";")
            if part.strip()
        }

    @staticmethod
    def _ncbi_eutils_params(params: dict[str, Any] | None = None) -> dict[str, Any]:
        merged = dict(params or {})
        api_key = os.getenv("ENTREZ_API_KEY")
        if api_key:
            merged["api_key"] = api_key
        return merged

    @staticmethod
    def _parse_sra_summary_result(summary: dict[str, Any]) -> list[dict[str, Any]]:
        expxml = summary.get("expxml", "")
        runs_xml = summary.get("runs", "")
        if not expxml or not runs_xml:
            return []

        try:
            exp_root = ET.fromstring(f"<root>{expxml}</root>")
            runs_root = ET.fromstring(f"<root>{runs_xml}</root>")
        except ET.ParseError:
            return []

        platform_element = exp_root.find(".//Platform")
        statistics_element = exp_root.find(".//Statistics")
        study_element = exp_root.find(".//Study")

        instrument_platform = (
            (platform_element.text or "").strip()
            if platform_element is not None and platform_element.text
            else ""
        )
        instrument_model = platform_element.get("instrument_model", "") if platform_element is not None else ""

        library_strategy_element = exp_root.find(".//LIBRARY_STRATEGY")
        library_layout_element = exp_root.find(".//LIBRARY_LAYOUT")
        library_name_element = exp_root.find(".//LIBRARY_NAME")
        library_protocol_element = exp_root.find(".//LIBRARY_CONSTRUCTION_PROTOCOL")
        biosample_element = exp_root.find(".//Biosample")
        bioproject_element = exp_root.find(".//Bioproject")

        read_count = _safe_int(statistics_element.get("total_spots") if statistics_element is not None else None, 0)
        base_count = _safe_int(statistics_element.get("total_bases") if statistics_element is not None else None, 0)
        submitted_bytes = _safe_int(
            statistics_element.get("total_size") if statistics_element is not None else None,
            0,
        )

        rows: list[dict[str, Any]] = []
        for run_element in runs_root.findall(".//Run"):
            rows.append(
                {
                    "run_accession": run_element.get("acc", ""),
                    "sample_accession": (
                        biosample_element.text.strip()
                        if biosample_element is not None and biosample_element.text
                        else ""
                    ),
                    "submitted_bytes": submitted_bytes,
                    "read_count": _safe_int(run_element.get("total_spots"), read_count),
                    "base_count": _safe_int(run_element.get("total_bases"), base_count),
                    "library_strategy": (
                        library_strategy_element.text.strip()
                        if library_strategy_element is not None and library_strategy_element.text
                        else ""
                    ),
                    "library_layout": (
                        library_layout_element.text.strip()
                        if library_layout_element is not None and library_layout_element.text
                        else ""
                    ),
                    "library_name": (
                        library_name_element.text.strip()
                        if library_name_element is not None and library_name_element.text
                        else ""
                    ),
                    "library_construction_protocol": (
                        library_protocol_element.text.strip()
                        if library_protocol_element is not None and library_protocol_element.text
                        else ""
                    ),
                    "instrument_platform": instrument_platform,
                    "instrument_model": instrument_model,
                    "study_accession": (
                        bioproject_element.text.strip()
                        if bioproject_element is not None and bioproject_element.text
                        else ""
                    ),
                    "secondary_study_accession": study_element.get("acc", "") if study_element is not None else "",
                    "submitted_ftp": "",
                    "fastq_ftp": "",
                    "metadata_source": "ncbi_sra_summary",
                    "read_count_basis": "spots",
                }
            )

        return rows


DEFAULT_SEQUENCING_FETCH_SERVICE = SequencingFetchService()
