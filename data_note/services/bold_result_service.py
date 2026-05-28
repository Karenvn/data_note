from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import importlib
import importlib.util
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping

from ..gbif_occurrence_client import GbifOccurrenceClient
from ..gbif_taxonomy_client import GbifTaxonomyClient
from ..species_summary_models import GbifDistributionSummary
from ..text_utils import oxford_comma_list


def _normalise_name(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"\s+", " ", name).strip().lower()


@dataclass(slots=True)
class BoldResultService:
    workflow_runner: Callable[[str], Any] | None = None
    gbif_taxonomy_client: GbifTaxonomyClient = field(default_factory=GbifTaxonomyClient)
    gbif_occurrence_client: GbifOccurrenceClient = field(default_factory=GbifOccurrenceClient)
    today_provider: Callable[[], date] = date.today

    def build_text(
        self,
        assembly_accession: str | None,
        species: str | None,
    ) -> str | None:
        if not assembly_accession:
            return None

        runner = self.workflow_runner or self._load_workflow_runner()
        raw_result = runner(assembly_accession)
        if hasattr(raw_result, "to_dict"):
            result = dict(raw_result.to_dict())
        else:
            result = dict(raw_result or {})

        if not result.get("success"):
            raise RuntimeError(str(result.get("error") or "BOLD workflow failed"))

        return self.render_result(result, expected_species=species)

    def render_result(
        self,
        result: Mapping[str, Any],
        *,
        expected_species: str | None = None,
    ) -> str | None:
        mt_accession = str(result.get("mt_accession") or "").strip()
        bin_number = str(result.get("bin_number") or "").strip()
        match_name = str(result.get("bold_match") or "").strip()
        process_id = str(result.get("bold_process_id") or "").strip()
        similarity = self._coerce_float(result.get("bold_similarity"))
        self_hit = bool(result.get("bold_self_hit"))
        accessed = self.today_provider().isoformat()

        if not any((mt_accession, bin_number, match_name)):
            return None

        sentences: list[str] = []

        if mt_accession and bin_number:
            sentences.append(
                f"The DNA barcode from the mitochondrial assembly ({mt_accession}) belongs to "
                f"BOLD cluster {bin_number} (accessed {accessed})."
            )
        elif mt_accession:
            sentences.append(
                f"The DNA barcode from the mitochondrial assembly ({mt_accession}) was compared "
                f"against public BOLD records (accessed {accessed})."
            )
        elif bin_number:
            sentences.append(f"The recovered COI barcode belongs to BOLD cluster {bin_number} (accessed {accessed}).")

        if match_name:
            lead = "After ignoring a likely self-hit, the closest species-level match on BOLD is"
            if not self_hit:
                lead = "The closest species-level match on BOLD is"

            clause = f"{lead} *{match_name}*"
            if process_id:
                clause += f", represented by {process_id}"

            if similarity is not None:
                expected = _normalise_name(expected_species)
                observed = _normalise_name(match_name)
                if expected and observed and expected != observed:
                    clause += (
                        f", which differs from *{expected_species}* by approximately a "
                        f"*p*-distance of {max(0.0, 100.0 - similarity):.2f}%."
                    )
                else:
                    clause += f" at {similarity:.2f}% similarity."
            else:
                clause += "."
            sentences.append(clause)

        nearest_distribution = self._nearest_species_distribution_sentence(match_name, expected_species)
        if nearest_distribution:
            sentences.append(nearest_distribution)

        return " ".join(sentences)

    def _nearest_species_distribution_sentence(
        self,
        match_name: str,
        expected_species: str | None,
    ) -> str | None:
        observed = _normalise_name(match_name)
        expected = _normalise_name(expected_species)
        if not observed or (expected and observed == expected):
            return None

        gbif_data = self.gbif_taxonomy_client.fetch_species_metadata(match_name)
        usage_key = gbif_data.get("gbif_usage_key")
        if not usage_key:
            return None

        summary = self.gbif_occurrence_client.fetch_distribution_summary(usage_key)
        return self._render_compact_distribution(match_name, summary)

    def _load_workflow_runner(self) -> Callable[[str], Any]:
        repo_path = os.environ.get("DATA_NOTE_BOLD_REPO", "").strip()
        if repo_path:
            return self._load_workflow_runner_from_path(repo_path)

        try:
            from . import bold_coi_pipeline

            return bold_coi_pipeline.process_gca_accession
        except ImportError:
            try:
                module = importlib.import_module("bold_coi_pipeline")
                return module.process_gca_accession
            except ImportError as external_exc:
                raise RuntimeError(
                    "BOLD workflow is not available. The bundled data_note workflow could not be imported, "
                    "and no external bold_coi_pipeline package was found."
                ) from external_exc

    def _load_workflow_runner_from_path(self, repo_path: str) -> Callable[[str], Any]:
        module_path = Path(repo_path).expanduser() / "bold_coi_pipeline.py"
        if not module_path.is_file():
            raise RuntimeError(
                f"DATA_NOTE_BOLD_REPO does not contain bold_coi_pipeline.py: {module_path}"
            )

        spec = importlib.util.spec_from_file_location("bold_coi_pipeline", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load BOLD workflow module from {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module.process_gca_accession

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _render_compact_distribution(
        species_name: str,
        summary: GbifDistributionSummary,
    ) -> str | None:
        if summary.record_count <= 0:
            return None

        if summary.countries:
            labels = [item.label for item in summary.countries[:3]]
            if len(labels) == 1:
                return f"*{species_name}* has public GBIF occurrence records from {labels[0]}."
            return f"*{species_name}* has public GBIF occurrence records from {oxford_comma_list(labels)}."

        if summary.continents:
            labels = [item.label for item in summary.continents[:3]]
            if len(labels) == 1:
                return f"*{species_name}* has public GBIF occurrence records from {labels[0]}."
            return f"*{species_name}* has public GBIF occurrence records from {oxford_comma_list(labels)}."

        return None


__all__ = ["BoldResultService"]
