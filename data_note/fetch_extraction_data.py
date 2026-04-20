#!/usr/bin/env python

"""
Requires tol-sdk version ≥1.6.28
Script to fetch extraction attributes from the ToL Portal.
sanger_sample_id is the library name in the sequencing data

"""
import logging
import os
import pandas as pd
from pathlib import Path
from .formatting_utils import format_with_nbsp, format_kb

try:
    from tol.sources.portal import portal
    from tol.core import DataSourceFilter
except ImportError:
    portal = None
    DataSourceFilter = None


PORTAL_API_PATH_DEFAULT = "/api/v1"
logger = logging.getLogger(__name__)


def _portal_datasource():
    if portal is None:
        logger.info("tol-sdk is not installed; skipping ToL Portal lookup.")
        return None

    os.environ.setdefault("PORTAL_API_PATH", os.getenv("PORTAL_API_PATH", PORTAL_API_PATH_DEFAULT))
    try:
        return portal()
    except Exception as exc:
        logger.warning("ToL Portal lookup unavailable: %s", exc)
        return None

def _normalize_identifier(value):
    if value is None:
        return ""
    return str(value).strip()


def _latest_by_completion(records):
    def _key(obj):
        attrs = obj.attributes or {}
        completion = attrs.get("benchling_completion_date")
        return (completion is not None, completion)

    return max(records, key=_key)


def _first_result(ds, object_name, object_filters):
    results = list(ds.get_list(object_name, object_filters=object_filters))
    if not results:
        return None
    if len(results) == 1:
        return results[0]
    return _latest_by_completion(results)


def _get_extraction_by_uid(ds, extraction_uid):
    extraction_uid = _normalize_identifier(extraction_uid)
    if not extraction_uid:
        return None
    f = DataSourceFilter()
    f.and_ = {"uid": {"eq": {"value": extraction_uid}}}
    return _first_result(ds, "extraction", f)


def _get_extraction_by_tolid(ds, tolid):
    tolid = _normalize_identifier(tolid)
    if not tolid:
        return None
    f = DataSourceFilter()
    f.and_ = {"benchling_tolid.id": {"eq": {"value": tolid, "negate": False}}}
    return _first_result(ds, "extraction", f)


def _get_extraction_by_sample_id(ds, sample_id):
    sample_id = _normalize_identifier(sample_id)
    if not sample_id:
        return None
    f = DataSourceFilter()
    f.and_ = {"benchling_sample.id": {"eq": {"value": sample_id, "negate": False}}}
    return _first_result(ds, "extraction", f)


def _get_sequencing_request(ds, identifier):
    identifier = _normalize_identifier(identifier)
    if not identifier:
        return None

    # First try direct sequencing request UID (e.g. DTOL14810540).
    f = DataSourceFilter()
    f.and_ = {"uid": {"eq": {"value": identifier}}}
    seq_request = _first_result(ds, "sequencing_request", f)
    if seq_request:
        return seq_request

    # Then try ToLID-based lookup (e.g. icGryEqui2).
    f = DataSourceFilter()
    f.and_ = {"benchling_tolid.id": {"eq": {"value": identifier, "negate": False}}}
    return _first_result(ds, "sequencing_request", f)


def _get_extraction_from_sequencing_request(ds, seq_request):
    to_one = getattr(seq_request, "to_one_relationships", {}) or {}

    extraction_rel = to_one.get("benchling_extraction")
    if extraction_rel and getattr(extraction_rel, "id", None):
        extraction = _get_extraction_by_uid(ds, extraction_rel.id)
        if extraction:
            return extraction

    tolid_rel = to_one.get("benchling_tolid")
    if tolid_rel and getattr(tolid_rel, "id", None):
        extraction = _get_extraction_by_tolid(ds, tolid_rel.id)
        if extraction:
            return extraction

    sample_rel = to_one.get("benchling_sample")
    if sample_rel and getattr(sample_rel, "id", None):
        extraction = _get_extraction_by_sample_id(ds, sample_rel.id)
        if extraction:
            return extraction

    return None


