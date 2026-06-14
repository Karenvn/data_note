#!/usr/bin/env python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

import pandas as pd

from data_note.fetch_extraction_data import (
    _resolve_lr_sample_prep_tsv,
    get_sequencing_and_extraction_metadata,
)
from data_note.models.assembly import AssemblyRecord, AssemblySelection
from data_note.services.sequencing_service import SequencingService


ASSEMBLY_INFORMATICS_TSV = (
    "https://docs.google.com/spreadsheets/d/"
    "1RKubj10g13INd4W7alHkwcSVX_0CRvNq0-SRe21m-GM/export?format=tsv&gid=1442224132"
)


@dataclass(frozen=True)
class FieldSpec:
    concept: str
    field_name: str
    public_label: str = ""
    portal_label: str = ""
    lr_label: str = ""
    public_getter: Callable[[dict[str, Any]], Any] | None = None
    portal_getter: Callable[[dict[str, Any]], Any] | None = None
    lr_getter: Callable[[dict[str, Any]], Any] | None = None
    compare_mode: str = "text"
    relationship_sensitive: bool = True
    note: str = ""


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value).strip().replace("\u00a0", " ")
    if text.lower() in {"", "nan", "none", "nat"}:
        return ""
    if re.fullmatch(r"-?\d+\.0", text):
        return text[:-2]
    return text


