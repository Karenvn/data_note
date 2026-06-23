from __future__ import annotations

from collections import Counter, defaultdict
import csv
import logging
import os
from pathlib import Path
import re

from Bio import Entrez
import pandas as pd

from .common import (
    build_native_table,
    filter_primary_chromosome_rows,
    flatten_cell,
    parse_sex_chromosome_labels,
    resolve_single_assembly_phrase,
    safe_str,
    software_version,
    software_versions_used,
)
from .darwin import make_table2_rows as _make_table2_rows, make_table4_rows as _make_table4_rows


GN_ASSETS_ROOT = Path(
    os.getenv(
        "DATA_NOTE_GN_ASSETS",
        os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "gn_assets")),
    )
)

ACCESSION_RE = re.compile(r"^[A-Z]{1,4}_?\d{5,}(?:\.\d+)?$")
CHROMOSOME_TITLE_RE = re.compile(r"\bchromosome:?\s*([^,;]+)", re.IGNORECASE)
MERIAN_ELEMENTS = frozenset({"MZ", *(f"M{i}" for i in range(1, 32))})


def _merian_tsv_candidates(tolid: str) -> tuple[Path, ...]:
    return (
        GN_ASSETS_ROOT / "merian" / tolid / "all_location.tsv",
        GN_ASSETS_ROOT / "merians" / tolid / "all_location.tsv",
    )


def _busco_table_candidates(tolid: str) -> tuple[Path, ...]:
    configured_roots = [
        os.getenv("DATA_NOTE_BUSCO_DIR"),
        os.getenv("BUSCO_DIR"),
        GN_ASSETS_ROOT / "busco",
    ]
    names = ("full_table_hap1.1.tsv", "full_table.hap1.1.tsv", "full_table.tsv")
    candidates: list[Path] = []
    for root in configured_roots:
        if not root:
            continue
        root_path = Path(root)
        for base in (root_path / tolid, root_path):
            candidates.extend(base / name for name in names)
    return tuple(dict.fromkeys(candidates))


def _merian_reference_candidates() -> tuple[Path, ...]:
    env_reference = os.getenv("DATA_NOTE_MERIAN_REFERENCE") or os.getenv("DATA_NOTE_MERIAN_REFERENCE_TABLE")
    candidates = [
        Path(env_reference) if env_reference else None,
        GN_ASSETS_ROOT / "Merian_elements_full_table.tsv",
        GN_ASSETS_ROOT / "merian" / "Merian_elements_full_table.tsv",
        GN_ASSETS_ROOT / "merians" / "Merian_elements_full_table.tsv",
        Path.home() / "Documents" / "Psyche_2026" / "scripts" / "merian_plotting" / "Merian_elements_full_table.tsv",
    ]
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate is not None))


def chrom_to_merian(tsv_file: str | Path, threshold: int = 5) -> dict[str, str]:
    df = pd.read_csv(tsv_file, sep="\t")
    df["chrom"] = df["query_chr"].map(_normalise_merian_key)
    counts = (
        df.groupby(["chrom", "assigned_chr"])
        .size()
        .reset_index(name="n")
        .query("n >= @threshold")
    )
    assignments = (
        counts.groupby("chrom")["assigned_chr"]
        .apply(lambda s: ";".join(sorted(s.unique())))
        .to_dict()
    )
    return _with_accession_aliases(assignments)


