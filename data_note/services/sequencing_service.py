from __future__ import annotations

from dataclasses import dataclass, field
import logging
from numbers import Real
import os
import re
from typing import Any, Callable

import pandas as pd

from ..fetch_biosample_info import get_biosample_tolid_map
from ..formatting_utils import format_with_nbsp
from ..formatting_utils import bytes_to_gb, format_scientific
from ..models import AssemblySelection, RunGroup, RunRecord, SequencingSummary, SequencingTotals, TechnologyRecord
from .sequencing_portal_service import (
    PORTAL_PREP_FIELDS,
    PortalEnrichmentResult,
    PortalSequencingService,
)
from .sequencing_fetch_service import SequencingFetchService


TECHNOLOGY_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("PACBIO_SMRT", "WGS", "pacbio", "PacBio"),
    ("ILLUMINA", "Hi-C", "hic", "Hi-C"),
    ("ILLUMINA", "WGS", "chromium", "Chromium"),
    ("ILLUMINA", "RNA-Seq", "rna", "RNA"),
)

TECHNOLOGY_NAMES: tuple[str, ...] = tuple(rule[2] for rule in TECHNOLOGY_RULES)
RUN_GROUP_NAMES: tuple[str, ...] = tuple(rule[3] for rule in TECHNOLOGY_RULES)
RUN_ACCESSION_GROUPS: tuple[tuple[str, str], ...] = (
    ("PacBio", "pacbio"),
    ("Hi-C", "hic"),
    ("Chromium", "chromium"),
    ("RNA", "rna"),
)
TECHNOLOGY_LABELS: dict[str, str] = {
    "pacbio": "PacBio HiFi",
    "hic": "Hi-C",
    "chromium": "Chromium",
    "rna": "RNA-seq",
}
NUMERIC_COLUMNS: tuple[str, ...] = ("fastq_bytes", "submitted_bytes", "read_count", "base_count")
TEXT_COLUMNS: tuple[str, ...] = (
    "study_accession",
    "run_accession",
    "run_alias",
    "experiment_accession",
    "experiment_alias",
    "experiment_title",
    "sample_accession",
    "sample_alias",
    "instrument_model",
    "library_strategy",
    "library_layout",
    "library_name",
    "library_construction_protocol",
    "library_source",
    "library_selection",
    "nominal_length",
    "nominal_sdev",
    "instrument_platform",
    "submitted_ftp",
    "fastq_ftp",
    "metadata_source",
    "supplementary_metadata_source",
    "read_count_basis",
    "read_count_source",
    "base_count_source",
    "read_count_unit",
    "public_read_count",
    "public_base_count",
    "portal_run_id",
    "portal_reads",
    "portal_bases",
    "portal_reported_read_count_unit",
    "portal_read_length_mean",
    "portal_lims_qc",
    "portal_manual_qc",
    "portal_qc",
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
    "mlwh_lims_qc",
    "mlwh_qc_seq_state",
    "mlwh_qc_seq_state_is_final",
    "mlwh_qc_date",
    *PORTAL_PREP_FIELDS,
    "multiplex_identifier",
    "multiplex_identifier_type",
    "multiplex_label",
    "multiplex_source",
    "sequencing_run",
    "multiplex_sample",
)
SEQUENCING_COLUMNS: tuple[str, ...] = (
    "study_accession",
    "run_accession",
    "sample_accession",
    "fastq_bytes",
    "submitted_bytes",
    "read_count",
    "instrument_model",
    "base_count",
    "library_strategy",
    "library_name",
    "library_construction_protocol",
    "instrument_platform",
)

logger = logging.getLogger(__name__)


def _sequencing_source_from_env() -> str:
    return os.getenv("DATA_NOTE_SEQUENCING_SOURCE", "public-with-portal")


def _illumina_count_unit_from_env() -> str:
    return os.getenv("DATA_NOTE_ILLUMINA_COUNT_UNIT", "read_pairs")


