#!/usr/bin/env python3

from typing import Dict


def na(value):
    r"""
    Return a printable value for Table 2.
    Empty strings, None, or the integer 0 become r'\-';
    everything else is converted to str unchanged.
    """
    if value in (None, "", 0, "0"):
        return r"\-"
    return str(value)


def safe_str(value):
    """Convert value to string, avoiding NoneType."""
    return str(value) if value is not None else ""


def flatten_cell(value, digits=2):
    """Flatten table cell to safe string format."""
    if value is None:
        return ""
    if isinstance(value, list):
        # Join with U+202F (narrow no-break space + regular comma)
        return "\u202f, ".join(flatten_cell(v, digits=digits) for v in value)
    if isinstance(value, (int, float)):
        try:
            if isinstance(value, int) or float(value).is_integer():
                return f"{int(value):,}".replace(",", "\u202f")
            else:
                return f"{float(value):,.{digits}f}".replace(",", "\u202f")
        except Exception:
            pass
    return str(value)


def native_cell(value):
    """Escape a value for a native Pandoc pipe-table cell."""
    if value is None:
        return r"\-"
    cell = str(value).replace("\n", " ").replace("|", r"\|").strip()
    return cell if cell else r"\-"


def build_native_table(headers, rows):
    """Build headers/alignment/rows for native Pandoc tables."""
    return {
        "native_headers": [native_cell(h) for h in headers],
        "native_align": [":--"] * len(headers),
        "native_rows": [[native_cell(c) for c in row] for row in rows],
    }


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
        ["**Base count total**", f"{flatten_cell(context.get('pacbio_bases_gb'))} Gb", f"{flatten_cell(context.get('hic_bases_gb'))} Gb"]
    ]

    # Conditionally add RNA column
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
            f"{flatten_cell(context.get('rna_bases_gb'))} Gb"
        ]
        for i in range(len(rows)):
            rows[i].append(rna_values[i])

    native_table = build_native_table(headers, rows)

    return {
        "caption": f"Specimen and sequencing data for *{safe_str(context.get('species'))}* (BioProject {flatten_cell(context.get('bioproject'))})",
        "label": "tbl:table1",
        "alignment": "LLLL" if context.get("rna_sample_accession") else "LLL",   # table formatting in LaTeX/Word
        "width" : [0.25, 0.25, 0.25, 0.25] if context.get("rna_sample_accession") else [0.25, 0.25, 0.25],
        "rows": [",".join(headers)] + [",".join(r) for r in rows],
        **native_table,
    }


def make_table2_rows(context):
    """Construct Table 2: Genome assembly statistics or data, depending on assembly type."""
    rows = []
    asm_type = context.get("assemblies_type")

    mito_raw = context.get("length_mito_kb") or ""
    mito_str = safe_str(mito_raw)
    mito_items = mito_str.replace(" and ", ", ").split(", ")
    mito_label = "Mitochondrion sequences" if len(mito_items) > 1 else "Mitochondrion"

    organelles_cell = f"{mito_label}: {mito_str} kb"

    if asm_type == "hap_asm":
        headers = ["**Genome assembly**", "**Haplotype 1**", "**Haplotype 2**"]
        rows = [
            ["**Assembly name**", safe_str(context.get("hap1_assembly_name")), safe_str(context.get("hap2_assembly_name"))],
            ["**Assembly accession**", safe_str(context.get("hap1_accession")), safe_str(context.get("hap2_accession"))],
            ["**Assembly level**", safe_str(context.get("hap1_assembly_level")), safe_str(context.get("hap2_assembly_level"))],
            ["**Span (Mb)**", safe_str(context.get("hap1_total_length")), safe_str(context.get("hap2_total_length"))],
            ["**Number of chromosomes**", safe_str(context.get("hap1_chromosome_count")), safe_str(context.get("hap2_chromosome_count"))],
            ["**Number of contigs**", safe_str(context.get("hap1_num_contigs")), safe_str(context.get("hap2_num_contigs"))],
            ["**Contig N50**", f"{safe_str(context.get('hap1_contig_N50'))} Mb", f"{safe_str(context.get('hap2_contig_N50'))} Mb"],
            ["**Number of scaffolds**", safe_str(context.get("hap1_num_scaffolds")), safe_str(context.get("hap2_num_scaffolds"))],
            ["**Scaffold N50**", f"{safe_str(context.get('hap1_scaffold_N50'))} Mb", f"{safe_str(context.get('hap2_scaffold_N50'))} Mb"],
            ["**Longest scaffold length (Mb)**", safe_str(context.get("hap1_longest_scaffold_length")), safe_str(context.get("hap2_longest_scaffold_length"))],
            ["**Sex chromosomes**", safe_str(context.get("hap1_sex_chromosomes")), safe_str(context.get("hap2_sex_chromosomes"))],
            ["**Organelles**", organelles_cell, r"\-"]
        ]
        caption   = f"Genome assembly statistics for *{safe_str(context.get('species'))}*"
        label     = "tbl:table2"
        alignment = "LLL"

    elif asm_type == "prim_alt":
        headers = ["**Genome assembly**", "**Primary assembly**"]
        rows = [
            ["**Assembly name**", safe_str(context.get("assembly_name"))],
            ["**Assembly accession**", safe_str(context.get("prim_accession"))],
            ["**Alternate haplotype accession**", safe_str(context.get("alt_accession"))],
            ["**Assembly level**", safe_str(context.get("assembly_level"))],
            ["**Span (Mb)**", safe_str(context.get("total_length"))],
            ["**Number of chromosomes**", safe_str(context.get("chromosome_count"))],
            ["**Number of contigs**", safe_str(context.get("num_contigs"))],
            ["**Contig N50**", f"{safe_str(context.get('contig_N50'))} Mb"],
            ["**Number of scaffolds**", safe_str(context.get("num_scaffolds"))],
            ["**Scaffold N50**", f"{safe_str(context.get('scaffold_N50'))} Mb"],
            ["**Sex chromosomes**", safe_str(context.get("sex_chromosomes"))],
            ["**Organelles**", organelles_cell]
        ]
        caption   = f"Genome assembly data for *{safe_str(context.get('species'))}*"
        label     = "tbl:table2"
        alignment = "LL"

    else:
        raise ValueError(f"Unsupported assemblies_type: {asm_type}")

    native_source_rows = [[na(cell) for cell in row] for row in rows]
    native_table = build_native_table(headers, native_source_rows)

    return {
        "caption":   caption,
        "label":     label,
        "alignment": alignment,
        "rows":      [",".join(map(na, row)) for row in rows],
        **native_table,
    }