def _extract_extraction_attrs(extraction):
    raw_attrs = extraction.attributes.copy()

    desired_fields = [
        "benchling_extraction_protocol",
        "benchling_yield_ng",
        "benchling_volume_ul",
        "benchling_qubit_concentration_ngul",
        "benchling_dna_260_280_ratio",
        "benchling_dna_260_230_ratio",
        "benchling_completion_date",
        "benchling_manual_vs_automatic",
        "benchling_gqn_index",
    ]
    extraction_attrs = {k: raw_attrs[k] for k in desired_fields if k in raw_attrs}
    extraction_attrs["extraction_uid"] = extraction.id

    # Tissue mass lives on the related tissue_prep object (not extraction itself).
    tissue_prep = extraction.to_one_relationships.get("benchling_tissue_prep")
    if tissue_prep:
        tp_attrs = tissue_prep.attributes or {}
        extraction_attrs["tissue_weight_mg"] = tp_attrs.get("benchling_weight_mg")
        extraction_attrs["tissue_weight_mg_calc"] = tp_attrs.get("calc_benchling_weight_mg")
        extraction_attrs["tissue_prep_uid"] = tissue_prep.id

    # Optional context from sample (not extraction-specific).
    sample = extraction.to_one_relationships.get("benchling_sample")
    if sample:
        s_attrs = sample.attributes or {}
        extraction_attrs["tissue_size_in_tube"] = s_attrs.get("benchling_size_of_tissue_in_tube")
        extraction_attrs["tissue_remaining_weight"] = s_attrs.get("benchling_remaining_weight")
        extraction_attrs["tissue_remaining_weight_calc"] = s_attrs.get("calc_benchling_remaining_weight")
        extraction_attrs["tissue_size"] = s_attrs.get("sts_tissue_size")
        extraction_attrs["tissue_remaining"] = s_attrs.get("sts_tissue_remaining")
        extraction_attrs["tissue_depleted"] = s_attrs.get("sts_tissue_depleted")

    return {
        "extraction_protocol": extraction_attrs.get("benchling_extraction_protocol"),
        "protocol": extraction_attrs.get("benchling_extraction_protocol"),
        "dna_yield_ng": format_with_nbsp(extraction_attrs.get("benchling_yield_ng")),
        "volume_ul": extraction_attrs.get("benchling_volume_ul"),
        "qubit_ngul": extraction_attrs.get("benchling_qubit_concentration_ngul"),
        "ratio_260_280": extraction_attrs.get("benchling_dna_260_280_ratio"),
        "ratio_260_230": extraction_attrs.get("benchling_dna_260_230_ratio"),
        "extraction_date": extraction_attrs.get("benchling_completion_date"),
        "extraction_mode": extraction_attrs.get("benchling_manual_vs_automatic"),
        "extraction_uid": extraction_attrs.get("extraction_uid"),
        "gqn": extraction_attrs.get("benchling_gqn_index"),
        "tissue_weight_mg": extraction_attrs.get("tissue_weight_mg"),
        "tissue_weight_mg_calc": extraction_attrs.get("tissue_weight_mg_calc"),
        "tissue_prep_uid": extraction_attrs.get("tissue_prep_uid"),
        "tissue_size_in_tube": extraction_attrs.get("tissue_size_in_tube"),
        "tissue_remaining_weight": extraction_attrs.get("tissue_remaining_weight"),
        "tissue_remaining_weight_calc": extraction_attrs.get("tissue_remaining_weight_calc"),
        "tissue_size": extraction_attrs.get("tissue_size"),
        "tissue_remaining": extraction_attrs.get("tissue_remaining"),
        "tissue_depleted": extraction_attrs.get("tissue_depleted"),
    }


def get_sequencing_and_extraction_metadata(sanger_sample_id):
    sanger_sample_id = _normalize_identifier(sanger_sample_id)

    seq_attrs_renamed = {}
    extraction_attrs_renamed = {}
    ds = _portal_datasource()
    if ds is None:
        return seq_attrs_renamed, extraction_attrs_renamed

    if not sanger_sample_id:
        return seq_attrs_renamed, extraction_attrs_renamed

    # --- Step 1: Try extraction directly ---
    extraction = _get_extraction_by_uid(ds, sanger_sample_id)
    if extraction:
        logger.info("Input matches an extraction UID directly.")
        extraction_attrs_renamed = _extract_extraction_attrs(extraction)
        return seq_attrs_renamed, extraction_attrs_renamed

    # --- Step 2: Try sequencing_request ---
    seq_request = _get_sequencing_request(ds, sanger_sample_id)
    if seq_request:
        seq_attrs = seq_request.attributes.copy() if seq_request.attributes else {}
        seq_attrs_renamed = {
            "sequencing_date": seq_attrs.get("benchling_completion_date"),
            "platform": seq_attrs.get("benchling_sequencing_platform"),
            "submission_id": seq_attrs.get("benchling_submission_sample_id"),
            "submission_name": seq_attrs.get("benchling_submission_sample_name"),
            "estimated_max_oplc": seq_attrs.get("lrpacbio_estimated_max_oplc"),
            "library_remaining": seq_attrs.get("lrpacbio_library_remaining"),
            "library_remaining_oplc": seq_attrs.get("lrpacbio_library_remaining_oplc"),
            "portion_of_cell": seq_attrs.get("lrpacbio_portion_of_cell"),
            "pacbio_run_count": seq_attrs.get("mlwh_run_data_pacbio_count"),
            "sanger_sample_id": seq_attrs.get("uid") or seq_request.id,
        }
        extraction = _get_extraction_from_sequencing_request(ds, seq_request)
        if extraction:
            extraction_attrs_renamed = _extract_extraction_attrs(extraction)

    # --- Step 3: Final fallback by ToLID ---
    if not extraction_attrs_renamed:
        extraction = _get_extraction_by_tolid(ds, sanger_sample_id)
        if extraction:
            extraction_attrs_renamed = _extract_extraction_attrs(extraction)

    return seq_attrs_renamed, extraction_attrs_renamed


