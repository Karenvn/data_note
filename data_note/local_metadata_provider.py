#!/usr/bin/env python

from __future__ import annotations

import logging
from datetime import timezone
from typing import Iterable

from dateutil.parser import parse as parse_date

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


def get_local_metadata_provider() -> LocalMetadataProvider:
    providers: list[LocalMetadataProvider] = []
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
