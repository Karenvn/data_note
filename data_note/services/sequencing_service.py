from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from ..fetch_biosample_info import get_biosample_tolid_map
from ..models import SequencingSummary
from ..process_sequencing_info import (
    check_pacbio_protocol,
    extract_technology_data,
    fetch_runinfo_for_bioprojects,
    filter_pacbio_rows_by_tolid,
    get_run_accession_lists,
    organise_sequencing_data,
    select_columns,
    summarise_sequencing_totals,
)


@dataclass(slots=True)
class SequencingService:
    runinfo_fetcher: Callable[[list[str]], pd.DataFrame] = fetch_runinfo_for_bioprojects
    biosample_tolid_getter: Callable[[list[str]], dict[str, str | None]] = get_biosample_tolid_map
    pacbio_filter: Callable[[pd.DataFrame, str, dict[str, str | None]], pd.DataFrame] = filter_pacbio_rows_by_tolid
    columns_selector: Callable[[pd.DataFrame], pd.DataFrame] = select_columns
    technology_extractor: Callable[[pd.DataFrame], dict[str, Any]] = extract_technology_data
    sequencing_organiser: Callable[[pd.DataFrame], dict[str, Any]] = organise_sequencing_data
    totals_summariser: Callable[[pd.DataFrame, dict[str, Any]], dict[str, Any]] = summarise_sequencing_totals
    pacbio_protocol_checker: Callable[[pd.DataFrame], list[str]] = check_pacbio_protocol
    run_accession_getter: Callable[[dict[str, Any]], dict[str, str]] = get_run_accession_lists

    def empty_context(self) -> SequencingSummary:
        empty_df = self.columns_selector(self._empty_dataframe())
        technology_data = self.technology_extractor(empty_df)
        seq_data = self.sequencing_organiser(empty_df)
        totals = self.totals_summariser(empty_df, technology_data)
        run_accessions = self.run_accession_getter(seq_data)
        return SequencingSummary.from_legacy_parts(
            technology_data=technology_data,
            seq_data=seq_data,
            totals=totals,
            pacbio_protocols=[],
            run_accessions=run_accessions,
        )

    def build_context(self, bioprojects: Any, tolid: str) -> SequencingSummary:
        bioproject_list = self._normalise_bioprojects(bioprojects)

        print(f"Processing sequencing information for bioproject(s): {', '.join(bioproject_list)}.")
        read_study_df = self.runinfo_fetcher(bioproject_list)
        if read_study_df.empty:
            raise RuntimeError(
                f"No SRA RunInfo rows found for BioProjects: {', '.join(bioproject_list)}"
            )

        print("Here is the read_study_df")
        print(read_study_df)
        if read_study_df.empty:
            print("No run records returned for any study accessions.")
            raise RuntimeError(
                f"No run records returned for BioProjects: {', '.join(bioproject_list)}"
            )
        if "sample_accession" not in read_study_df.columns:
            print("Missing sample_accession in read study data.")
            raise RuntimeError(
                f"Missing sample_accession for BioProjects: {', '.join(bioproject_list)}"
            )

        biosample_ids = read_study_df["sample_accession"].dropna().unique().tolist()
        biosample_tolid_map = self.biosample_tolid_getter(biosample_ids)
        read_study_df = self.pacbio_filter(read_study_df, tolid, biosample_tolid_map)
        technology_df = self.columns_selector(read_study_df)
        technology_data = self.technology_extractor(technology_df)
        seq_data = self.sequencing_organiser(technology_df)
        totals = self.totals_summariser(technology_df, technology_data)

        pacbio_protocols = self.pacbio_protocol_checker(technology_df)

        run_accessions = self.run_accession_getter(seq_data)
        return SequencingSummary.from_legacy_parts(
            technology_data=technology_data,
            seq_data=seq_data,
            totals=totals,
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
            columns=[
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
            ]
        )