def _read_merian_reference(reference_table: Path) -> dict[str, str]:
    ref_map: dict[str, str] = {}
    with reference_table.open(newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or row[0].startswith("#") or len(row) < 3:
                continue
            busco_id = row[0].strip()
            merian = row[2].strip().upper()
            if busco_id.lower().startswith("busco") or merian not in MERIAN_ELEMENTS:
                continue
            ref_map[busco_id] = merian
    return ref_map


def _chrom_to_merian_from_busco(
    query_table: str | Path,
    reference_table: str | Path,
    threshold: int = 5,
) -> dict[str, str]:
    ref_map = _read_merian_reference(Path(reference_table))
    if not ref_map:
        return {}

    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    with Path(query_table).open(newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row or row[0].startswith("#") or len(row) < 5:
                continue
            status = row[1].strip()
            if status not in {"Complete", "Duplicated"}:
                continue
            merian = ref_map.get(row[0].strip())
            if not merian:
                continue
            chrom = _normalise_merian_key(row[2])
            if chrom:
                counts[chrom][merian] += 1

    assignments = {
        chrom: ";".join(sorted(merian for merian, count in counter.items() if count >= threshold))
        for chrom, counter in counts.items()
    }
    return _with_accession_aliases({chrom: merian for chrom, merian in assignments.items() if merian})


def _derive_merian_dict_from_busco(tolid: str, threshold: int = 5) -> dict[str, str]:
    query_table = next((candidate for candidate in _busco_table_candidates(tolid) if candidate.is_file()), None)
    reference_table = next((candidate for candidate in _merian_reference_candidates() if candidate.is_file()), None)
    if not query_table or not reference_table:
        return {}
    try:
        return _chrom_to_merian_from_busco(query_table, reference_table, threshold=threshold)
    except Exception as exc:
        logging.warning("Could not derive Merian assignments from BUSCO for %s: %s", tolid, exc)
        return {}


def _normalise_merian_key(value) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip().split(":")[0]


def _unversioned_accession(value: str) -> str:
    return re.sub(r"\.\d+$", "", value.strip())


def _candidate_lookup_keys(*values) -> tuple[str, ...]:
    keys: list[str] = []
    for value in values:
        key = _normalise_merian_key(value)
        if not key:
            continue
        keys.append(key)
        keys.append(_unversioned_accession(key))
        keys.append(key.upper())
    return tuple(dict.fromkeys(keys))


def _with_accession_aliases(assignments: dict[str, str]) -> dict[str, str]:
    lookup = dict(assignments)
    for key, value in assignments.items():
        lookup.setdefault(_unversioned_accession(key), value)
    return lookup


def _ncbi_chromosome_aliases(accessions) -> dict[str, str]:
    accession_list = sorted(
        {
            _normalise_merian_key(accession)
            for accession in accessions
            if ACCESSION_RE.fullmatch(_normalise_merian_key(accession))
        }
    )
    if not accession_list:
        return {}

    if not Entrez.email:
        Entrez.email = os.getenv("ENTREZ_EMAIL", "default_email")

    aliases: dict[str, str] = {}
    for index in range(0, len(accession_list), 100):
        batch = accession_list[index : index + 100]
        try:
            with Entrez.esummary(db="nuccore", id=",".join(batch), retmode="xml") as handle:
                summaries = Entrez.read(handle)
        except Exception:
            continue
        for summary in summaries:
            accession = str(summary.get("AccessionVersion") or "").strip()
            title = str(summary.get("Title") or "")
            match = CHROMOSOME_TITLE_RE.search(title)
            if accession and match:
                aliases[accession] = match.group(1).strip()
    return aliases


def _with_chromosome_aliases(lookup: dict[str, str]) -> dict[str, str]:
    aliases = _ncbi_chromosome_aliases(lookup.keys())
    if not aliases:
        return lookup

    expanded = dict(lookup)
    for accession, molecule in aliases.items():
        value = lookup.get(accession) or lookup.get(_unversioned_accession(accession))
        if not value:
            continue
        for key in _candidate_lookup_keys(molecule):
            expanded.setdefault(key, value)
    return expanded


def _lookup_merian(entry: dict, lookup: dict[str, str]) -> str | None:
    for key in _candidate_lookup_keys(entry.get("INSDC"), entry.get("molecule")):
        if key in lookup:
            return lookup[key]
    return None


def _prepare_merian_lookup(tolid: str | None, chromosome_rows: list[dict]) -> dict[str, str]:
    lookup = merian_dict(tolid)
    if not lookup or not chromosome_rows:
        return lookup
    if any(_lookup_merian(entry, lookup) for entry in chromosome_rows):
        return lookup
    return _with_chromosome_aliases(lookup)


def merian_dict(tolid: str | None, threshold: int = 5) -> dict[str, str]:
    if not tolid:
        return {}
    for candidate in _merian_tsv_candidates(tolid):
        if candidate.is_file():
            try:
                return chrom_to_merian(candidate, threshold=threshold)
            except Exception as exc:
                logging.warning("Could not read Merian assignment table %s: %s", candidate, exc)
    return _derive_merian_dict_from_busco(tolid, threshold=threshold)


def _format_read_count_cell(context: dict, prefix: str) -> str:
    value = flatten_cell(context.get(f"{prefix}_reads_millions"))
    unit = flatten_cell(context.get(f"{prefix}_read_count_unit"))
    if unit:
        return f"{value} million {unit}"
    return f"{value} million"


def _table1_widths(num_cols: int) -> list[float]:
    if num_cols == 3:
        return [0.25, 0.25, 0.25]
    return [1 / num_cols] * num_cols


def _append_table1_technology_column(
    context: dict,
    headers: list[str],
    rows: list[list[str]],
    *,
    prefix: str,
    label: str,
) -> None:
    if not context.get(f"{prefix}_sample_accession"):
        return
    headers.append(label)
    values = [
        flatten_cell(context.get(f"{prefix}_tolid")),
        flatten_cell(context.get(f"{prefix}_specimen_id")),
        flatten_cell(context.get(f"{prefix}_sample_derived_from")),
        flatten_cell(context.get(f"{prefix}_sample_accession")),
        flatten_cell(context.get(f"{prefix}_organism_part")),
        flatten_cell(context.get(f"{prefix}_instrument")),
        flatten_cell(context.get(f"{prefix}_run_accessions")),
        _format_read_count_cell(context, prefix),
        f"{flatten_cell(context.get(f'{prefix}_bases_gb'))} Gb",
    ]
    for index, value in enumerate(values):
        rows[index].append(value)


def make_table1_rows(context):
    headers = ["**Platform**", "**PacBio HiFi**", "**Hi-C**"]

    rows = [
        ["**ToLID**", flatten_cell(context.get("tolid")), flatten_cell(context.get("hic_tolid"))],
        ["**Specimen ID**", flatten_cell(context.get("pacbio_specimen_id")), flatten_cell(context.get("hic_specimen_id"))],
        ["**BioSample (source individual)**", flatten_cell(context.get("pacbio_sample_derived_from")), flatten_cell(context.get("hic_sample_derived_from"))],
        ["**BioSample (tissue)**", flatten_cell(context.get("pacbio_sample_accession")), flatten_cell(context.get("hic_sample_accession"))],
        ["**Tissue**", flatten_cell(context.get("pacbio_organism_part")), flatten_cell(context.get("hic_organism_part"))],
        ["**Instrument**", flatten_cell(context.get("pacbio_instrument")), flatten_cell(context.get("hic_instrument"))],
        ["**Run accessions**", flatten_cell(context.get("pacbio_run_accessions")), flatten_cell(context.get("hic_run_accessions"))],
        ["**Read count total**", _format_read_count_cell(context, "pacbio"), _format_read_count_cell(context, "hic")],
        ["**Base count total**", f"{flatten_cell(context.get('pacbio_bases_gb'))} Gb", f"{flatten_cell(context.get('hic_bases_gb'))} Gb"],
    ]

    _append_table1_technology_column(
        context,
        headers,
        rows,
        prefix="chromium",
        label="**10X Chromium**",
    )

    if context.get("rna_sample_accession"):
        headers.append("**RNA-seq**")
        rna_values = [
            flatten_cell(context.get("rna_tolid")),
            flatten_cell(context.get("rna_specimen_id")),
            flatten_cell(context.get("rna_sample_derived_from")),
            flatten_cell(context.get("rna_sample_accession")),
            flatten_cell(context.get("rna_organism_part")),
            flatten_cell(context.get("rna_instrument")),
            flatten_cell(context.get("rna_run_accessions")),
            _format_read_count_cell(context, "rna"),
            f"{flatten_cell(context.get('rna_bases_gb'))} Gb",
        ]
        for index, value in enumerate(rna_values):
            rows[index].append(value)

    if context.get("isoseq_sample_accession"):
        headers.append("**Iso-Seq**")
        isoseq_values = [
            flatten_cell(context.get("isoseq_tolid")),
            flatten_cell(context.get("isoseq_specimen_id")),
            flatten_cell(context.get("isoseq_sample_derived_from")),
            flatten_cell(context.get("isoseq_sample_accession")),
            flatten_cell(context.get("isoseq_organism_part")),
            flatten_cell(context.get("isoseq_instrument")),
            flatten_cell(context.get("isoseq_run_accessions")),
            _format_read_count_cell(context, "isoseq"),
            f"{flatten_cell(context.get('isoseq_bases_gb'))} Gb",
        ]
        for index, value in enumerate(isoseq_values):
            rows[index].append(value)

    num_cols = len(headers)
    alignment = "L" * num_cols
    width = _table1_widths(num_cols)
    native_table = build_native_table(headers, rows)

    return {
        "caption": f"Specimen and sequencing data for *{safe_str(context.get('species'))}* (BioProject {flatten_cell(context.get('bioproject'))})",
        "label": "tbl:table1",
        "alignment": alignment,
        "width": width,
        "rows": [",".join(headers)] + [",".join(r) for r in rows],
        **native_table,
    }


def make_table2_rows(context):
    return _make_table2_rows(context)


def make_table3_rows(context: dict) -> dict:
    rows = []
    native_headers = []
    native_rows = []
    label = "tbl:table3"
    species = context.get("species", "")
    tolid = context.get("tolid", "")
    assemblies_type = context.get("assemblies_type", "")

    def format_row(entry: dict, keys: list[str]) -> list[str]:
        return [flatten_cell(entry.get(k)) for k in keys]

    if assemblies_type == "hap_asm":
        hap1_chrom = context.get("hap1_assembly_level") == "chromosome"
        hap2_chrom = context.get("hap2_assembly_level") == "chromosome"

        if hap1_chrom:
            hap1_data = context.get("hap1_chromosome_data")
            if not hap1_data and context.get("chromosome_data"):
                hap1_data = [
                    {
                        "INSDC": row.get("hap1_INSDC"),
                        "molecule": row.get("hap1_molecule"),
                        "length": row.get("hap1_length"),
                        "GC": row.get("hap1_GC"),
                    }
                    for row in context.get("chromosome_data", [])
                    if row.get("hap1_INSDC")
                ]
            hap1_data = filter_primary_chromosome_rows(
                hap1_data or [],
                parse_sex_chromosome_labels(context.get("hap1_sex_chromosomes")),
            )

            if hap1_data:
                if hap2_chrom:
                    caption = (
                        f"Chromosomal pseudomolecules in the haplotype 1 genome assembly of *{species}* "
                        f"{tolid} (haplotype 2 also at chromosome level)"
                    )
                else:
                    caption = f"Chromosomal pseudomolecules in the haplotype 1 genome assembly of *{species}* {tolid}"
                alignment = "CCCCC"
                native_headers = [
                    "**INSDC accession**",
                    "**Molecule**",
                    "**Length (Mb)**",
                    "**GC%**",
                    "**Assigned Merian elements**",
                ]
                rows.append(",".join(native_headers))
                merian_lookup = _prepare_merian_lookup(tolid, hap1_data)
                for entry in hap1_data:
                    formatted = format_row(entry, ["INSDC", "molecule", "length", "GC"]) + [
                        _lookup_merian(entry, merian_lookup) or r"\-"
                    ]
                    rows.append(",".join(formatted))
                    native_rows.append(formatted)
            else:
                caption = f"No chromosomal data available for haplotype 1 of *{species}*"
                alignment = "CCCC"
                rows.append("No chromosome data available.")
                native_headers = ["**Note**"]
                native_rows = [["No chromosome data available."]]
        else:
            caption = f"No chromosomal-level scaffolds in haplotype 1 assembly of *{species}*"
            alignment = "CCCC"
            rows.append("No chromosome data available.")
            native_headers = ["**Note**"]
            native_rows = [["No chromosome data available."]]
    elif assemblies_type == "prim_alt":
        chrom_data = filter_primary_chromosome_rows(
            context.get("chromosome_data", []),
            parse_sex_chromosome_labels(context.get("sex_chromosomes")),
        )
        caption = f"Chromosomal pseudomolecules in the {resolve_single_assembly_phrase(context)} of *{species}* {tolid}"
        alignment = "CCCCC"
        native_headers = [
            "**INSDC accession**",
            "**Molecule**",
            "**Length (Mb)**",
            "**GC%**",
            "**Assigned Merian elements**",
        ]
        rows.append(",".join(native_headers))
        merian_lookup = _prepare_merian_lookup(tolid, chrom_data)
        for entry in chrom_data:
            formatted = format_row(entry, ["INSDC", "molecule", "length", "GC"]) + [
                _lookup_merian(entry, merian_lookup) or r"\-"
            ]
            rows.append(",".join(formatted))
            native_rows.append(formatted)
    else:
        caption = f"No chromosomal data available for *{species}*"
        alignment = "CCCC"
        rows.append("No chromosome data available.")
        native_headers = ["**Note**"]
        native_rows = [["No chromosome data available."]]

    native_table = build_native_table(native_headers, native_rows)

    return {
        "label": label,
        "caption": caption,
        "alignment": alignment,
        "width": [0.25, 0.20, 0.15, 0.15, 0.25] if alignment == "CCCCC" else None,
        "rows": rows,
        **native_table,
    }


def make_table4_rows(context):
    return _make_table4_rows(context)


def make_table5_rows(context):
    rows = []
    native_body = []
    label = "tbl:table5"
    alignment = "LLL"
    caption = f"Software versions and sources used for *{safe_str(context.get('species'))}*"

    software_list = [
        ("BLAST", software_version(context, "blast_version", "2.14.0"), "[ftp://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/](ftp://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/)"),
        ("BlobToolKit", context.get("blobtoolkit_version"), "[https://github.com/blobtoolkit/blobtoolkit](https://github.com/blobtoolkit/blobtoolkit)"),
        ("BUSCO", software_versions_used(context, "btk_busco_version", "busco_version", "local_busco_version"), "[https://gitlab.com/ezlab/busco](https://gitlab.com/ezlab/busco)"),
        ("bwa-mem2", software_version(context, "bwa_mem2_version", "2.2.1"), "[https://github.com/bwa-mem2/bwa-mem2](https://github.com/bwa-mem2/bwa-mem2)"),
        ("DIAMOND", context.get("diamond_version"), "[https://github.com/bbuchfink/diamond](https://github.com/bbuchfink/diamond)"),
        ("fasta_windows", software_version(context, "fasta_windows_version", "0.2.4"), "[https://github.com/tolkit/fasta_windows](https://github.com/tolkit/fasta_windows)"),
        ("FastK", "1.1", "[https://github.com/thegenemyers/FASTK](https://github.com/thegenemyers/FASTK)"),
        ("GenomeScope2.0", software_version(context, "genomescope_version", "2.0.1"), "[https://github.com/tbenavi1/genomescope2.0](https://github.com/tbenavi1/genomescope2.0)"),
        ("Gfastats", software_version(context, "gfastats_version", "1.3.6"), "[https://github.com/vgl-hub/gfastats](https://github.com/vgl-hub/gfastats)"),
        ("Hifiasm", context.get("hifiasm_version"), "[https://github.com/chhylp123/hifiasm](https://github.com/chhylp123/hifiasm)"),
        ("HiGlass", software_version(context, "higlass_version", "1.13.4"), "[https://github.com/higlass/higlass](https://github.com/higlass/higlass)"),
        ("Long Ranger", context.get("longranger_version"), "[https://support.10xgenomics.com/genome-exome/software/pipelines/latest/advanced/other-pipelines](https://support.10xgenomics.com/genome-exome/software/pipelines/latest/advanced/other-pipelines)"),
        ("freebayes", context.get("freebayes_version"), "[https://github.com/freebayes/freebayes](https://github.com/freebayes/freebayes)"),
        ("merian-busco-painter", software_version(context, "merian_busco_painter_version", "v1.0.0"), "[https://github.com/Karenvn/merian-busco-painter](https://github.com/Karenvn/merian-busco-painter)"),
        ("MerquryFK", "1.1.0-c1", "[https://github.com/thegenemyers/MERQURY.FK](https://github.com/thegenemyers/MERQURY.FK)"),
        ("Minimap2", context.get("minimap2_version"), "[https://github.com/lh3/minimap2](https://github.com/lh3/minimap2)"),
        ("MitoHiFi", context.get("mitohifi_version"), "[https://github.com/marcelauliano/MitoHiFi](https://github.com/marcelauliano/MitoHiFi)"),
        ("Oatk", context.get("oatk_version"), "[https://github.com/c-zhou/oatk](https://github.com/c-zhou/oatk)"),
        ("MultiQC", software_version(context, "multiqc_version", "1.14; 1.17 and 1.18"), "[https://github.com/MultiQC/MultiQC](https://github.com/MultiQC/MultiQC)"),
        ("Nextflow", context.get("nextflow_version"), "[https://github.com/nextflow-io/nextflow](https://github.com/nextflow-io/nextflow)"),
        ("PretextSnapshot", software_version(context, "pretextsnapshot_version", "0.0.5"), "[https://github.com/sanger-tol/PretextSnapshot](https://github.com/sanger-tol/PretextSnapshot)"),
        ("PretextView", software_version(context, "pretextview_version", "1.0.3"), "[https://github.com/sanger-tol/PretextView](https://github.com/sanger-tol/PretextView)"),
        ("purge_dups", context.get("purge_dups_version"), "[https://github.com/dfguan/purge_dups](https://github.com/dfguan/purge_dups)"),
        ("samtools", context.get("samtools_version"), "[https://github.com/samtools/samtools](https://github.com/samtools/samtools)"),
        ("SALSA2", context.get("salsa_version"), "[https://github.com/marbl/SALSA](https://github.com/marbl/SALSA)"),
        ("sanger-tol/ascc", software_version(context, "ascc_version", "0.1.0"), "[https://github.com/sanger-tol/ascc](https://github.com/sanger-tol/ascc)"),
        ("sanger-tol/blobtoolkit", context.get("btk_pipeline_version"), "[https://github.com/sanger-tol/blobtoolkit](https://github.com/sanger-tol/blobtoolkit)"),
        ("sanger-tol/curationpretext", software_version(context, "curationpretext_version", "1.4.2"), "[https://github.com/sanger-tol/curationpretext](https://github.com/sanger-tol/curationpretext)"),
        ("Seqtk", software_version(context, "seqtk_version", "1.3"), "[https://github.com/lh3/seqtk](https://github.com/lh3/seqtk)"),
        ("Singularity", software_version(context, "singularity_version", "3.9.0"), "[https://github.com/sylabs/singularity](https://github.com/sylabs/singularity)"),
        ("TreeVal", software_version(context, "treeval_version", "1.4.0"), "[https://github.com/sanger-tol/treeval](https://github.com/sanger-tol/treeval)"),
        ("YaHS", context.get("yahs_version"), "[https://github.com/c-zhou/yahs](https://github.com/c-zhou/yahs)"),
    ]

    headers = ["**Software**", "**Version**", "**Source**"]
    rows.append(",".join(headers))
    for name, version, url in software_list:
        if version is None:
            continue
        native_body.append([name, version, url])
        rows.append(f"{name},{version},{url}")

    native_table = build_native_table(headers, native_body)

    return {
        "label": label,
        "caption": caption,
        "alignment": alignment,
        "width": [0.25, 0.15, 0.60],
        "rows": rows,
        **native_table,
    }


def build_all_tables(context: dict) -> dict:
    context["tables"] = {
        "table1": make_table1_rows(context),
        "table2": make_table2_rows(context),
        "table3": make_table3_rows(context),
        "table4": make_table4_rows(context),
        "table5": make_table5_rows(context),
    }
    return context
