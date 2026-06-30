#!/usr/bin/env python

from __future__ import annotations

import logging
import os
from pathlib import Path
from datetime import timezone
from collections.abc import Mapping
from typing import Any, Iterable

from dateutil.parser import parse as parse_date
import yaml

from .local_metadata import LocalMetadataProvider, NullLocalMetadataProvider

try:
    from tol.core import DataSourceFilter
    from tol.sources.portal import portal
except ImportError:
    DataSourceFilter = None
    portal = None


_CURATION_TOLID_FILTERS = ("grit_tolid.id", "tolid.id")
_COMPLETE_STATUSES = {"complete", "completed", "done"}
_REJECTED_STATUSES = {"cancelled", "canceled", "failed", "rejected"}

logger = logging.getLogger(__name__)


def _derive_tolid(tolid: str | None, assembly_name: str | None) -> str | None:
    if tolid:
        return str(tolid).strip() or None
    if assembly_name:
        return str(assembly_name).strip().split(".", 1)[0] or None
    return None


def _best_effort_datetime(value):
    if value in (None, "", "None"):
        return None
    try:
        return parse_date(str(value))
    except Exception:
        return None


def _sort_key(curation_obj):
    attrs = curation_obj.attributes or {}
    status = str(attrs.get("grit_status") or attrs.get("status") or "").strip().casefold()
    if status in _COMPLETE_STATUSES:
        status_rank = 2
    elif status in _REJECTED_STATUSES:
        status_rank = 0
    else:
        status_rank = 1

    done_date = _best_effort_datetime(attrs.get("done_date") or attrs.get("grit_done_date"))
    created = _best_effort_datetime(attrs.get("created") or attrs.get("grit_created"))
    return (status_rank, _datetime_rank(done_date or created))


def _datetime_rank(value):
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


class PortalCurationMetadataProvider:
    def __init__(self, retries: int = 1) -> None:
        self.retries = retries

    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        if portal is None or DataSourceFilter is None:
            return None

        resolved_tolid = _derive_tolid(tolid, assembly_name)
        if not resolved_tolid:
            return None

        try:
            ds = portal(retries=self.retries)
        except Exception as exc:
            logger.warning("Portal curation lookup unavailable for %s: %s", resolved_tolid, exc)
            return None

        for filter_name in _CURATION_TOLID_FILTERS:
            try:
                f = DataSourceFilter()
                f.and_ = {
                    filter_name: {
                        "eq": {"value": resolved_tolid, "negate": False}
                    }
                }
                curations = list(ds.get_list("curation", object_filters=f))
            except Exception:
                continue

            jira_ticket = self._select_identifier(curations)
            if jira_ticket:
                return jira_ticket

        return None

    def lookup_project_provenance(
        self,
        bioproject: str,
        *,
        tolid: str | None = None,
        species: str | None = None,
    ) -> Mapping[str, Any] | None:
        # The portal should ultimately be the source of truth for this. Until the
        # relevant object/attribute is stable, keep the method explicit and let
        # file-backed metadata supply the structured values.
        return None

    @staticmethod
    def _select_identifier(curations: Iterable) -> str | None:
        candidates = []
        for obj in curations:
            identifier = getattr(obj, "id", None) or (obj.attributes or {}).get("identifier")
            if identifier:
                candidates.append(obj)

        if not candidates:
            return None

        selected = sorted(candidates, key=_sort_key, reverse=True)[0]
        return getattr(selected, "id", None) or (selected.attributes or {}).get("identifier")


class FileProjectProvenanceMetadataProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._data: Mapping[str, Any] | None = None

    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        return None

    def lookup_project_provenance(
        self,
        bioproject: str,
        *,
        tolid: str | None = None,
        species: str | None = None,
    ) -> Mapping[str, Any] | None:
        data = self._load()
        for scope, value in (
            ("bioproject", bioproject),
            ("tolid", tolid),
            ("species", species),
        ):
            if not value:
                continue
            scoped = data.get(scope)
            if isinstance(scoped, Mapping):
                match = scoped.get(value)
                if isinstance(match, Mapping):
                    return match
        return None

    def _load(self) -> Mapping[str, Any]:
        if self._data is not None:
            return self._data
        if not self.path.is_file():
            self._data = {}
            return self._data
        with self.path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        if not isinstance(payload, Mapping):
            logger.warning("Ignoring project provenance file %s: top-level value is not a mapping", self.path)
            payload = {}
        self._data = payload
        return self._data


def _project_provenance_path_from_env() -> Path | None:
    explicit = os.getenv("DATA_NOTE_PROJECT_PROVENANCE_FILE")
    if explicit:
        return Path(explicit).expanduser()

    assets_root = os.getenv("DATA_NOTE_GN_ASSETS") or os.getenv("DATA_NOTE_SERVER_DATA")
    if not assets_root:
        return None

    root = Path(assets_root).expanduser()
    for filename in ("project_provenance.yaml", "project_provenance.yml", "project_provenance.json"):
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None


def get_local_metadata_provider() -> LocalMetadataProvider:
    providers: list[LocalMetadataProvider] = []
    provenance_path = _project_provenance_path_from_env()
    if provenance_path is not None:
        providers.append(FileProjectProvenanceMetadataProvider(provenance_path))

    if portal is not None and DataSourceFilter is not None:
        providers.append(PortalCurationMetadataProvider())

    if not providers:
        return NullLocalMetadataProvider()
    if len(providers) == 1:
        return providers[0]
    return CompositeLocalMetadataProvider(providers)


class CompositeLocalMetadataProvider:
    def __init__(self, providers: list[LocalMetadataProvider]) -> None:
        self.providers = providers

    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        for provider in self.providers:
            jira_ticket = provider.lookup_jira_ticket(
                accession,
                tolid=tolid,
                assembly_name=assembly_name,
            )
            if jira_ticket:
                return jira_ticket
        return None

    def lookup_project_provenance(
        self,
        bioproject: str,
        *,
        tolid: str | None = None,
        species: str | None = None,
    ) -> Mapping[str, Any] | None:
        for provider in self.providers:
            provenance = provider.lookup_project_provenance(
                bioproject,
                tolid=tolid,
                species=species,
            )
            if provenance:
                return provenance
        return None