def value_from(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean_value(mapping.get(key))
        if value:
            return value
    return ""


def format_parts(parts: list[tuple[str, Any]]) -> str:
    present = [(label, clean_value(value)) for label, value in parts if clean_value(value)]
    return "; ".join(f"{label}: {value}" for label, value in present)


def normalise_text(value: Any) -> str:
    text = clean_value(value).lower()
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("automated", "automatic")
    return text


def numeric_value(value: Any, *, unit: str = "") -> float | None:
    text = clean_value(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match is None:
        return None
    number = float(match.group(0))
    if unit == "bp" and re.search(r"\bkb\b", text, flags=re.IGNORECASE):
        number *= 1000
    elif unit == "bp" and abs(number) < 500:
        # data_note formats this field as kb, while LR stores the raw bp value.
        number *= 1000
    return number


def values_match(public_value: str, portal_value: str, lr_value: str, mode: str) -> bool:
    populated = [value for value in (public_value, portal_value, lr_value) if clean_value(value)]
    if len(populated) < 2:
        return False

    if mode == "run_id":
        first, *rest = [normalise_text(value) for value in populated]
        return all(first == other or first in other or other in first for other in rest)

    if mode in {"number", "bp"}:
        unit = "bp" if mode == "bp" else ""
        numbers = [numeric_value(value, unit=unit) for value in populated]
        if any(number is None for number in numbers):
            return False
        assert all(number is not None for number in numbers)
        first = numbers[0]
        return all(
            abs(first - number) <= max(0.05, abs(first) * 0.01)
            for number in numbers[1:]
        )

    normalised = [normalise_text(value) for value in populated]
    return len(set(normalised)) == 1


def compare_status(
    *,
    public_value: str,
    portal_value: str,
    lr_value: str,
    mode: str,
    relationship_unclear: bool,
    relationship_sensitive: bool,
) -> str:
    public_present = bool(clean_value(public_value))
    portal_present = bool(clean_value(portal_value))
    lr_present = bool(clean_value(lr_value))

    if relationship_unclear and relationship_sensitive and portal_present and lr_present:
        return "relationship_unclear"
    if not public_present and not portal_present and not lr_present:
        return "missing"
    if portal_present and not lr_present and not public_present:
        return "portal_only"
    if lr_present and not portal_present and not public_present:
        return "lr_only"
    if public_present and not portal_present and not lr_present:
        return "public_only"
    if values_match(public_value, portal_value, lr_value, mode):
        return "match"
    return "conflict"


def normalise_column_name(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^\w]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def load_lr_rows(path: str | None) -> tuple[pd.DataFrame, dict[str, str], str]:
    tsv_path = _resolve_lr_sample_prep_tsv(path)
    if tsv_path is None:
        return pd.DataFrame(), {}, ""

    raw = pd.read_csv(tsv_path, sep="\t")
    original_for: dict[str, str] = {}
    columns = []
    for column in raw.columns:
        normalised = normalise_column_name(column)
        original_for[normalised] = column
        columns.append(normalised)
    raw.columns = columns
    return raw, original_for, str(tsv_path)


def lr_find(
    lr_df: pd.DataFrame,
    *,
    lookup_id: str,
    tolid: str,
    allow_tolid_fallback: bool,
) -> tuple[dict[str, Any], str]:
    if lr_df.empty:
        return {}, ""

    lookup_id = clean_value(lookup_id).upper()
    tolid = clean_value(tolid).upper()

    candidate_columns = [
        column
        for column in ("sanger_sample_id", "tol_id", "to_l_id", "tolid")
        if column in lr_df.columns
    ]

    if lookup_id:
        for column in candidate_columns:
            series = lr_df[column].astype(str).str.strip().str.upper()
            matches = lr_df[series == lookup_id]
            if not matches.empty:
                return matches.iloc[0].to_dict(), f"library:{column}"

    if allow_tolid_fallback and tolid:
        for column in candidate_columns:
            series = lr_df[column].astype(str).str.strip().str.upper()
            matches = lr_df[series == tolid]
            if not matches.empty:
                return matches.iloc[0].to_dict(), f"tolid:{column}"

    return {}, ""


def lr_tolid_candidate_ids(lr_df: pd.DataFrame, tolid: str) -> str:
    if lr_df.empty or "sanger_sample_id" not in lr_df.columns:
        return ""
    tolid = clean_value(tolid).upper()
    candidate_columns = [column for column in ("tol_id", "to_l_id", "tolid") if column in lr_df.columns]
    if not tolid or not candidate_columns:
        return ""
    matches = pd.DataFrame()
    for column in candidate_columns:
        series = lr_df[column].astype(str).str.strip().str.upper()
        matches = lr_df[series == tolid]
        if not matches.empty:
            break
    if matches.empty:
        return ""
    ids = [clean_value(value) for value in matches["sanger_sample_id"].tolist()]
    return "; ".join(value for value in ids if value)


def lr_value(row: dict[str, Any], *keys: str) -> str:
    return value_from(row, *keys)


def make_assembly_selection(accession: str, tolid: str) -> AssemblySelection | None:
    accession = clean_value(accession)
    if not accession:
        return None
    return AssemblySelection(
        assemblies_type="prim_alt",
        primary=AssemblyRecord(accession=accession, assembly_name=tolid, role="primary"),
    )


def run_alias_matches(public_run_alias: str, mlwh_run_id: str) -> bool:
    public_run_alias = clean_value(public_run_alias)
    mlwh_run_id = clean_value(mlwh_run_id)
    return bool(public_run_alias and mlwh_run_id and mlwh_run_id in public_run_alias)


def build_field_specs() -> list[FieldSpec]:
    return [
        FieldSpec(
            "Identity/linkage",
            "run_id",
            public_label="ENA run alias",
            portal_label="MLWH run id",
            public_getter=lambda c: c.get("public_run_alias"),
            portal_getter=lambda c: c.get("mlwh_run_id"),
            compare_mode="run_id",
            relationship_sensitive=False,
            note="Public run alias should contain the MLWH run id for PacBio.",
        ),
        FieldSpec(
            "Identity/linkage",
            "library_id",
            public_label="ENA library name",
            portal_label="MLWH library id",
            lr_label="LR Sanger sample ID",
            public_getter=lambda c: c.get("public_library_id"),
            portal_getter=lambda c: c.get("portal_library_id"),
            lr_getter=lambda c: lr_value(c["lr_row"], "sanger_sample_id"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "Sample used",
            "tissue_tube_id",
            portal_label="Portal tissue prep FluidX",
            lr_label="LR Tissue Tube ID",
            portal_getter=lambda c: value_from(
                c["row"],
                "portal_tissue_prep_fluidx_id",
                "portal_sample_tissue_fluidx_id",
            ),
            lr_getter=lambda c: lr_value(c["lr_row"], "tissue_tube_id"),
        ),
        FieldSpec(
            "Tissue used",
            "tissue_type",
            portal_label="Portal organism part/tissue prep type",
            lr_label="LR Tissue Type",
            portal_getter=lambda c: value_from(
                c["row"],
                "portal_sample_organism_part",
                "portal_tissue_prep_type",
                "tissue_prep_type",
            ),
            lr_getter=lambda c: lr_value(c["lr_row"], "tissue_type"),
        ),
        FieldSpec(
            "Amount of tissue used",
            "tissue_mass_mg",
            portal_label="Portal benchling_weight_of_prep_for_dna",
            lr_label="LR Tissue Mass (mg)",
            portal_getter=lambda c: value_from(
                c["row"],
                "portal_tissue_prep_weight_of_prep_for_dna",
                "tissue_weight_mg",
            ),
            lr_getter=lambda c: lr_value(c["lr_row"], "tissue_mass_mg"),
            compare_mode="number",
        ),
        FieldSpec(
            "Disruption / homogenisation",
            "disruption_method",
            portal_label="Portal tissue prep disruption method",
            lr_label="LR Crush Method",
            portal_getter=lambda c: value_from(
                c["row"],
                "portal_tissue_prep_disruption_method",
                "disruption_method",
            ),
            lr_getter=lambda c: lr_value(c["lr_row"], "crush_method"),
        ),
        FieldSpec(
            "HMW extraction",
            "extraction_protocol",
            portal_label="Portal extraction protocol",
            lr_label="LR Extraction Protocol/Kit version",
            portal_getter=lambda c: value_from(
                c["row"],
                "portal_extraction_protocol",
                "extraction_protocol",
            ),
            lr_getter=lambda c: lr_value(c["lr_row"], "extraction_protocol_kit_version"),
        ),
        FieldSpec(
            "HMW extraction",
            "extraction_mode",
            portal_label="Portal manual/automatic mode",
            portal_getter=lambda c: value_from(c["row"], "portal_extraction_mode", "extraction_mode"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "HMW extraction",
            "extraction_date",
            portal_label="Portal extraction completion date",
            lr_label="LR EXT Date Started",
            portal_getter=lambda c: value_from(c["row"], "portal_extraction_date", "extraction_date"),
            lr_getter=lambda c: lr_value(c["lr_row"], "ext_date_started"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "HMW extraction",
            "extraction_qc",
            portal_label="Portal extraction QC result",
            lr_label="LR TOL DECISION [ESP1]",
            portal_getter=lambda c: value_from(c["row"], "portal_extraction_qc_result", "extraction_qc_result"),
            lr_getter=lambda c: lr_value(c["lr_row"], "tol_decision_esp1"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "DNA yield",
            "dna_yield_pre_shear_ng",
            portal_label="Portal extraction yield",
            lr_label="LR DNA Total ng [ESP1]",
            portal_getter=lambda c: value_from(
                c["row"],
                "portal_extraction_dna_yield_ng",
                "dna_yield_ng",
            ),
            lr_getter=lambda c: lr_value(c["lr_row"], "dna_total_ng_esp1"),
            compare_mode="number",
        ),
        FieldSpec(
            "DNA yield",
            "dna_yield_selected_container_or_post_shear_ng",
            portal_label="Portal selected extraction-container yield",
            lr_label="LR Total DNA ng [ESP2]",
            portal_getter=lambda c: value_from(c["row"], "extraction_container_yield_ng"),
            lr_getter=lambda c: lr_value(c["lr_row"], "total_dna_ng_esp2"),
            compare_mode="number",
            note="Stage may need confirmation before using this in prose.",
        ),
        FieldSpec(
            "DNA concentration / purity",
            "post_spri_qubit_ngul",
            portal_label="Portal sequencing-request post-SPRI concentration",
            lr_label="LR Qubit Quant (ng/ul) [ESP2]",
            portal_getter=lambda c: value_from(c["seq"], "qubit_ngul"),
            lr_getter=lambda c: lr_value(c["lr_row"], "qubit_quant_ng_ul_esp2", "qubit_quant_ngul_esp2"),
            compare_mode="number",
        ),
        FieldSpec(
            "DNA concentration / purity",
            "post_spri_nanodrop_ngul",
            portal_label="Portal sequencing-request Nanodrop concentration",
            lr_label="LR ND Quant (ng/uL) [ESP2]",
            portal_getter=lambda c: value_from(c["seq"], "nanodrop_concentration_ngul"),
            lr_getter=lambda c: lr_value(c["lr_row"], "nd_quant_ng_ul_esp2", "nd_quant_ngul_esp2"),
            compare_mode="number",
        ),
        FieldSpec(
            "DNA concentration / purity",
            "post_spri_260_280",
            portal_label="Portal sequencing-request 260/280",
            lr_label="LR ND 260/280 [ESP2]",
            portal_getter=lambda c: value_from(c["seq"], "ratio_260_280"),
            lr_getter=lambda c: lr_value(c["lr_row"], "nd_260_280_esp2", "nd_260280_esp2"),
            compare_mode="number",
        ),
        FieldSpec(
            "DNA concentration / purity",
            "post_spri_260_230",
            portal_label="Portal sequencing-request 260/230",
            lr_label="LR ND 260/230 [ESP2]",
            portal_getter=lambda c: value_from(c["seq"], "ratio_260_230"),
            lr_getter=lambda c: lr_value(c["lr_row"], "nd_260_230_esp2", "nd_260230_esp2"),
            compare_mode="number",
        ),
        FieldSpec(
            "Fragmentation",
            "shearing_date",
            lr_label="LR SHEAR Date started",
            lr_getter=lambda c: lr_value(c["lr_row"], "shear_date_started"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "Fragmentation",
            "fragmentation_machine",
            lr_label="LR MR Machine ID",
            lr_getter=lambda c: lr_value(c["lr_row"], "mr_machine_id"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "Fragmentation",
            "fragmentation_speed",
            lr_label="LR MR speed",
            lr_getter=lambda c: lr_value(c["lr_row"], "mr_speed"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "Fragment size / GQN",
            "fragment_size_bp",
            portal_label="Portal sheared Femto fragment size",
            lr_label="LR Femto Fragment Size [ESP2]",
            portal_getter=lambda c: value_from(c["seq"], "fragment_size_kb"),
            lr_getter=lambda c: lr_value(c["lr_row"], "femto_fragment_size_esp2"),
            compare_mode="bp",
        ),
        FieldSpec(
            "Fragment size / GQN",
            "gqn",
            portal_label="Portal extraction GQN",
            lr_label="LR GQN 10kb Threshold [ESP2] / GQN >30000 [ESP1]",
            portal_getter=lambda c: value_from(c["row"], "gqn"),
            lr_getter=lambda c: lr_value(c["lr_row"], "gqn_10kb_threshold_esp2", "gqn_30000_esp1"),
            compare_mode="number",
        ),
        FieldSpec(
            "Clean-up",
            "spri_type",
            portal_label="Portal sequencing-request SPRI type",
            lr_label="LR SPRI Type",
            portal_getter=lambda c: value_from(c["seq"], "spri_type"),
            lr_getter=lambda c: lr_value(c["lr_row"], "spri_type"),
        ),
        FieldSpec(
            "Clean-up",
            "bead_type",
            portal_label="Portal sequencing-request bead type",
            portal_getter=lambda c: value_from(c["seq"], "bead_type"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "Clean-up",
            "spri_input_volume_ul",
            lr_label="LR Vol Input SPRI (uL)",
            lr_getter=lambda c: lr_value(c["lr_row"], "vol_input_spri_ul"),
            relationship_sensitive=False,
        ),
        FieldSpec(
            "Clean-up",
            "post_shear_spri_volume_ul",
            lr_label="LR Post-Shear SPRI Volume",
            lr_getter=lambda c: lr_value(c["lr_row"], "post_shear_spri_volume", "postshear_spri_volume"),
            relationship_sensitive=False,
        ),
    ]


def context_from_summary(
    *,
    summary: Any,
    tolid: str,
    bioproject: str,
    species: str,
    assembly_accession: str,
    lr_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pacbio_runs = summary.run_groups["PacBio"].runs
    for run in pacbio_runs:
        row = run.to_context_dict()
        public_library_id = clean_value(row.get("library_name")) or clean_value(
            summary.technology_records["pacbio"].library_name
        )
        portal_library_id = value_from(
            row,
            "mlwh_library_id",
            "mlwh_pac_bio_library_tube_name",
        )
        metadata_lookup_id = portal_library_id or public_library_id or tolid
        seq_attrs, extraction_attrs = get_sequencing_and_extraction_metadata(metadata_lookup_id)
        merged_row = {**row, **extraction_attrs}

        public_run_alias = clean_value(row.get("run_alias")) or clean_value(
            summary.technology_records["pacbio"].extras.get("pacbio_run_alias")
        )
        mlwh_run_id = value_from(row, "mlwh_run_id", "mlwh_pac_bio_run_name")
        public_library_id = clean_value(public_library_id)
        portal_library_id = clean_value(portal_library_id)
        library_identity_conflict = bool(
            public_library_id
            and portal_library_id
            and normalise_text(public_library_id) != normalise_text(portal_library_id)
        )
        run_identity_conflict = bool(
            public_run_alias and mlwh_run_id and not run_alias_matches(public_run_alias, mlwh_run_id)
        )
        relationship_unclear = library_identity_conflict or run_identity_conflict

        lr_lookup_id = public_library_id or portal_library_id
        lr_row, lr_match_basis = lr_find(
            lr_df,
            lookup_id=lr_lookup_id,
            tolid=tolid,
            allow_tolid_fallback=not bool(lr_lookup_id),
        )
        portal_lr_row, portal_lr_match_basis = ({}, "")
        if portal_library_id and portal_library_id != lr_lookup_id:
            portal_lr_row, portal_lr_match_basis = lr_find(
                lr_df,
                lookup_id=portal_library_id,
                tolid=tolid,
                allow_tolid_fallback=False,
            )
        lr_candidates = lr_tolid_candidate_ids(lr_df, tolid)

        rows.append(
            {
                "row": merged_row,
                "seq": seq_attrs,
                "lr_row": lr_row,
                "portal_lr_row": portal_lr_row,
                "tolid": tolid,
                "species": species,
                "bioproject": bioproject,
                "assembly_accession": assembly_accession,
                "public_run_accession": clean_value(row.get("read_accession")),
                "public_run_alias": public_run_alias,
                "public_library_id": public_library_id,
                "public_sample_accession": clean_value(row.get("sample_accession")),
                "portal_run_id": clean_value(row.get("portal_run_id")),
                "mlwh_run_id": mlwh_run_id,
                "portal_library_id": portal_library_id,
                "portal_sample_uid": clean_value(row.get("portal_sample_uid")),
                "portal_extraction_uid": clean_value(row.get("portal_extraction_uid") or extraction_attrs.get("extraction_uid")),
                "portal_extraction_name": clean_value(row.get("portal_extraction_name") or extraction_attrs.get("extraction_name")),
                "portal_tissue_prep_uid": clean_value(
                    row.get("portal_tissue_prep_uid") or extraction_attrs.get("tissue_prep_uid")
                ),
                "portal_tissue_prep_name": clean_value(
                    row.get("portal_tissue_prep_name") or extraction_attrs.get("tissue_prep_name")
                ),
                "lr_lookup_id": lr_lookup_id or tolid,
                "lr_match_basis": lr_match_basis,
                "portal_lr_lookup_id": portal_library_id,
                "portal_lr_match_basis": portal_lr_match_basis,
                "lr_tolid_candidate_ids": lr_candidates,
                "library_identity_conflict": library_identity_conflict,
                "run_identity_conflict": run_identity_conflict,
                "relationship_unclear": relationship_unclear,
                "sequencing_qc_filter_applied": clean_value(
                    summary.totals.extras.get("sequencing_qc_filter_applied")
                ),
                "sequencing_qc_excluded_runs": clean_value(
                    summary.totals.extras.get("sequencing_qc_excluded_runs")
                ),
                "sequencing_qc_excluded_portal_runs": clean_value(
                    summary.totals.extras.get("sequencing_qc_excluded_portal_runs")
                ),
                "sequencing_assembly_run_accessions": clean_value(
                    summary.totals.extras.get("sequencing_assembly_run_accessions")
                ),
                "sequencing_assembly_excluded_runs": clean_value(
                    summary.totals.extras.get("sequencing_assembly_excluded_runs")
                ),
            }
        )
    return rows


def audit_context(context: dict[str, Any], field_specs: list[FieldSpec]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in field_specs:
        public_value = clean_value(spec.public_getter(context) if spec.public_getter else "")
        portal_value = clean_value(spec.portal_getter(context) if spec.portal_getter else "")
        lr_value = clean_value(spec.lr_getter(context) if spec.lr_getter else "")
        status = compare_status(
            public_value=public_value,
            portal_value=portal_value,
            lr_value=lr_value,
            mode=spec.compare_mode,
            relationship_unclear=bool(context["relationship_unclear"]),
            relationship_sensitive=spec.relationship_sensitive,
        )
        note = spec.note
        if status == "relationship_unclear":
            note = (
                f"{note} " if note else ""
            ) + "Public run/library identity differs from the Portal/Core/MLWH identity."
        elif (
            (spec.lr_getter is not None or spec.lr_label)
            and not clean_value(lr_value)
            and clean_value(context.get("lr_lookup_id"))
            and not clean_value(context.get("lr_match_basis"))
            and clean_value(context.get("lr_tolid_candidate_ids"))
        ):
            note = (
                f"{note} " if note else ""
            ) + f"No exact LR row for the selected library; ToLID-level LR candidates: {context['lr_tolid_candidate_ids']}."

        rows.append(
            {
                "tolid": context["tolid"],
                "species": context["species"],
                "bioproject": context["bioproject"],
                "assembly_accession": context["assembly_accession"],
                "public_run_accession": context["public_run_accession"],
                "public_run_alias": context["public_run_alias"],
                "public_library_id": context["public_library_id"],
                "public_sample_accession": context["public_sample_accession"],
                "portal_run_id": context["portal_run_id"],
                "mlwh_run_id": context["mlwh_run_id"],
                "portal_library_id": context["portal_library_id"],
                "portal_sample_uid": context["portal_sample_uid"],
                "portal_extraction_uid": context["portal_extraction_uid"],
                "portal_extraction_name": context["portal_extraction_name"],
                "portal_tissue_prep_uid": context["portal_tissue_prep_uid"],
                "portal_tissue_prep_name": context["portal_tissue_prep_name"],
                "lr_lookup_id": context["lr_lookup_id"],
                "lr_match_basis": context["lr_match_basis"],
                "lr_tolid_candidate_ids": context["lr_tolid_candidate_ids"],
                "portal_lr_lookup_id": context["portal_lr_lookup_id"],
                "portal_lr_match_basis": context["portal_lr_match_basis"],
                "library_identity_conflict": context["library_identity_conflict"],
                "run_identity_conflict": context["run_identity_conflict"],
                "relationship_unclear": context["relationship_unclear"],
                "sequencing_qc_filter_applied": context["sequencing_qc_filter_applied"],
                "sequencing_qc_excluded_runs": context["sequencing_qc_excluded_runs"],
                "sequencing_qc_excluded_portal_runs": context["sequencing_qc_excluded_portal_runs"],
                "sequencing_assembly_run_accessions": context["sequencing_assembly_run_accessions"],
                "sequencing_assembly_excluded_runs": context["sequencing_assembly_excluded_runs"],
                "concept": spec.concept,
                "field_name": spec.field_name,
                "public_source": spec.public_label,
                "public_value": public_value,
                "portal_core_source": spec.portal_label,
                "portal_core_value": portal_value,
                "lr_source": spec.lr_label,
                "lr_value": lr_value,
                "status": status,
                "note": note,
            }
        )
    return rows


def error_rows(
    *,
    case: dict[str, str],
    message: str,
) -> list[dict[str, Any]]:
    return [
        {
            "tolid": case.get("tolid", ""),
            "species": case.get("species", ""),
            "bioproject": case.get("bioproject", ""),
            "assembly_accession": case.get("assembly_accession", ""),
            "concept": "Audit",
            "field_name": "error",
            "status": "error",
            "note": message,
        }
    ]


def load_cases(args: argparse.Namespace) -> list[dict[str, str]]:
    df = pd.read_csv(args.assembly_tsv, sep="\t", low_memory=False)
    df = df.rename(
        columns={
            "sample": "tolid",
            "BioProject": "bioproject",
            "accession": "assembly_accession",
        }
    )
    if args.tolid:
        wanted = {value.strip() for value in args.tolid}
        df = df[df["tolid"].astype(str).isin(wanted)]
    if args.bioproject:
        wanted = {value.strip() for value in args.bioproject}
        df = df[df["bioproject"].astype(str).isin(wanted)]
    if not args.tolid and not args.bioproject:
        if args.status:
            df = df[df["statussummary"].astype(str) == args.status]
        df = df[df["bioproject"].notna() & df["tolid"].notna()]
        if "PacBio" in df.columns:
            df = df[df["PacBio"].notna()]
    if args.offset:
        df = df.iloc[args.offset:]
    if args.limit:
        df = df.head(args.limit)

    cases = []
    for _, row in df.iterrows():
        cases.append(
            {
                "tolid": clean_value(row.get("tolid")),
                "species": clean_value(row.get("species")),
                "bioproject": clean_value(row.get("bioproject")),
                "assembly_accession": clean_value(row.get("assembly_accession")),
            }
        )
    return cases


def write_outputs(rows: list[dict[str, Any]], output_dir: Path, prefix: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    long_path = output_dir / f"{prefix}_long.csv"
    summary_path = output_dir / f"{prefix}_summary.csv"
    audit_df = pd.DataFrame(rows)
    audit_df.to_csv(long_path, index=False)

    if audit_df.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            audit_df.groupby(["tolid", "bioproject", "status"], dropna=False)
            .size()
            .reset_index(name="field_count")
            .sort_values(["tolid", "status"])
        )
    summary.to_csv(summary_path, index=False)
    return long_path, summary_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit assembly-selected PacBio DNA extraction metadata against "
            "Portal/Core/MLWH and LR sample prep values."
        )
    )
    parser.add_argument("--tolid", action="append", help="Restrict audit to a ToLID. Repeatable.")
    parser.add_argument("--bioproject", action="append", help="Restrict audit to a BioProject. Repeatable.")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many filtered rows.")
    parser.add_argument("--limit", type=int, help="Limit the number of Assembly Informatics rows.")
    parser.add_argument("--status", default="1 submitted", help="Assembly Informatics statussummary filter.")
    parser.add_argument("--assembly-tsv", default=ASSEMBLY_INFORMATICS_TSV)
    parser.add_argument("--lr-tsv", default=None, help="Override LR_sample_prep.tsv path.")
    parser.add_argument(
        "--output-dir",
        default=str(Path.cwd()),
        help="Directory for audit CSV outputs.",
    )
    parser.add_argument("--prefix", default="dna_extraction_audit")
    args = parser.parse_args()

    cases = load_cases(args)
    lr_df, _original_for, lr_path = load_lr_rows(args.lr_tsv)
    field_specs = build_field_specs()
    sequencing_service = SequencingService()

    print(f"Loaded {len(cases)} case(s).")
    print(f"LR sample prep TSV: {lr_path or 'not found'}")

    output_rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        tolid = case["tolid"]
        bioproject = case["bioproject"]
        print(f"[{index}/{len(cases)}] {tolid} {bioproject}")
        try:
            summary = sequencing_service.build_context(
                bioproject,
                tolid,
                assembly_selection=make_assembly_selection(
                    case["assembly_accession"],
                    tolid,
                ),
            )
            contexts = context_from_summary(
                summary=summary,
                tolid=tolid,
                bioproject=bioproject,
                species=case["species"],
                assembly_accession=case["assembly_accession"],
                lr_df=lr_df,
            )
            if not contexts:
                output_rows.extend(error_rows(case=case, message="No retained PacBio run after filtering."))
                continue
            for context in contexts:
                output_rows.extend(audit_context(context, field_specs))
        except Exception as exc:  # noqa: BLE001 - audit should continue across cases.
            output_rows.extend(error_rows(case=case, message=str(exc)))

    long_path, summary_path = write_outputs(output_rows, Path(args.output_dir), args.prefix)
    print(f"Wrote {long_path}")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