@dataclass(slots=True)
class SequencingService:
    fetch_service: SequencingFetchService = field(default_factory=SequencingFetchService)
    portal_service: PortalSequencingService = field(default_factory=PortalSequencingService)
    biosample_tolid_getter: Callable[[list[str]], dict[str, str | None]] = get_biosample_tolid_map
    assembly_run_accession_fetcher: Callable[[list[str]], set[str]] | None = None
    sequencing_source: str = field(default_factory=_sequencing_source_from_env)
    illumina_count_unit: str = field(default_factory=_illumina_count_unit_from_env)

    def empty_context(self) -> SequencingSummary:
        empty_df = self._select_columns(self._empty_dataframe())
        technology_records = self._build_technology_records(empty_df)
        run_groups = self._build_run_groups(empty_df)
        run_accessions = self._build_run_accessions(run_groups)
        return SequencingSummary(
            technology_records=technology_records,
            run_groups=run_groups,
            totals=self._build_totals(empty_df, technology_records),
            pacbio_protocols=[],
            run_accessions=run_accessions,
            multiplexing=[],
        )

    def build_context(
        self,
        bioprojects: Any,
        tolid: str,
        *,
        assembly_selection: AssemblySelection | None = None,
    ) -> SequencingSummary:
        bioproject_list = self._normalise_bioprojects(bioprojects)
        logger.info(
            "Scanning sequencing BioProject candidate(s): %s.",
            ", ".join(bioproject_list),
        )
        fetch_result = self.fetch_service.fetch_for_bioprojects_with_sources(bioproject_list)
        read_study_df = fetch_result.dataframe
        if read_study_df.empty:
            raise RuntimeError(
                f"No SRA RunInfo rows found for BioProjects: {', '.join(bioproject_list)}"
            )
        logger.info(
            "Processing sequencing information for bioproject(s): %s.",
            ", ".join(fetch_result.source_accessions),
        )

        if "sample_accession" not in read_study_df.columns:
            raise RuntimeError(
                f"Missing sample_accession for BioProjects: {', '.join(bioproject_list)}"
            )

        assembly_run_accessions = self._assembly_run_accessions(assembly_selection)
        read_study_df, assembly_filter_excluded_runs = self._filter_rows_by_assembly_run_accessions(
            read_study_df,
            assembly_run_accessions,
        )

        biosample_ids = read_study_df["sample_accession"].dropna().unique().tolist()
        biosample_tolid_map = self.biosample_tolid_getter(biosample_ids)
        read_study_df = self._filter_pacbio_rows_by_tolid(read_study_df, tolid, biosample_tolid_map)
        portal_result = self._enrich_from_portal(
            read_study_df,
            tolid=tolid,
            biosample_tolid_map=biosample_tolid_map,
        )
        read_study_df = portal_result.dataframe
        read_study_df, qc_excluded_runs, qc_excluded_portal_runs = self._filter_failed_qc_rows(
            read_study_df,
            protected_run_accessions=assembly_run_accessions,
        )
        technology_df = self._select_columns(read_study_df)
        technology_df = self._normalise_read_count_units(technology_df)
        technology_df = self._add_multiplexing_columns(technology_df)
        technology_records = self._build_technology_records(technology_df)
        run_groups = self._build_run_groups(technology_df)
        multiplexing = self._build_multiplexing_records(technology_df)

        pacbio_protocols = self._extract_pacbio_protocols(technology_df)

        run_accessions = self._build_run_accessions(run_groups)
        return SequencingSummary(
            technology_records=technology_records,
            run_groups=run_groups,
            totals=self._build_totals(
                technology_df,
                technology_records,
                source_accessions=fetch_result.source_accessions,
                portal_result=portal_result,
                sequencing_source=self._normalise_sequencing_source(),
                illumina_count_unit=self._normalise_illumina_count_unit(),
                assembly_run_accessions=assembly_run_accessions,
                assembly_filter_excluded_runs=assembly_filter_excluded_runs,
                qc_filter_excluded_runs=qc_excluded_runs,
                qc_filter_excluded_portal_runs=qc_excluded_portal_runs,
            ),
            pacbio_protocols=pacbio_protocols,
            run_accessions=run_accessions,
            multiplexing=multiplexing,
        )

    @staticmethod
    def _normalise_bioprojects(bioprojects: Any) -> list[str]:
        if isinstance(bioprojects, (list, tuple, set)):
            return list(bioprojects)
        return [bioprojects]

    @staticmethod
    def _empty_dataframe() -> pd.DataFrame:
        return pd.DataFrame(
            columns=list(SEQUENCING_COLUMNS)
        )

    @staticmethod
    def _select_columns(df: pd.DataFrame) -> pd.DataFrame:
        normalised = df.copy()

        for column in NUMERIC_COLUMNS:
            if column not in normalised.columns:
                normalised[column] = 0
            normalised[column] = normalised[column].apply(SequencingService._numeric_total).astype(int)

        for column in TEXT_COLUMNS:
            if column not in normalised.columns:
                normalised[column] = ""
            else:
                normalised[column] = normalised[column].fillna("").astype(str)

        selected_columns = list(SEQUENCING_COLUMNS)
        for column in TEXT_COLUMNS:
            if column not in selected_columns:
                selected_columns.append(column)

        return normalised.loc[:, selected_columns]

    def _enrich_from_portal(
        self,
        read_study_df: pd.DataFrame,
        *,
        tolid: str,
        biosample_tolid_map: dict[str, str | None],
    ) -> PortalEnrichmentResult:
        sequencing_source = self._normalise_sequencing_source()
        empty_result = PortalEnrichmentResult(dataframe=read_study_df.copy())
        if sequencing_source == "public" or not tolid:
            return empty_result

        portal_rows = self._portal_rows_for_sequencing_samples(read_study_df, tolid, biosample_tolid_map)
        if not portal_rows:
            return PortalEnrichmentResult(dataframe=read_study_df.copy(), portal_run_data=[])

        extra_biosamples = [
            accession
            for accession in self.portal_service.biosample_accessions(portal_rows)
            if accession not in biosample_tolid_map
        ]
        if extra_biosamples:
            biosample_tolid_map.update(self.biosample_tolid_getter(extra_biosamples))

        return self.portal_service.enrich_dataframe(
            read_study_df,
            tolid=tolid,
            portal_rows=portal_rows,
            biosample_tolid_map=biosample_tolid_map,
            mode=sequencing_source,
        )

    def _portal_rows_for_sequencing_samples(
        self,
        read_study_df: pd.DataFrame,
        tolid: str,
        biosample_tolid_map: dict[str, str | None],
    ) -> list[dict[str, Any]]:
        portal_rows = self.portal_service.fetch_run_data(tolid)
        seen_run_ids = {
            self._string_value(row.get("portal_run_id"))
            for row in portal_rows
            if self._string_value(row.get("portal_run_id"))
        }

        wanted_related_pairs: set[tuple[str, str]] = set()
        related_tolids: set[str] = set()
        for _, row in read_study_df.iterrows():
            match = self._match_technology(row)
            if match is None:
                continue
            tech_name, _ = match
            if tech_name == "pacbio":
                continue
            sample_accession = self._string_value(row.get("sample_accession"))
            sample_tolid = biosample_tolid_map.get(sample_accession)
            if not sample_accession or not sample_tolid or sample_tolid == tolid:
                continue
            wanted_related_pairs.add((tech_name, sample_accession))
            related_tolids.add(sample_tolid)

        for related_tolid in sorted(related_tolids):
            for row in self.portal_service.fetch_run_data(related_tolid):
                portal_run_id = self._string_value(row.get("portal_run_id"))
                if portal_run_id and portal_run_id in seen_run_ids:
                    continue
                portal_tech = self.portal_service._portal_technology(row)
                portal_sample = self._string_value(row.get("mlwh_biosample_accession"))
                if (portal_tech, portal_sample) not in wanted_related_pairs:
                    continue
                portal_rows.append(row)
                if portal_run_id:
                    seen_run_ids.add(portal_run_id)

        return portal_rows

    def _normalise_read_count_units(self, df: pd.DataFrame) -> pd.DataFrame:
        normalised = df.copy()
        illumina_count_unit = self._normalise_illumina_count_unit()

        for index, row in normalised.iterrows():
            if not self._is_paired_illumina(row):
                normalised.at[index, "read_count_unit"] = "reads"
                continue

            read_count = self._numeric_value(row.get("read_count"))
            basis = self._string_value(row.get("read_count_basis")).lower()

            if illumina_count_unit == "reads":
                if basis in {"spots", "spot", "read_pairs", "pairs", "fragments"}:
                    read_count *= 2
                normalised.at[index, "read_count"] = int(round(read_count))
                normalised.at[index, "read_count_unit"] = "reads"
                continue

            if basis in {"reads", "individual_reads", "ena_reads", "portal_reads"}:
                read_count /= 2
            normalised.at[index, "read_count"] = int(round(read_count))
            normalised.at[index, "read_count_unit"] = "read pairs"

        return normalised

    @staticmethod
    def _add_multiplexing_columns(df: pd.DataFrame) -> pd.DataFrame:
        normalised = df.copy()
        for column in (
            "multiplex_identifier",
            "multiplex_identifier_type",
            "multiplex_label",
            "multiplex_source",
            "sequencing_run",
            "multiplex_sample",
        ):
            if column not in normalised.columns:
                normalised[column] = ""

        for index, row in normalised.iterrows():
            multiplexing = SequencingService._extract_multiplexing(row)
            for key, value in multiplexing.items():
                normalised.at[index, key] = value

        return normalised

    @staticmethod
    def _extract_multiplexing(row: pd.Series) -> dict[str, str]:
        match = SequencingService._match_technology(row)
        tech_name = match[0] if match else ""

        if tech_name == "pacbio":
            pacbio_barcode = SequencingService._extract_pacbio_barcode(row)
            if pacbio_barcode:
                return pacbio_barcode

        portal_tag = SequencingService._extract_portal_tag(row)
        if portal_tag:
            return portal_tag

        illumina_tag = SequencingService._extract_illumina_tag(row)
        if illumina_tag:
            return illumina_tag

        if tech_name != "pacbio":
            pacbio_barcode = SequencingService._extract_pacbio_barcode(row)
            if pacbio_barcode:
                return pacbio_barcode

        return {}

    @staticmethod
    def _extract_portal_tag(row: pd.Series) -> dict[str, str]:
        tag_index = SequencingService._string_value(row.get("mlwh_tag_index"))
        tag_id = SequencingService._string_value(row.get("mlwh_tag1_id"))
        tag_sequence = SequencingService._string_value(row.get("mlwh_tag_sequence"))
        if not (tag_index or tag_id or tag_sequence):
            return {}

        identifier = tag_index or tag_id or tag_sequence
        identifier_type = "Illumina tag index" if tag_index else "Illumina tag"
        label = f"tag {identifier}"
        if tag_sequence and tag_sequence != identifier:
            label = f"{label} ({tag_sequence})"

        return {
            "multiplex_identifier": identifier,
            "multiplex_identifier_type": identifier_type,
            "multiplex_label": label,
            "multiplex_source": "portal_mlwh",
            "sequencing_run": SequencingService._string_value(row.get("mlwh_run_id")),
        }

    @staticmethod
    def _extract_pacbio_barcode(row: pd.Series) -> dict[str, str]:
        for field_name in (
            "run_alias",
            "experiment_alias",
            "submitted_ftp",
            "mlwh_irods_file",
            "portal_run_id",
        ):
            value = SequencingService._string_value(row.get(field_name))
            if not value:
                continue
            match = re.search(r"(?i)(?<![A-Za-z0-9])(?P<barcode>t?bc\d+)(?![A-Za-z0-9])", value)
            if match is None:
                continue
            barcode = match.group("barcode")
            result = {
                "multiplex_identifier": barcode,
                "multiplex_identifier_type": "PacBio barcode",
                "multiplex_label": f"barcode {barcode}",
                "multiplex_source": field_name,
                "sequencing_run": SequencingService._extract_pacbio_run(value),
            }
            sample = SequencingService._extract_pacbio_sample(value)
            if sample:
                result["multiplex_sample"] = sample
            return result
        return {}

    @staticmethod
    def _extract_illumina_tag(row: pd.Series) -> dict[str, str]:
        for field_name in (
            "run_alias",
            "experiment_alias",
            "submitted_ftp",
            "mlwh_irods_file",
            "portal_run_id",
        ):
            value = SequencingService._string_value(row.get(field_name))
            if not value:
                continue
            match = re.search(r"#(?P<tag>\d+)(?!\d)", value)
            if match is None:
                continue
            tag = match.group("tag")
            return {
                "multiplex_identifier": tag,
                "multiplex_identifier_type": "Illumina tag index",
                "multiplex_label": f"tag {tag}",
                "multiplex_source": field_name,
                "sequencing_run": SequencingService._extract_illumina_run(value),
            }
        return {}

    @staticmethod
    def _extract_pacbio_run(value: str) -> str:
        match = re.search(r"(m\d+_\d+_\d+_s\d+)", value)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_pacbio_sample(value: str) -> str:
        match = re.search(r":(s\d+)(?::|$)", value)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_illumina_run(value: str) -> str:
        match = re.search(r"(?P<run>(?:SC_(?:RUN|EXP)_)?[^/;\s#]+)#\d+", value)
        if match is None:
            return ""
        return re.sub(r"^SC_(?:RUN|EXP)_", "", match.group("run"))

    @staticmethod
    def _build_multiplexing_records(df: pd.DataFrame) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for _, row in df.iterrows():
            match = SequencingService._match_technology(row)
            identifier = SequencingService._string_value(row.get("multiplex_identifier"))
            if match is None or not identifier:
                continue

            tech_name, _ = match
            read_accession = SequencingService._string_value(row.get("run_accession"))
            key = (tech_name, read_accession, identifier)
            if key in seen:
                continue
            seen.add(key)

            record = {
                "technology": tech_name,
                "technology_label": TECHNOLOGY_LABELS.get(tech_name, tech_name),
                "read_accession": read_accession,
                "sample_accession": SequencingService._string_value(row.get("sample_accession")),
                "multiplex_identifier": identifier,
                "multiplex_identifier_type": SequencingService._string_value(row.get("multiplex_identifier_type")),
                "multiplex_label": SequencingService._string_value(row.get("multiplex_label")),
                "multiplex_source": SequencingService._string_value(row.get("multiplex_source")),
                "sequencing_run": SequencingService._string_value(row.get("sequencing_run")),
                "run_alias": SequencingService._string_value(row.get("run_alias")),
                "experiment_alias": SequencingService._string_value(row.get("experiment_alias")),
                "plex_count": SequencingService._string_value(row.get("mlwh_plex_count")),
            }
            multiplex_sample = SequencingService._string_value(row.get("multiplex_sample"))
            if multiplex_sample:
                record["multiplex_sample"] = multiplex_sample
            records.append({key: value for key, value in record.items() if value})

        technology_order = {name: index for index, name in enumerate(TECHNOLOGY_NAMES)}
        records.sort(
            key=lambda record: (
                technology_order.get(record.get("technology", ""), len(technology_order)),
                record.get("read_accession", ""),
            )
        )
        return records

    @staticmethod
    def _extract_pacbio_protocols(df: pd.DataFrame) -> list[str]:
        if df.empty:
            return []

        pacbio_df = df[
            (df["library_strategy"].fillna("").astype(str).str.strip().str.upper() == "WGS")
            & (df["instrument_platform"].fillna("").astype(str).str.strip().str.upper() == "PACBIO_SMRT")
        ]
        if pacbio_df.empty:
            return []

        protocols = (
            pacbio_df["library_construction_protocol"]
            .fillna("")
            .astype(str)
            .drop_duplicates()
            .tolist()
        )
        return protocols

    @staticmethod
    def _filter_pacbio_rows_by_tolid(
        read_study_df: pd.DataFrame,
        tolid: str,
        biosample_tolid_map: dict[str, str | None],
    ) -> pd.DataFrame:
        if read_study_df.empty:
            return read_study_df

        is_pacbio = (
            (read_study_df["library_strategy"] == "WGS")
            & (read_study_df["instrument_platform"] == "PACBIO_SMRT")
        )

        def keep_row(row: pd.Series) -> bool:
            if not bool(is_pacbio.loc[row.name]):
                return True
            biosample_id = SequencingService._string_value(row.get("sample_accession"))
            tolid_in_record = biosample_tolid_map.get(biosample_id)
            return tolid_in_record is None or tolid_in_record == tolid

        return read_study_df[read_study_df.apply(keep_row, axis=1)]

    def _assembly_run_accessions(self, assembly_selection: AssemblySelection | None) -> set[str]:
        if assembly_selection is None:
            return set()
        accessions = [
            accession
            for accession in assembly_selection.assembly_accessions().values()
            if accession
        ]
        if not accessions:
            return set()
        fetcher = self.assembly_run_accession_fetcher or self.fetch_service.fetch_assembly_run_accessions
        try:
            return set(fetcher(accessions))
        except Exception as exc:
            logger.warning("Assembly run-accession lookup failed for %s: %s", ", ".join(accessions), exc)
            return set()

    @staticmethod
    def _filter_rows_by_assembly_run_accessions(
        read_study_df: pd.DataFrame,
        assembly_run_accessions: set[str],
    ) -> tuple[pd.DataFrame, list[str]]:
        if read_study_df.empty or not assembly_run_accessions:
            return read_study_df, []

        excluded: list[str] = []

        def keep_row(row: pd.Series) -> bool:
            match = SequencingService._match_technology(row)
            if match is None or match[0] not in {"pacbio", "hic", "chromium"}:
                return True
            run_accession = SequencingService._string_value(row.get("run_accession"))
            if not run_accession or run_accession in assembly_run_accessions:
                return True
            excluded.append(run_accession)
            return False

        filtered = read_study_df[read_study_df.apply(keep_row, axis=1)]
        return filtered, excluded

    @staticmethod
    def _filter_failed_qc_rows(
        read_study_df: pd.DataFrame,
        *,
        protected_run_accessions: set[str] | None = None,
    ) -> tuple[pd.DataFrame, list[str], list[str]]:
        if read_study_df.empty:
            return read_study_df, [], []

        excluded_runs: list[str] = []
        excluded_portal_runs: list[str] = []
        protected = protected_run_accessions or set()

        def keep_row(row: pd.Series) -> bool:
            if not SequencingService._row_has_failed_qc(row):
                return True
            run_accession = SequencingService._string_value(row.get("run_accession"))
            if run_accession and run_accession in protected:
                return True
            portal_run = SequencingService._string_value(row.get("portal_run_id"))
            if run_accession:
                excluded_runs.append(run_accession)
            if portal_run:
                excluded_portal_runs.append(portal_run)
            return False

        filtered = read_study_df[read_study_df.apply(keep_row, axis=1)].reset_index(drop=True)
        return filtered, excluded_runs, excluded_portal_runs

    @staticmethod
    def _row_has_failed_qc(row: pd.Series) -> bool:
        return any(
            SequencingService._is_failed_qc_value(row.get(field_name))
            for field_name in (
                "portal_manual_qc",
                "portal_lims_qc",
                "portal_qc",
                "mlwh_lims_qc",
                "mlwh_qc_seq_state",
            )
        )

    @staticmethod
    def _is_failed_qc_value(value: Any) -> bool:
        text = SequencingService._string_value(value).lower()
        if not text:
            return False
        text = re.sub(r"[^a-z0-9]+", " ", text).strip()
        return text in {"fail", "failed", "qc fail", "qc failed"} or text.startswith("failed ")

    @staticmethod
    def _build_technology_records(df: pd.DataFrame) -> dict[str, TechnologyRecord]:
        records = {name: TechnologyRecord(name=name) for name in TECHNOLOGY_NAMES}
        for _, row in df.iterrows():
            match = SequencingService._match_technology(row)
            if match is None:
                continue
            tech_name, _ = match
            extras = {
                f"{tech_name}_{key}": SequencingService._string_value(row.get(key))
                for key in (
                    "read_count_unit",
                    "read_count_source",
                    "base_count_source",
                    "metadata_source",
                    "supplementary_metadata_source",
                    "run_alias",
                    "experiment_alias",
                    "library_source",
                    "library_selection",
                    "multiplex_identifier",
                    "multiplex_identifier_type",
                    "multiplex_label",
                    "multiplex_source",
                    "sequencing_run",
                    "multiplex_sample",
                    "portal_run_id",
                    "mlwh_library_id",
                    "mlwh_pipeline_id_lims",
                    "mlwh_plex_count",
                    *PORTAL_PREP_FIELDS,
                )
                if SequencingService._string_value(row.get(key))
            }
            plex_count = SequencingService._string_value(row.get("mlwh_plex_count"))
            if plex_count:
                extras[f"{tech_name}_plex_count"] = plex_count
                extras[f"{tech_name}_plex_level"] = f"{plex_count}-plex"
            records[tech_name] = TechnologyRecord(
                name=tech_name,
                sample_accession=SequencingService._string_value(row.get("sample_accession")),
                instrument_model=SequencingService._string_value(row.get("instrument_model")),
                library_construction_protocol=SequencingService._string_value(
                    row.get("library_construction_protocol")
                ),
                library_name=SequencingService._string_value(row.get("library_name")),
                base_count_gb=SequencingService._formatted_base_count_gb(row.get("base_count")),
                read_count_millions=SequencingService._formatted_read_count_millions(row.get("read_count")),
                extras=extras,
            )
        return records

    @staticmethod
    def _build_run_groups(df: pd.DataFrame) -> dict[str, RunGroup]:
        groups = {name: RunGroup(name=name) for name in RUN_GROUP_NAMES}
        for _, row in df.iterrows():
            match = SequencingService._match_technology(row)
            if match is None:
                continue
            _, group_name = match
            extras = {
                key: SequencingService._string_value(row.get(key))
                for key in TEXT_COLUMNS
                if key
                not in {
                    "study_accession",
                    "run_accession",
                    "sample_accession",
                    "instrument_model",
                    "library_strategy",
                    "library_name",
                    "library_construction_protocol",
                    "instrument_platform",
                }
                and SequencingService._string_value(row.get(key))
            }
            groups[group_name].runs.append(
                RunRecord(
                    read_accession=SequencingService._string_value(row.get("run_accession")),
                    sample_accession=SequencingService._string_value(row.get("sample_accession")),
                    fastq_bytes=SequencingService._bytes_gb(row.get("fastq_bytes")),
                    submitted_bytes=SequencingService._bytes_gb(row.get("submitted_bytes")),
                    read_count=SequencingService._scientific_read_count(row.get("read_count")),
                    instrument_model=SequencingService._string_value(row.get("instrument_model")),
                    base_count_gb=SequencingService._run_base_count_gb(row.get("base_count")),
                    extras=extras,
                )
            )
        return groups

    @staticmethod
    def _build_run_accessions(run_groups: dict[str, RunGroup]) -> dict[str, str]:
        accessions: dict[str, str] = {}
        for group_name, prefix in RUN_ACCESSION_GROUPS:
            runs = run_groups.get(group_name, RunGroup(name=group_name)).runs
            run_ids = [run.read_accession for run in runs if run.read_accession]
            accessions[f"{prefix}_run_accessions"] = "; ".join(run_ids)
        return accessions

    @staticmethod
    def _build_totals(
        df: pd.DataFrame,
        technology_records: dict[str, TechnologyRecord],
        *,
        source_accessions: list[str] | None = None,
        portal_result: PortalEnrichmentResult | None = None,
        sequencing_source: str = "public-with-portal",
        illumina_count_unit: str = "read_pairs",
        assembly_run_accessions: set[str] | None = None,
        assembly_filter_excluded_runs: list[str] | None = None,
        qc_filter_excluded_runs: list[str] | None = None,
        qc_filter_excluded_portal_runs: list[str] | None = None,
    ) -> SequencingTotals:
        totals = {
            "pacbio_total_reads": 0,
            "pacbio_total_bases": 0,
            "hic_total_reads": 0,
            "hic_total_bases": 0,
            "chromium_total_reads": 0,
            "chromium_total_bases": 0,
            "rna_total_reads": 0,
            "rna_total_bases": 0,
        }

        for _, row in df.iterrows():
            match = SequencingService._match_technology(row)
            if match is None:
                continue
            tech_name, _ = match
            read_count = SequencingService._numeric_value(row.get("read_count"))
            base_count = SequencingService._numeric_value(row.get("base_count"))
            if tech_name == "pacbio":
                totals["pacbio_total_reads"] += read_count
                totals["pacbio_total_bases"] += base_count
            elif tech_name == "hic":
                totals["hic_total_reads"] += read_count
                totals["hic_total_bases"] += base_count
            elif tech_name == "chromium":
                totals["chromium_total_reads"] += read_count
                totals["chromium_total_bases"] += base_count
            elif tech_name == "rna":
                totals["rna_total_reads"] += read_count
                totals["rna_total_bases"] += base_count

        extras: dict[str, Any] = {
            "sequencing_data_source": sequencing_source,
            "illumina_read_count_unit": illumina_count_unit,
            "sequencing_public_source_accessions": "; ".join(source_accessions or []),
        }
        if assembly_run_accessions:
            extras["sequencing_assembly_run_accession_filter"] = True
            extras["sequencing_assembly_run_accessions"] = "; ".join(sorted(assembly_run_accessions))
            extras["sequencing_assembly_excluded_runs"] = "; ".join(assembly_filter_excluded_runs or [])
        if qc_filter_excluded_runs or qc_filter_excluded_portal_runs:
            extras["sequencing_qc_filter_applied"] = True
            extras["sequencing_qc_excluded_runs"] = "; ".join(qc_filter_excluded_runs or [])
            extras["sequencing_qc_excluded_portal_runs"] = "; ".join(qc_filter_excluded_portal_runs or [])
        for tech_name in ("pacbio", "hic", "chromium", "rna"):
            unit = SequencingService._first_technology_value(df, tech_name, "read_count_unit")
            read_source = SequencingService._first_technology_value(df, tech_name, "read_count_source")
            base_source = SequencingService._first_technology_value(df, tech_name, "base_count_source")
            metadata_source = SequencingService._first_technology_value(df, tech_name, "metadata_source")
            if unit:
                extras[f"{tech_name}_read_count_unit"] = unit
            if read_source:
                extras[f"{tech_name}_read_count_source"] = read_source
            if base_source:
                extras[f"{tech_name}_base_count_source"] = base_source
            if metadata_source:
                extras[f"{tech_name}_metadata_source"] = metadata_source
            for column in ("mlwh_library_id", "mlwh_pipeline_id_lims", *PORTAL_PREP_FIELDS):
                value = SequencingService._first_technology_value(df, tech_name, column)
                if value:
                    extras[f"{tech_name}_{column}"] = value

        if portal_result is not None:
            extras["sequencing_portal_enrichment_applied"] = portal_result.applied
            extras["sequencing_portal_matched_runs"] = "; ".join(portal_result.matched_run_ids)
            extras["sequencing_portal_excluded_runs"] = "; ".join(portal_result.excluded_run_ids)
            extras["sequencing_portal_dropped_public_runs"] = "; ".join(
                portal_result.dropped_public_run_accessions
            )
            extras["sequencing_portal_unmatched_runs"] = "; ".join(portal_result.unmatched_run_ids)
            extras["sequencing_portal_warnings"] = " | ".join(portal_result.warnings)

        pacbio = technology_records.get("pacbio", TechnologyRecord(name="pacbio"))
        hic = technology_records.get("hic", TechnologyRecord(name="hic"))
        chromium = technology_records.get("chromium", TechnologyRecord(name="chromium"))
        rna = technology_records.get("rna", TechnologyRecord(name="rna"))

        return SequencingTotals(
            pacbio_total_reads=format_with_nbsp(totals["pacbio_total_reads"]),
            pacbio_total_bases=format_with_nbsp(totals["pacbio_total_bases"]),
            pacbio_reads_millions=format_with_nbsp(totals["pacbio_total_reads"] / 1e6),
            pacbio_bases_gb=format_with_nbsp(totals["pacbio_total_bases"] / 1e9),
            pacbio_sample_accession=pacbio.sample_accession or "",
            pacbio_instrument=pacbio.instrument_model or "",
            hic_total_reads=format_with_nbsp(totals["hic_total_reads"]),
            hic_total_bases=format_with_nbsp(totals["hic_total_bases"]),
            hic_reads_millions=format_with_nbsp(totals["hic_total_reads"] / 1e6),
            hic_bases_gb=format_with_nbsp(totals["hic_total_bases"] / 1e9),
            hic_sample_accession=hic.sample_accession or "",
            hic_instrument=hic.instrument_model or "",
            chromium_total_reads=format_with_nbsp(totals["chromium_total_reads"]),
            chromium_total_bases=format_with_nbsp(totals["chromium_total_bases"]),
            chromium_reads_millions=format_with_nbsp(totals["chromium_total_reads"] / 1e6),
            chromium_bases_gb=format_with_nbsp(totals["chromium_total_bases"] / 1e9),
            chromium_sample_accession=chromium.sample_accession or "",
            chromium_instrument=chromium.instrument_model or "",
            rna_total_reads=format_with_nbsp(totals["rna_total_reads"]),
            rna_total_bases=format_with_nbsp(totals["rna_total_bases"]),
            rna_reads_millions=format_with_nbsp(totals["rna_total_reads"] / 1e6),
            rna_bases_gb=format_with_nbsp(totals["rna_total_bases"] / 1e9),
            rna_sample_accession=rna.sample_accession or "",
            rna_instrument=rna.instrument_model or "",
            extras=extras,
        )

    @staticmethod
    def _first_technology_value(df: pd.DataFrame, tech_name: str, column: str) -> str:
        if column not in df.columns:
            return ""
        for _, row in df.iterrows():
            match = SequencingService._match_technology(row)
            if match is None or match[0] != tech_name:
                continue
            value = SequencingService._string_value(row.get(column))
            if value:
                return value
        return ""

    @staticmethod
    def _match_technology(row: pd.Series) -> tuple[str, str] | None:
        platform = SequencingService._string_value(row.get("instrument_platform"))
        strategy = SequencingService._string_value(row.get("library_strategy"))
        for expected_platform, expected_strategy, tech_name, group_name in TECHNOLOGY_RULES:
            if platform == expected_platform and strategy == expected_strategy:
                return tech_name, group_name
        return None

    def _normalise_sequencing_source(self) -> str:
        source = (self.sequencing_source or "public-with-portal").strip().lower().replace("_", "-")
        if source in {"public", "public-only"}:
            return "public"
        if source in {"portal", "portal-only", "portal-priority"}:
            return "portal"
        return "public-with-portal"

    def _normalise_illumina_count_unit(self) -> str:
        unit = (self.illumina_count_unit or "read_pairs").strip().lower().replace("-", "_")
        if unit in {"reads", "read", "individual_reads"}:
            return "reads"
        return "read_pairs"

    @classmethod
    def _is_paired_illumina(cls, row: pd.Series) -> bool:
        platform = cls._string_value(row.get("instrument_platform"))
        if platform != "ILLUMINA":
            return False
        layout = cls._string_value(row.get("library_layout")).upper()
        strategy = cls._string_value(row.get("library_strategy"))
        basis = cls._string_value(row.get("read_count_basis")).lower()
        return layout == "PAIRED" or strategy == "Hi-C" or (strategy == "RNA-Seq" and basis == "reads")

    @staticmethod
    def _string_value(value: Any) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, str) and value.strip().lower() in {"nan", "none"}:
            return ""
        if isinstance(value, Real) and float(value).is_integer():
            return str(int(value))
        if isinstance(value, str) and value.endswith(".0"):
            try:
                numeric = float(value)
            except ValueError:
                return value
            if numeric.is_integer():
                return str(int(numeric))
        return str(value)

    @staticmethod
    def _numeric_value(value: Any) -> float:
        if pd.isna(value):
            return 0.0
        return float(value)

    @staticmethod
    def _numeric_total(value: Any) -> int:
        if pd.isna(value):
            return 0
        if isinstance(value, Real):
            return int(float(value))

        text = str(value).strip()
        if not text or text.lower() in {"nan", "none"}:
            return 0

        total = 0.0
        for part in text.split(";"):
            part = part.strip().replace(",", "")
            if not part:
                continue
            try:
                total += float(part)
            except ValueError:
                continue
        return int(total)

    @staticmethod
    def _formatted_base_count_gb(value: Any) -> str:
        numeric = 0 if pd.isna(value) else value
        return format_with_nbsp(round((float(numeric)) / 1e9, 2))

    @staticmethod
    def _formatted_read_count_millions(value: Any) -> str:
        numeric = 0 if pd.isna(value) else value
        return format_with_nbsp(round((float(numeric)) / 1e6, 2))

    @staticmethod
    def _run_base_count_gb(value: Any) -> str:
        numeric = 0 if pd.isna(value) else value
        return str(round((float(numeric)) / 1e9, 2))

    @staticmethod
    def _bytes_gb(value: Any) -> str:
        numeric = 0 if pd.isna(value) else value
        return str(round(bytes_to_gb(numeric), 2))

    @staticmethod
    def _scientific_read_count(value: Any) -> str:
        numeric = 0 if pd.isna(value) else value
        return str(format_scientific(float(numeric)))
