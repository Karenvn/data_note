from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .formatting_utils import format_with_nbsp
from .species_summary_models import GbifDistributionSummary, GbifFacetCount
from .text_utils import oxford_comma_list


@dataclass(slots=True)
class GbifOccurrenceClient:
    request_get: Callable[..., Any] = requests.get
    timeout: int = 30
    _country_lookup: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def fetch_distribution_summary(
        self,
        usage_key: int | str,
        *,
        facet_limit: int = 20,
    ) -> GbifDistributionSummary:
        response = self.request_get(
            "https://api.gbif.org/v1/occurrence/search",
            params={
                "taxonKey": str(usage_key),
                "hasCoordinate": "true",
                "limit": 0,
                "facet": ["country", "continent"],
                "facetLimit": facet_limit,
                "facetMincount": 1,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json() or {}
        return GbifDistributionSummary(
            usage_key=str(usage_key),
            record_count=int(data.get("count") or 0),
            countries=self._parse_facet_counts(data.get("facets", []), "COUNTRY"),
            continents=self._parse_facet_counts(data.get("facets", []), "CONTINENT"),
            species_url=f"https://www.gbif.org/species/{usage_key}",
        )

    def render_distribution_summary(self, summary: GbifDistributionSummary) -> str:
        if summary.record_count <= 0:
            return (
                "No GBIF occurrence records with coordinates are currently available for this species. "
                f"(Source: [GBIF]({summary.species_url}))"
            )

        lines = [
            "A total of "
            f"{format_with_nbsp(summary.record_count, as_int=True)} GBIF occurrence records with "
            "coordinates are available for this species."
        ]

        if summary.continents:
            if len(summary.continents) == 1:
                lines.append(f"All the records are from {summary.continents[0].label}.")
            else:
                items = [
                    f"{item.label} ({format_with_nbsp(item.count, as_int=True)})"
                    for item in summary.continents
                ]
                lines.append(
                    "The species has been observed on the following continents: "
                    f"{oxford_comma_list(items)}."
                )

        if summary.countries:
            if len(summary.countries) == 1:
                lines.append(f"All records are from {summary.countries[0].label}.")
            elif len(summary.countries) <= 12:
                items = [
                    f"{item.label} ({format_with_nbsp(item.count, as_int=True)})"
                    for item in summary.countries
                ]
                lines.append(
                    f"It has been most frequently recorded in {oxford_comma_list(items)}."
                )
            else:
                top_countries = self._top_countries_covering_fraction(summary.countries, fraction=0.8)
                lines.append(
                    "The species has been recorded in several countries, most frequently in "
                    f"{oxford_comma_list(top_countries)}."
                )

        lines.append(f"(Source: [GBIF]({summary.species_url}))")
        return " ".join(lines)

    def _parse_facet_counts(
        self,
        facets: list[dict[str, Any]],
        field_name: str,
    ) -> list[GbifFacetCount]:
        for facet in facets:
            if facet.get("field") != field_name:
                continue
            return [
                GbifFacetCount(
                    code=str(item.get("name") or ""),
                    label=self._label_for_facet(field_name, str(item.get("name") or "")),
                    count=int(item.get("count") or 0),
                )
                for item in facet.get("counts", [])
                if item.get("name")
            ]
        return []

    def _label_for_facet(self, field_name: str, value: str) -> str:
        if field_name == "COUNTRY":
            return self._country_lookup_for(value)
        if field_name == "CONTINENT":
            return value.replace("_", " ").title()
        return value

    def _country_lookup_for(self, iso2_code: str) -> str:
        if not self._country_lookup:
            response = self.request_get(
                "https://api.gbif.org/v1/enumeration/country",
                timeout=self.timeout,
            )
            response.raise_for_status()
            items = response.json() or []
            self._country_lookup = {
                str(item.get("iso2") or ""): str(item.get("title") or "")
                for item in items
                if item.get("iso2") and item.get("title")
            }
        return self._country_lookup.get(iso2_code, iso2_code)

    @staticmethod
    def _top_countries_covering_fraction(
        countries: list[GbifFacetCount],
        *,
        fraction: float,
    ) -> list[str]:
        total = sum(item.count for item in countries)
        if total <= 0:
            return []

        running_total = 0
        selected: list[str] = []
        for item in countries:
            running_total += item.count
            selected.append(item.label)
            if running_total / total >= fraction:
                break
        return selected


__all__ = ["GbifOccurrenceClient"]
