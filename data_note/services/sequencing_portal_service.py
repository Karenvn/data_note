from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import PurePosixPath
from typing import Any, Callable

import pandas as pd

try:
    from tol.sources.portal import portal
except ImportError:  # pragma: no cover - optional internal dependency
    portal = None


logger = logging.getLogger(__name__)


PORTAL_CATEGORY_TO_PUBLIC: dict[str, tuple[str, str, str]] = {
    "hic": ("ILLUMINA", "Hi-C", "hic"),
    "rnaseq": ("ILLUMINA", "RNA-Seq", "rna"),
    "pacbio": ("PACBIO_SMRT", "WGS", "pacbio"),
}

MLWH_RUN_FIELDS: tuple[str, ...] = (
    "mlwh_pipeline_id_lims",
    "mlwh_instrument_model",
    "mlwh_instrument_name",
    "mlwh_study_id",
    "mlwh_library_id",
    "mlwh_sample_supplier_name",
    "mlwh_biosample_accession",
    "mlwh_biospecimen_accession",
    "mlwh_irods_path",
    "mlwh_irods_file",
    "mlwh_run_id",
    "mlwh_position",
    "mlwh_tag_index",
    "mlwh_tag1_id",
    "mlwh_tag_sequence",
    "mlwh_plex_count",
    "mlwh_pac_bio_run_name",
    "mlwh_pac_bio_library_tube_name",
    "mlwh_run_complete",
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text


def _basename(value: str) -> str:
    return PurePosixPath(value).name


def _split_ftp_files(value: Any) -> set[str]:
    text = _string_value(value)
    if not text:
        return set()
    return {_basename(part.strip()) for part in text.split(";") if part.strip()}


@dataclass(slots=True)
class PortalEnrichmentResult:
    dataframe: pd.DataFrame
    matched_run_ids: list[str] = field(default_factory=list)
    excluded_run_ids: list[str] = field(default_factory=list)
    dropped_public_run_accessions: list[str] = field(default_factory=list)
    unmatched_run_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    portal_run_data: list[dict[str, Any]] = field(default_factory=list)

    @property
    def applied(self) -> bool:
        return bool(self.matched_run_ids)


@dataclass(slots=True)
class PortalSequencingService:
    datasource_factory: Callable[[], Any] | None = None

    def portal_available(self) -> bool:
        return self.datasource_factory is not None or portal is not None

    def fetch_run_data(self, tolid: str | None) -> list[dict[str, Any]]:
        if not tolid or not self.portal_available():
            return []

        try:
            datasource = self._datasource()
            tolid_records = [obj for obj in datasource.get_by_id("tolid", [tolid]) if obj is not None]
            if not tolid_records:
                return []
            run_objects = list(datasource.get_to_many_relations(tolid_records[0], "tolqc_run_datas"))
        except Exception as exc:
            logger.warning("ToL Portal sequencing lookup unavailable for %s: %s", tolid, exc)
            return []

        rows: list[dict[str, Any]] = []
        for run_object in run_objects:
            attrs = dict(getattr(run_object, "attributes", {}) or {})
            attrs["portal_run_id"] = getattr(run_object, "id", None) or attrs.get("tolqc_run")
            rows.append(attrs)
        return rows

    @staticmethod
    def biosample_accessions(portal_rows: list[dict[str, Any]]) -> list[str]:
        accessions: list[str] = []
        seen: set[str] = set()
        for row in portal_rows:
            for field_name in (
                "mlwh_biosample_accession",
                "mlwh_biospecimen_accession",
                "tolqc_biospecimen_id",
            ):
                accession = _string_value(row.get(field_name))
                if accession and accession not in seen:
                    seen.add(accession)
                    accessions.append(accession)
        return accessions

    def enrich_dataframe(
        self,
        dataframe: pd.DataFrame,
        *,
        tolid: str,
        portal_rows: list[dict[str, Any]],
        biosample_tolid_map: dict[str, str | None],
        mode: str,
    ) -> PortalEnrichmentResult:
        enriched = dataframe.copy()
        result = PortalEnrichmentResult(dataframe=enriched, portal_run_data=portal_rows)
        if enriched.empty or self._normalise_mode(mode) == "public" or not portal_rows:
            return result

        for portal_row in portal_rows:
            portal_id = _string_value(portal_row.get("portal_run_id"))
            if self._has_mismatched_portal_sample(portal_row, tolid, biosample_tolid_map, result):
                if portal_id:
                    result.excluded_run_ids.append(portal_id)
                result.dropped_public_run_accessions.extend(
                    self._drop_mismatched_public_rows(enriched, portal_row)
                )
                continue

            row_index = self._match_public_row(enriched, portal_row)
            if row_index is None:
                if portal_id:
                    result.unmatched_run_ids.append(portal_id)
                continue

            self._apply_portal_row(enriched, row_index, portal_row, mode=self._normalise_mode(mode))
            if portal_id:
                result.matched_run_ids.append(portal_id)

        return result

    def _datasource(self):
        if self.datasource_factory is not None:
            return self.datasource_factory()
        if portal is None:
            raise RuntimeError("tol-sdk is not installed")
        return portal()

    @staticmethod
    def _normalise_mode(mode: str) -> str:
        normalised = (mode or "public-with-portal").strip().lower().replace("_", "-")
        if normalised in {"public", "public-only"}:
            return "public"
        if normalised in {"portal", "portal-priority", "portal-only"}:
            return "portal"
        return "public-with-portal"

    @staticmethod
    def _portal_technology(portal_row: dict[str, Any]) -> str | None:
        category = _string_value(portal_row.get("tolqc_reporting_category")).lower()
        mapping = PORTAL_CATEGORY_TO_PUBLIC.get(category)
        return mapping[2] if mapping else None

    @staticmethod
    def _row_technology(row: pd.Series) -> str | None:
        platform = _string_value(row.get("instrument_platform"))
        strategy = _string_value(row.get("library_strategy"))
        for expected_platform, expected_strategy, technology in PORTAL_CATEGORY_TO_PUBLIC.values():
            if platform == expected_platform and strategy == expected_strategy:
                return technology
        return None

    def _has_mismatched_portal_sample(
        self,
        portal_row: dict[str, Any],
        tolid: str,
        biosample_tolid_map: dict[str, str | None],
        result: PortalEnrichmentResult,
    ) -> bool:
        portal_id = _string_value(portal_row.get("portal_run_id"))
        exclude = False
        for field_name in ("mlwh_biosample_accession", "mlwh_biospecimen_accession"):
            accession = _string_value(portal_row.get(field_name))
            if not accession:
                continue
            sample_tolid = biosample_tolid_map.get(accession)
            if sample_tolid and sample_tolid != tolid:
                result.warnings.append(
                    f"Portal run {portal_id or '<unknown>'} has {field_name}={accession} "
                    f"with BioSamples ToLID {sample_tolid}, not {tolid}."
                )
                if field_name == "mlwh_biosample_accession":
                    exclude = True
        return exclude

    def _match_public_row(self, dataframe: pd.DataFrame, portal_row: dict[str, Any]) -> Any | None:
        portal_technology = self._portal_technology(portal_row)
        if portal_technology is None:
            return None

        portal_sample = _string_value(portal_row.get("mlwh_biosample_accession"))
        candidates: list[Any] = []
        for index, row in dataframe.iterrows():
            if self._row_technology(row) != portal_technology:
                continue
            public_sample = _string_value(row.get("sample_accession"))
            if portal_sample and public_sample and portal_sample != public_sample:
                continue
            candidates.append(index)

        if not candidates:
            return None

        file_matches = [index for index in candidates if self._file_match(dataframe.loc[index], portal_row)]
        if len(file_matches) == 1:
            return file_matches[0]

        library_matches = [index for index in candidates if self._library_match(dataframe.loc[index], portal_row)]
        if len(library_matches) == 1:
            return library_matches[0]

        if len(candidates) == 1:
            return candidates[0]

        return None

    def _drop_mismatched_public_rows(self, dataframe: pd.DataFrame, portal_row: dict[str, Any]) -> list[str]:
        dropped: list[str] = []
        for index, row in list(dataframe.iterrows()):
            if self._row_technology(row) != self._portal_technology(portal_row):
                continue
            if not self._mismatched_public_row_match(row, portal_row):
                continue
            read_accession = _string_value(row.get("run_accession"))
            if read_accession:
                dropped.append(read_accession)
            dataframe.drop(index=index, inplace=True)
        if dropped:
            dataframe.reset_index(drop=True, inplace=True)
        return dropped

    @staticmethod
    def _mismatched_public_row_match(row: pd.Series, portal_row: dict[str, Any]) -> bool:
        library_name = _string_value(row.get("library_name"))
        portal_libraries = {
            _string_value(portal_row.get("mlwh_library_id")),
            _string_value(portal_row.get("mlwh_pac_bio_library_tube_name")),
        }
        if library_name and library_name in {value for value in portal_libraries if value}:
            return True

        public_text = " ".join(
            _string_value(row.get(field_name))
            for field_name in (
                "run_alias",
                "experiment_alias",
                "submitted_ftp",
                "fastq_ftp",
                "library_name",
            )
        )
        run_id = _string_value(portal_row.get("mlwh_run_id")) or _string_value(portal_row.get("tolqc_run"))
        barcode = _string_value(portal_row.get("mlwh_tag1_id")) or _string_value(portal_row.get("tolqc_tag_sequence"))
        return bool(run_id and run_id in public_text and (not barcode or barcode in public_text))

    @staticmethod
    def _file_match(row: pd.Series, portal_row: dict[str, Any]) -> bool:
        public_files = _split_ftp_files(row.get("submitted_ftp")) | _split_ftp_files(row.get("fastq_ftp"))
        if not public_files:
            return False

        portal_files = {
            _string_value(portal_row.get("mlwh_irods_file")),
            _string_value(portal_row.get("portal_run_id")),
        }
        portal_files = {value for value in portal_files if value}
        portal_stems = {value.removesuffix(".cram").removesuffix(".bam") for value in portal_files}
        public_stems = {value.removesuffix(".cram").removesuffix(".bam") for value in public_files}
        return bool((portal_files & public_files) or (portal_stems & public_stems))

    @staticmethod
    def _library_match(row: pd.Series, portal_row: dict[str, Any]) -> bool:
        library_name = _string_value(row.get("library_name"))
        if not library_name:
            return False
        portal_libraries = {
            _string_value(portal_row.get("mlwh_library_id")),
            _string_value(portal_row.get("mlwh_pac_bio_library_tube_name")),
        }
        return library_name in portal_libraries

    @staticmethod
    def _apply_portal_row(
        dataframe: pd.DataFrame,
        row_index: Any,
        portal_row: dict[str, Any],
        *,
        mode: str,
    ) -> None:
        portal_reads = _safe_int(portal_row.get("tolqc_reads"))
        portal_bases = _safe_int(portal_row.get("tolqc_bases"))
        public_reads = _safe_int(dataframe.at[row_index, "read_count"] if "read_count" in dataframe else 0)
        public_bases = _safe_int(dataframe.at[row_index, "base_count"] if "base_count" in dataframe else 0)

        dataframe.at[row_index, "public_read_count"] = public_reads
        dataframe.at[row_index, "public_base_count"] = public_bases
        dataframe.at[row_index, "portal_run_id"] = _string_value(portal_row.get("portal_run_id"))
        dataframe.at[row_index, "portal_reads"] = portal_reads
        dataframe.at[row_index, "portal_bases"] = portal_bases
        dataframe.at[row_index, "portal_reported_read_count_unit"] = "reads"
        dataframe.at[row_index, "portal_read_length_mean"] = portal_row.get("tolqc_read_length_mean", "")
        dataframe.at[row_index, "portal_lims_qc"] = portal_row.get("tolqc_lims_qc", "")
        dataframe.at[row_index, "portal_manual_qc"] = portal_row.get("tolqc_manual_qc", "")

        for field_name in MLWH_RUN_FIELDS:
            dataframe.at[row_index, field_name] = portal_row.get(field_name, "")

        prefer_portal = mode == "portal"
        if portal_reads > 0 and (prefer_portal or public_reads <= 0):
            dataframe.at[row_index, "read_count"] = portal_reads
            dataframe.at[row_index, "read_count_basis"] = "reads"
            dataframe.at[row_index, "read_count_source"] = "portal_tolqc"
        elif "read_count_source" not in dataframe or not _string_value(dataframe.at[row_index, "read_count_source"]):
            dataframe.at[row_index, "read_count_source"] = _string_value(
                dataframe.at[row_index, "metadata_source"] if "metadata_source" in dataframe else "public"
            )

        if portal_bases > 0 and (prefer_portal or public_bases <= 0):
            dataframe.at[row_index, "base_count"] = portal_bases
            dataframe.at[row_index, "base_count_source"] = "portal_tolqc"
        elif "base_count_source" not in dataframe or not _string_value(dataframe.at[row_index, "base_count_source"]):
            dataframe.at[row_index, "base_count_source"] = _string_value(
                dataframe.at[row_index, "metadata_source"] if "metadata_source" in dataframe else "public"
            )
