from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable

import pandas as pd

from ..fetch_biosample_info import get_biosample_tolid_map
from ..formatting_utils import format_with_nbsp
from ..formatting_utils import bytes_to_gb, format_scientific
from ..models import RunGroup, RunRecord, SequencingSummary, SequencingTotals, TechnologyRecord
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
    ("RNA", "rna"),
)
NUMERIC_COLUMNS: tuple[str, ...] = ("fastq_bytes", "submitted_bytes", "read_count", "base_count")
TEXT_COLUMNS: tuple[str, ...] = (
    "study_accession",
    "run_accession",
    "sample_accession",
    "instrument_model",
    "library_strategy",
    "library_name",
    "library_construction_protocol",
    "instrument_platform",
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


@dataclass(slots=True)
class SequencingService:
    fetch_service: SequencingFetchService = field(default_factory=SequencingFetchService)
    biosample_tolid_getter: Callable[[list[str]], dict[str, str | None]] = get_biosample_tolid_map

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
        )

    def build_context(self, bioprojects: Any, tolid: str) -> SequencingSummary:
        bioproject_list = self._normalise_bioprojects(bioprojects)

        logger.info(
            "Processing sequencing information for bioproject(s): %s.",
            ", ".join(bioproject_list),
        )
        read_study_df = self.fetch_service.fetch_for_bioprojects(bioproject_list)
        if read_study_df.empty:
            raise RuntimeError(
                f"No SRA RunInfo rows found for BioProjects: {', '.join(bioproject_list)}"
            )

        if "sample_accession" not in read_study_df.columns:
            raise RuntimeError(
                f"Missing sample_accession for BioProjects: {', '.join(bioproject_list)}"
            )

        biosample_ids = read_study_df["sample_accession"].dropna().unique().tolist()
        biosample_tolid_map = self.biosample_tolid_getter(biosample_ids)
        read_study_df = self._filter_pacbio_rows_by_tolid(read_study_df, tolid, biosample_tolid_map)
        technology_df = self._select_columns(read_study_df)
        technology_records = self._build_technology_records(technology_df)
        run_groups = self._build_run_groups(technology_df)

        pacbio_protocols = self._extract_pacbio_protocols(technology_df)

        run_accessions = self._build_run_accessions(run_groups)
        return SequencingSummary(
            technology_records=technology_records,
            run_groups=run_groups,
            totals=self._build_totals(technology_df, technology_records),
            pacbio_protocols=pacbio_protocols,
            run_accessions=run_accessions,
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
            normalised[column] = pd.to_numeric(normalised[column], errors="coerce").fillna(0).astype(int)

        for column in TEXT_COLUMNS:
            if column not in normalised.columns:
                normalised[column] = ""
            else:
                normalised[column] = normalised[column].fillna("").astype(str)

        return normalised.loc[:, SEQUENCING_COLUMNS]

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

    @staticmethod
    def _build_technology_records(df: pd.DataFrame) -> dict[str, TechnologyRecord]:
        records = {name: TechnologyRecord(name=name) for name in TECHNOLOGY_NAMES}
        for _, row in df.iterrows():
            match = SequencingService._match_technology(row)
            if match is None:
                continue
            tech_name, _ = match
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
            groups[group_name].runs.append(
                RunRecord(
                    read_accession=SequencingService._string_value(row.get("run_accession")),
                    sample_accession=SequencingService._string_value(row.get("sample_accession")),
                    fastq_bytes=SequencingService._bytes_gb(row.get("fastq_bytes")),
                    submitted_bytes=SequencingService._bytes_gb(row.get("submitted_bytes")),
                    read_count=SequencingService._scientific_read_count(row.get("read_count")),
                    instrument_model=SequencingService._string_value(row.get("instrument_model")),
                    base_count_gb=SequencingService._run_base_count_gb(row.get("base_count")),
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
    def _build_totals(df: pd.DataFrame, technology_records: dict[str, TechnologyRecord]) -> SequencingTotals:
        totals = {
            "pacbio_total_reads": 0,
            "pacbio_total_bases": 0,
            "hic_total_reads": 0,
            "hic_total_bases": 0,
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
            elif tech_name == "rna":
                totals["rna_total_reads"] += read_count
                totals["rna_total_bases"] += base_count

        pacbio = technology_records.get("pacbio", TechnologyRecord(name="pacbio"))
        hic = technology_records.get("hic", TechnologyRecord(name="hic"))
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
            rna_total_reads=format_with_nbsp(totals["rna_total_reads"]),
            rna_total_bases=format_with_nbsp(totals["rna_total_bases"]),
            rna_reads_millions=format_with_nbsp(totals["rna_total_reads"] / 1e6),
            rna_bases_gb=format_with_nbsp(totals["rna_total_bases"] / 1e9),
            rna_sample_accession=rna.sample_accession or "",
            rna_instrument=rna.instrument_model or "",
        )

    @staticmethod
    def _match_technology(row: pd.Series) -> tuple[str, str] | None:
        platform = SequencingService._string_value(row.get("instrument_platform"))
        strategy = SequencingService._string_value(row.get("library_strategy"))
        for expected_platform, expected_strategy, tech_name, group_name in TECHNOLOGY_RULES:
            if platform == expected_platform and strategy == expected_strategy:
                return tech_name, group_name
        return None

    @staticmethod
    def _string_value(value: Any) -> str:
        if pd.isna(value):
            return ""
        return str(value)

    @staticmethod
    def _numeric_value(value: Any) -> float:
        if pd.isna(value):
            return 0.0
        return float(value)

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
