from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .common import build_native_table, flatten_cell, safe_str
from .darwin import make_table2_rows as _make_table2_rows, make_table4_rows as _make_table4_rows


GN_ASSETS_ROOT = Path(
    os.getenv(
        "DATA_NOTE_GN_ASSETS",
        os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "gn_assets")),
    )
)


def _merian_tsv_candidates(tolid: str) -> tuple[Path, ...]:
    return (
        GN_ASSETS_ROOT / "merian" / tolid / "all_location.tsv",
        GN_ASSETS_ROOT / "merians" / tolid / "all_location.tsv",
    )


def chrom_to_merian(tsv_file: str | Path, threshold: int = 5) -> dict[str, str]:
    df = pd.read_csv(tsv_file, sep="\t")
    df["chrom"] = df["query_chr"].astype(str).str.split(":").str[0]
    counts = (
        df.groupby(["chrom", "assigned_chr"])
        .size()
        .reset_index(name="n")
        .query("n >= @threshold")
    )
    return (
        counts.groupby("chrom")["assigned_chr"]
        .apply(lambda s: ";".join(sorted(s.unique())))
        .to_dict()
    )


def merian_dict(tolid: str | None, threshold: int = 5) -> dict[str, str]:
    if not tolid:
        return {}
    for candidate in _merian_tsv_candidates(tolid):
        if candidate.is_file():
            try:
                return chrom_to_merian(candidate, threshold=threshold)
            except Exception:
                return {}
    return {}


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
        ["**Read count total**", f"{flatten_cell(context.get('pacbio_reads_millions'))} million", f"{flatten_cell(context.get('hic_reads_millions'))} million"],
        ["**Base count total**", f"{flatten_cell(context.get('pacbio_bases_gb'))} Gb", f"{flatten_cell(context.get('hic_bases_gb'))} Gb"],
    ]

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
            f"{flatten_cell(context.get('rna_reads_millions'))} million",
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
            f"{flatten_cell(context.get('isoseq_reads_millions'))} million",
            f"{flatten_cell(context.get('isoseq_bases_gb'))} Gb",
        ]
        for index, value in enumerate(isoseq_values):
            rows[index].append(value)

    num_cols = len(headers)
    alignment = "L" * num_cols
    width = [0.25] * num_cols if num_cols == 4 else ([0.20] * num_cols if num_cols == 5 else [0.25, 0.25, 0.25])
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
    merian_lookup = merian_dict(tolid)

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
                for entry in hap1_data:
                    formatted = format_row(entry, ["INSDC", "molecule", "length", "GC"]) + [
                        merian_lookup.get(entry.get("INSDC"), r"\-")
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
        chrom_data = context.get("chromosome_data", [])
        caption = f"Chromosomal pseudomolecules in the primary genome assembly of *{species}* {tolid}"
        alignment = "CCCCC"
        native_headers = [
            "**INSDC accession**",
            "**Molecule**",
            "**Length (Mb)**",
            "**GC%**",
            "**Assigned Merian elements**",
        ]
        rows.append(",".join(native_headers))
        for entry in chrom_data:
            formatted = format_row(entry, ["INSDC", "molecule", "length", "GC"]) + [
                merian_lookup.get(entry.get("INSDC"), r"\-")
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
        ("BLAST", "2.14.0", "[ftp://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/](ftp://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/)"),
        ("BlobToolKit", context.get("blobtoolkit_version"), "[https://github.com/blobtoolkit/blobtoolkit](https://github.com/blobtoolkit/blobtoolkit)"),
        ("BUSCO", context.get("busco_version"), "[https://gitlab.com/ezlab/busco](https://gitlab.com/ezlab/busco)"),
        ("bwa-mem2", "2.2.1", "[https://github.com/bwa-mem2/bwa-mem2](https://github.com/bwa-mem2/bwa-mem2)"),
        ("DIAMOND", context.get("diamond_version"), "[https://github.com/bbuchfink/diamond](https://github.com/bbuchfink/diamond)"),
        ("fasta_windows", "0.2.4", "[https://github.com/tolkit/fasta_windows](https://github.com/tolkit/fasta_windows)"),
        ("FastK", "1.1", "[https://github.com/thegenemyers/FASTK](https://github.com/thegenemyers/FASTK)"),
        ("GenomeScope2.0", "2.0.1", "[https://github.com/tbenavi1/genomescope2.0](https://github.com/tbenavi1/genomescope2.0)"),
        ("Gfastats", "1.3.6", "[https://github.com/vgl-hub/gfastats](https://github.com/vgl-hub/gfastats)"),
        ("Hifiasm", context.get("hifiasm_version"), "[https://github.com/chhylp123/hifiasm](https://github.com/chhylp123/hifiasm)"),
        ("HiGlass", "1.13.4", "[https://github.com/higlass/higlass](https://github.com/higlass/higlass)"),
        ("lep_busco_painter", "1.0.0", "[https://github.com/charlottewright/lep_busco_painter](https://github.com/charlottewright/lep_busco_painter)"),
        ("MerquryFK", "1.1.2", "[https://github.com/thegenemyers/MERQURY.FK](https://github.com/thegenemyers/MERQURY.FK)"),
        ("Minimap2", context.get("minimap2_version"), "[https://github.com/lh3/minimap2](https://github.com/lh3/minimap2)"),
        ("MitoHiFi", context.get("mitohifi_version"), "[https://github.com/marcelauliano/MitoHiFi](https://github.com/marcelauliano/MitoHiFi)"),
        ("Oatk", context.get("oatk_version"), "[https://github.com/c-zhou/oatk](https://github.com/c-zhou/oatk)"),
        ("MultiQC", "1.14; 1.17 and 1.18", "[https://github.com/MultiQC/MultiQC](https://github.com/MultiQC/MultiQC)"),
        ("Nextflow", context.get("nextflow_version"), "[https://github.com/nextflow-io/nextflow](https://github.com/nextflow-io/nextflow)"),
        ("PretextSnapshot", "0.0.5", "[https://github.com/sanger-tol/PretextSnapshot](https://github.com/sanger-tol/PretextSnapshot)"),
        ("PretextView", "1.0.3", "[https://github.com/sanger-tol/PretextView](https://github.com/sanger-tol/PretextView)"),
        ("purge_dups", context.get("purge_dups_version"), "[https://github.com/dfguan/purge_dups](https://github.com/dfguan/purge_dups)"),
        ("samtools", context.get("samtools_version"), "[https://github.com/samtools/samtools](https://github.com/samtools/samtools)"),
        ("sanger-tol/ascc", "0.1.0", "[https://github.com/sanger-tol/ascc](https://github.com/sanger-tol/ascc)"),
        ("sanger-tol/blobtoolkit", context.get("btk_pipeline_version"), "[https://github.com/sanger-tol/blobtoolkit](https://github.com/sanger-tol/blobtoolkit)"),
        ("sanger-tol/curationpretext", "1.4.2", "[https://github.com/sanger-tol/curationpretext](https://github.com/sanger-tol/curationpretext)"),
        ("Seqtk", "1.3", "[https://github.com/lh3/seqtk](https://github.com/lh3/seqtk)"),
        ("Singularity", "3.9.0", "[https://github.com/sylabs/singularity](https://github.com/sylabs/singularity)"),
        ("TreeVal", "1.4.0", "[https://github.com/sanger-tol/treeval](https://github.com/sanger-tol/treeval)"),
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
