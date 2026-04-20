from __future__ import annotations

import pandas as pd

from .services.sequencing_fetch_service import DEFAULT_SEQUENCING_FETCH_SERVICE


def fetch_read_runs_for_bioproject(bioproject: str):
    """Compatibility wrapper around the sequencing fetch service."""
    return DEFAULT_SEQUENCING_FETCH_SERVICE.fetch_read_runs_for_bioproject(bioproject)


def fetch_read_runs_for_bioprojects(bioprojects):
    """Compatibility wrapper around the sequencing fetch service."""
    return (
        pd.DataFrame([row for bp in bioprojects for row in fetch_read_runs_for_bioproject(bp)])
        if bioprojects
        else pd.DataFrame()
    )


def fetch_runinfo_rows_for_accession(accession: str):
    """Compatibility wrapper around the sequencing fetch service."""
    return DEFAULT_SEQUENCING_FETCH_SERVICE.fetch_runinfo_rows_for_accession(accession)


def fetch_sra_summary_rows_for_accession(accession: str):
    """Compatibility wrapper around the sequencing fetch service."""
    return DEFAULT_SEQUENCING_FETCH_SERVICE.fetch_sra_summary_rows_for_accession(accession)


def fetch_runinfo_for_bioprojects(bioprojects):
    """Compatibility wrapper around the sequencing fetch service."""
    return DEFAULT_SEQUENCING_FETCH_SERVICE.fetch_for_bioprojects(list(bioprojects))


def fetch_experiment_protocol(experiment_accession: str):
    """Compatibility wrapper around the sequencing fetch service."""
    return DEFAULT_SEQUENCING_FETCH_SERVICE.fetch_experiment_protocol(experiment_accession)