def make_table3_rows(context: dict) -> dict:
    """
    Construct Table 3: Chromosomal pseudomolecules in the genome assembly.
    """
    rows = []
    native_headers = []
    native_rows = []
    alignment = ""
    label = "tbl:table3"
    species = context.get("species", "")
    tolid = context.get("tolid", "")
    assemblies_type = context.get("assemblies_type", "")
    dual_haplotype_chromosomes = False

    def format_row(entry: dict, keys: list) -> list:
        return [flatten_cell(entry.get(k)) for k in keys]

    if assemblies_type == "hap_asm":
        hap1_chrom = context.get("hap1_assembly_level") == "chromosome"
        hap2_chrom = context.get("hap2_assembly_level") == "chromosome"

        if hap1_chrom and hap2_chrom:
            dual_haplotype_chromosomes = True
            chromosome_data = context.get("chromosome_data", [])
            caption = f"Chromosomal pseudomolecules in both haplotypes of the genome assembly of *{species}*, {tolid}"
            alignment = "LLLL|LLLL"
            native_headers = [
                "**Haplotype 1**",
                "",
                "",
                "",
                "**Haplotype 2**",
                "",
                "",
                "",
            ]
            native_rows.append([
                "**INSDC accession**",
                "**Name**",
                "**Length (Mb)**",
                "**GC%**",
                "**INSDC accession**",
                "**Name**",
                "**Length (Mb)**",
                "**GC%**",
            ])
            for row in chromosome_data:
                row1 = [flatten_cell(row.get(f"hap1_{k}")) for k in ["INSDC", "molecule", "length", "GC"]]
                row2 = [flatten_cell(row.get(f"hap2_{k}")) for k in ["INSDC", "molecule", "length", "GC"]]
                native_rows.append(row1 + row2)

        elif hap1_chrom:
            hap1_data = context.get("hap1_chromosome_data", [])
            caption = f"Chromosomal pseudomolecules in the haplotype 1 genome assembly of *{species}* {tolid}"
            alignment = "CCCC"
            rows.append("**INSDC accession**,**Molecule**,**Length (Mb)**,**GC%**")
            native_headers = ["**INSDC accession**", "**Molecule**", "**Length (Mb)**", "**GC%**"]
            for entry in hap1_data:
                formatted = format_row(entry, ["INSDC", "molecule", "length", "GC"])
                rows.append(",".join(formatted))
                native_rows.append(formatted)

        else:
            caption = f"No chromosomal-level scaffolds in haplotype 1 assembly of *{species}*"
            alignment = "CCCC"
            rows.append("No chromosome data available.")
            native_headers = ["**Note**"]
            native_rows = [["No chromosome data available."]]

    elif assemblies_type == "prim_alt":
        chrom_data = context.get("chromosome_data", [])
        caption = f"Chromosomal pseudomolecules in the primary genome assembly of *{species}* {tolid}"
        alignment = "CCCC"
        rows.append("**INSDC accession**,**Molecule**,**Length (Mb)**,**GC%**")
        native_headers = ["**INSDC accession**", "**Molecule**", "**Length (Mb)**", "**GC%**"]
        for entry in chrom_data:
            formatted = format_row(entry, ["INSDC", "molecule", "length", "GC"])
            rows.append(",".join(formatted))
            native_rows.append(formatted)

    else:
        caption = f"No chromosomal data available for *{species}*"
        alignment = "CCCC"
        rows.append("No chromosome data available.")
        native_headers = ["**Note**"]
        native_rows = [["No chromosome data available."]]

    if dual_haplotype_chromosomes:
        native_table = {
            "native_headers": native_headers,
            "native_align": [":--"] * 8,
            "native_rows": native_rows,
        }
    else:
        native_table = build_native_table(native_headers, native_rows)

    return {
        "label": label,
        "caption": caption,
        "alignment": alignment,
        "rows": rows,
        **native_table,
    }