def fallback_fetch_from_lr_sample_prep(sanger_sample_id, tsv_path=None):
    """
    Fallback to fetching extraction info from LR_sample_prep.tsv if Portal has no usable data.
    """
    if tsv_path is None:
        tsv_path = os.getenv("DATA_NOTE_LR_SAMPLE_PREP_TSV", "~/genome_note_templates/LR_sample_prep.tsv")

    # Normalize path: strip accidental quotes and expand "~"
    tsv_path = str(tsv_path).strip().strip('"').strip("'")
    tsv_file = Path(tsv_path).expanduser()
    if not tsv_file.exists():
        # Fallback to CWD if only a filename was intended
        candidate = Path.cwd() / Path(tsv_path).name
        if candidate.exists():
            tsv_file = candidate
        else:
            logger.warning("TSV file not found. Tried: %s and %s", tsv_file, candidate)
            return {}

    df = pd.read_csv(tsv_file, sep="\t")
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[^\w_]", "", regex=True)  # optional: remove punctuation
)

    df["sanger_sample_id"] = df["sanger_sample_id"].astype(str).str.strip().str.upper()
    sanger_sample_id = sanger_sample_id.strip().upper()

    match = df[df["sanger_sample_id"] == sanger_sample_id]

    if match.empty:
        logger.warning("Sanger sample ID %s not found in %s.", sanger_sample_id, tsv_path)
        return {}
    
    row = match.iloc[0]

    protocol_value = row.get("extraction_protocolkit_version")
    extracted_data = {
    "qubit_ngul": row.get("qubit_quant_ngul_esp2"),
    "dna_yield_ng": format_with_nbsp(row.get("total_dna_ng_esp2")),
    "volume_ul": row.get("final_elution_volume_ul"),
    "ratio_260_280": row.get("nd_260280_esp2"),
    "ratio_260_230": row.get("nd_260230_esp2"),
    "nanodrop_concentration_ngul": row.get("nd_quant_ngul_esp1"),
    "extraction_date": row.get("ext_date_started"),
    "fragment_size_kb": format_kb(row.get("femto_fragment_size_esp2")),
    "gqn": row.get("gqn_10kb_threshold_esp2") or row.get("gqn_30000_esp1"),
    "extraction_protocol": protocol_value,
    "protocol": protocol_value,
    "spri_type": row.get("spri_type"),
    "disruption_method": row.get("crush_method")
    }

    #print(extracted_data)  # debugging
    return extracted_data



def fetch_barcoding_info(tolid):
    """
    Fetches information about the sample including whether tissue was removed for barcoding, and the sample_set_id
    """
    barcode_dict = {
        "sts_tremoved": None,
        "barcode_hub": None,
        "eln_id": None,
        "sample_set_id": None,
    }

    ds = _portal_datasource()
    if ds is None:
        return barcode_dict

    f = DataSourceFilter()
    f.and_ = {"benchling_tolid.id": {"eq": {"value": tolid, "negate": False}}}

    samples = list(ds.get_list("sample", object_filters=f))

    if samples:
        sample = samples[0]
        attrs = sample.attributes
        barcode_dict["sts_tremoved"] = attrs.get("sts_tremoved")
        barcode_dict["barcode_hub"] = attrs.get("sts_barcode_hub")
        barcode_dict["eln_id"] = attrs.get("sts_eln_id")
        barcode_dict["sample_set_id"] = attrs.get("benchling_sample_set_id")

    return barcode_dict
