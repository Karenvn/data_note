#!/usr/bin/env python

from __future__ import annotations

import os
from typing import Iterable

import pandas as pd
from dateutil.parser import parse as parse_date

from .local_metadata import LocalMetadataProvider, NullLocalMetadataProvider

try:
    from tol.core import DataSourceFilter
    from tol.sources.portal import portal
except ImportError:
    DataSourceFilter = None
    portal = None


DATA_NOTE_TOLA_TSV_URL = "DATA_NOTE_TOLA_TSV_URL"
_MISSING_JIRA_VALUES = {"", "N/A", "nan", "None"}
_CURATION_TOLID_FILTERS = ("grit_tolid.id", "tolid.id")


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
    done_date = _best_effort_datetime(attrs.get("done_date"))
    created = _best_effort_datetime(attrs.get("created"))
    done_rank = 1 if done_date is None else 0
    return (done_rank, created or done_date or 0)


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
            print(f"Portal curation lookup unavailable for {resolved_tolid}: {exc}")
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


class ToLASpreadsheetMetadataProvider:
    def __init__(self, spreadsheet_url: str) -> None:
        self.spreadsheet_url = spreadsheet_url

    def lookup_jira_ticket(
        self,
        accession: str,
        *,
        tolid: str | None = None,
        assembly_name: str | None = None,
    ) -> str | None:
        if not accession:
            return None

        try:
            info_df = pd.read_csv(
                self.spreadsheet_url,
                sep="\t",
                usecols=["jira", "accession"],
                low_memory=False,
            )
        except Exception as exc:
            print(f"Local ToLA lookup unavailable for {accession}: {exc}")
            return None

        info_df.columns = ["jira", "accession"]
        rows = info_df.loc[info_df["accession"] == accession, "jira"]
        if rows.empty:
            return None

        jira_values = rows.fillna("").astype(str).str.strip()
        for jira_ticket in jira_values:
            if jira_ticket not in _MISSING_JIRA_VALUES:
                return jira_ticket
        return None


def get_local_metadata_provider() -> LocalMetadataProvider:
    providers: list[LocalMetadataProvider] = []
    if portal is not None and DataSourceFilter is not None:
        providers.append(PortalCurationMetadataProvider())

    spreadsheet_url = os.getenv(DATA_NOTE_TOLA_TSV_URL)
    if spreadsheet_url:
        providers.append(ToLASpreadsheetMetadataProvider(spreadsheet_url))

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
