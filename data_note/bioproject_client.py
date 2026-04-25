from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

import requests

from . import assembly_version_checker
from .models import AssemblyCandidate

logger = logging.getLogger(__name__)

PORTAL_SEARCH_URL = "https://www.ebi.ac.uk/ena/portal/api/search"


@dataclass(slots=True)
class BioprojectClient:
    session_get: Callable[..., Any] | None = None
    revision_fetcher: Callable[[str], Any] | None = None

    def fetch_umbrella_project(self, bioproject_id: str) -> dict[str, Any] | None:
        data = self._search(
            result="study",
            query=f"study_accession={bioproject_id}",
            fields="study_accession,study_title,tax_id,study_description",
            error_message=f"Failed to get data for project {bioproject_id}",
        )
        if not data:
            logger.warning("No data found for project %s", bioproject_id)
            return None

        for study in data:
            if study.get("study_accession") == bioproject_id:
                return study
        return data[0]

    @staticmethod
    def build_umbrella_project_details(
        umbrella_data: dict[str, Any] | None,
        bioproject_id: str,
    ) -> dict[str, str]:
        umbrella_data = umbrella_data or {}
        return {
            "bioproject": bioproject_id,
            "study_title": umbrella_data.get(
                "study_title",
                umbrella_data.get("study_description", "No description available"),
            ),
            "tax_id": str(umbrella_data.get("tax_id", "")),
        }

    def fetch_child_accessions(self, umbrella_data: dict[str, Any] | None) -> list[str]:
        bioproject_id = (umbrella_data or {}).get("study_accession")
        if not bioproject_id:
            return []

        logger.info("Searching for child projects of %s...", bioproject_id)
        data = self._search(
            result="study",
            query=f"parent_study_accession={bioproject_id}",
            fields="study_accession,parent_study_accession,study_title",
            error_message=f"Failed to get child projects for {bioproject_id}",
        )
        if not data:
            return []

        child_projects: list[str] = []
        for study in data:
            parent_studies = study.get("parent_study_accession", "")
            if bioproject_id in parent_studies.split(";"):
                child_projects.append(study["study_accession"])

        logger.info("Found %s child projects for %s: %s", len(child_projects), bioproject_id, child_projects)
        return child_projects

    def fetch_and_update_assembly_details(self, bioproject: str) -> list[AssemblyCandidate] | None:
        logger.info("Fetching assemblies for bioproject: %s", bioproject)
        assemblies = self._search(
            result="assembly",
            query=f"study_accession={bioproject}",
            fields="accession,assembly_name,assembly_set_accession,tax_id,study_accession",
            error_message=f"Failed to get assemblies for project {bioproject}",
        )
        if assemblies is None:
            return None

        logger.info("Found %s assemblies for bioproject %s", len(assemblies), bioproject)
        if assemblies:
            logger.info("Assembly tax_ids found for %s: %s", bioproject, [asm.get("tax_id") for asm in assemblies])

        return [
            AssemblyCandidate.from_mapping(
                self._update_assembly_revision(
                    assembly,
                    accession_key="assembly_set_accession",
                    include_assembly_name=True,
                ),
                accession_key="assembly_set_accession",
            )
            for assembly in assemblies
        ]

    def fetch_assembly_details(self, bioproject: str) -> list[AssemblyCandidate] | None:
        assemblies = self._search(
            result="assembly",
            query=f"study_accession={bioproject}",
            fields="accession,assembly_name,assembly_set_accession,tax_id",
            error_message=f"Failed to get data for project {bioproject}",
        )
        if assemblies is None:
            return None

        return [
            AssemblyCandidate.from_mapping(
                self._update_assembly_revision(
                    assembly,
                    accession_key="accession",
                    include_assembly_name=False,
                ),
                accession_key="accession",
            )
            for assembly in assemblies
        ]

    def fetch_assemblies_for_bioprojects(self, bioproject_ids: list[str]) -> list[AssemblyCandidate]:
        return [
            assembly
            for bioproject_id in bioproject_ids
            for assembly in (self.fetch_and_update_assembly_details(bioproject_id) or [])
        ]

    def fetch_parent_projects(self, bioproject_id: str) -> dict[str, Any]:
        data = self._search(
            result="study",
            query=f"study_accession={bioproject_id}",
            fields="study_accession,parent_study_accession",
            error_message=f"Failed to get data for project {bioproject_id}",
        )
        if not data:
            return {}

        study_info = data[0]
        parent_studies = study_info.get("parent_study_accession", "")
        if not parent_studies:
            return {}

        parent_project_dict: dict[str, Any] = {}
        parent_projects: list[dict[str, str]] = []
        parent_accessions = [accession.strip() for accession in parent_studies.split(";") if accession.strip()]

        for index, parent_accession in enumerate(parent_accessions, start=1):
            parent_data = self._search(
                result="study",
                query=f"study_accession={parent_accession}",
                fields="study_accession,study_title,project_name",
                error_message=f"Failed to fetch parent project details for accession {parent_accession}",
            )
            if not parent_data:
                continue

            parent_info = parent_data[0]
            project_title = parent_info.get("study_title", "No title available")
            project_name = parent_info.get("project_name", project_title)
            best_name = project_name or project_title

            parent_projects.append(
                {
                    "accession": parent_accession,
                    "name": project_name if project_name else "No name available",
                    "title": project_title,
                    "project_name": best_name,
                }
            )
            parent_project_dict[f"parentproject{index}_accession"] = parent_accession
            parent_project_dict[f"parentproject{index}_project_name"] = best_name

        parent_project_dict["parent_projects"] = parent_projects
        return parent_project_dict

    def _search(
        self,
        *,
        result: str,
        query: str,
        fields: str,
        error_message: str,
    ) -> list[dict[str, Any]] | None:
        params = {
            "result": result,
            "query": query,
            "fields": fields,
            "format": "json",
        }
        getter = self.session_get or requests.get
        try:
            response = getter(PORTAL_SEARCH_URL, params=params)
        except Exception as exc:
            logger.warning("%s: %s", error_message, exc)
            return None

        if response.status_code != 200:
            logger.warning("%s (HTTP %s)", error_message, response.status_code)
            return None

        try:
            data = response.json()
        except ValueError:
            logger.warning("Invalid JSON response for %s query %s", result, query)
            return None

        if not isinstance(data, list):
            logger.warning("Unexpected ENA payload for %s query %s", result, query)
            return None
        return data

    def _update_assembly_revision(
        self,
        assembly: dict[str, Any],
        *,
        accession_key: str,
        include_assembly_name: bool,
    ) -> dict[str, Any]:
        updated = dict(assembly)
        current_accession = updated.get(accession_key)
        if not current_accession:
            return updated

        latest_accession, latest_assembly_name = self._resolve_latest_revision(current_accession)
        if latest_accession != current_accession:
            logger.info("Updated %s: %s -> %s", accession_key, current_accession, latest_accession)
            updated[accession_key] = latest_accession
        if include_assembly_name and latest_assembly_name:
            updated["assembly_name"] = latest_assembly_name
        return updated

    def _resolve_latest_revision(self, accession: str) -> tuple[str, str | None]:
        revision_fetcher = self.revision_fetcher or assembly_version_checker.get_latest_revision
        result = revision_fetcher(accession)
        if isinstance(result, tuple):
            latest_accession = result[0] if len(result) >= 1 and result[0] else accession
            latest_assembly_name = result[1] if len(result) >= 2 else None
            return latest_accession, latest_assembly_name
        if isinstance(result, str):
            return result, None
        return accession, None


EnaPortalClient = BioprojectClient


__all__ = ["BioprojectClient", "EnaPortalClient", "PORTAL_SEARCH_URL"]