def make_table4_rows(context: dict) -> dict:
    """
    Build EBP summary metrics table (Table 4), adapting for hap_asm or prim_alt assembly type.
    """
    rows = []
    native_rows = []
    label = "tbl:table4"
    alignment = "LLL"
    width = [0.3, 0.5, 0.2]
    species = context.get("species", "")
    assemblies_type = context.get("assemblies_type", "")

    rows.append("**Measure**,**Value**,**Benchmark**")

    def csv_cell(value) -> str:
        cell = str(value)
        if any(ch in cell for ch in [",", '"', "\n"]):
            return '"' + cell.replace('"', '""') + '"'
        return cell

    def native_cell(value) -> str:
        cell = str(value).replace("\n", " ").replace("|", r"\|").strip()
        return cell if cell else r"\-"

    def add_row(measure, value, benchmark):
        rows.append(",".join(csv_cell(v) for v in [measure, value, benchmark]))
        native_rows.append({
            "measure": native_cell(measure),
            "value": native_cell(value),
            "benchmark": native_cell(benchmark),
        })

    if assemblies_type == "hap_asm":
        add_row("EBP summary (haplotype 1)", flatten_cell(context.get("ebp_metric")), "6.C.Q40")
        add_row("Contig N50 length", f"{flatten_cell(context.get('hap1_contig_N50'))} Mb", "≥ 1 Mb")
        add_row("Scaffold N50 length", f"{flatten_cell(context.get('hap1_scaffold_N50'))} Mb", "= chromosome N50")
        add_row(
            "Consensus quality (QV)",
            f"Haplotype 1: {flatten_cell(context.get('hap1_QV'))}; haplotype 2: {flatten_cell(context.get('hap2_QV'))}; combined: {flatten_cell(context.get('combined_QV'))}",
            "≥ 40",
        )
        add_row(
            "*k*-mer completeness",
            f"Haplotype 1: {flatten_cell(context.get('hap1_kmer_completeness'))}%; Haplotype 2: {flatten_cell(context.get('hap2_kmer_completeness'))}%; combined: {flatten_cell(context.get('combined_kmer_completeness'))}%",
            "≥ 95%",
        )
        add_row("BUSCO", flatten_cell(context.get("hap1_BUSCO_string")), "S > 90%; D < 5%")
        add_row(
            "Percentage of assembly assigned to chromosomes",
            f"{flatten_cell(context.get('hap1_perc_assembled'))}%",
            "≥ 90%",
        )
    elif assemblies_type == "prim_alt":
        add_row("EBP summary (primary)", flatten_cell(context.get("ebp_metric")), "6.C.Q40")
        add_row("Contig N50 length", f"{flatten_cell(context.get('contig_N50'))} Mb", "≥ 1 Mb")
        add_row("Scaffold N50 length", f"{flatten_cell(context.get('scaffold_N50'))} Mb", "= chromosome N50")
        add_row(
            "Consensus quality (QV)",
            f"Primary: {flatten_cell(context.get('prim_QV'))}; alternate: {flatten_cell(context.get('alt_QV'))}; combined: {flatten_cell(context.get('combined_QV'))}",
            "≥ 40",
        )
        add_row(
            "*k*-mer completeness",
            f"Primary: {flatten_cell(context.get('prim_kmer_completeness'))}%; alternate: {flatten_cell(context.get('alt_kmer_completeness'))}%; combined: {flatten_cell(context.get('combined_kmer_completeness'))}%",
            "≥ 95%",
        )
        add_row("BUSCO", flatten_cell(context.get("BUSCO_string")), "S > 90%; D < 5%")
        add_row(
            "Percentage of assembly assigned to chromosomes",
            f"{flatten_cell(context.get('perc_assembled'))}%",
            "≥ 90%",
        )
    else:
        add_row("Assembly type not recognised", "no metrics available", "")

    caption = f"Earth Biogenome Project summary metrics for the *{species}* assembly"

    notes = ("The EBP summary uses log10(Contig N50); chromosome-level (C) or log10(Scaffold N50); Q (Merqury QV). BUSCO: C=complete; S=single-copy; D=duplicated; F=fragmented; M=missing; n=orthologues")

    return {
        "label": label,
        "caption": caption,
        "alignment": alignment,
        "width": width,
        "rows": rows,
        "native_rows": native_rows,
        "notes": notes
    }


def make_table5_rows(context: dict) -> dict:
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
        ("sanger-tol/curationpretext","1.4.2","[https://github.com/sanger-tol/curationpretext](https://github.com/sanger-tol/curationpretext)"),
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
        "rows": rows,
        **native_table,
    }


def build_all_tables(context: Dict) -> Dict:
    context["tables"] = {
        "table1": make_table1_rows(context),
        "table2": make_table2_rows(context),
        "table3": make_table3_rows(context),
        "table4": make_table4_rows(context),
        "table5": make_table5_rows(context),
    }
    return context
