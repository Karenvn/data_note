#!/usr/bin/env python

# 15 January 2025 edited to have different functions for prim_alt assemblies and haplotype assemblies.
# 16 June updated to use new GenomeScope naming convention and to use the format with nbsp convention
# 17 June updated to parse the latest Merqury run
# 10 Sept use absolute paths for server_data

import pandas as pd
import os
import logging
from pathlib import Path
import re
import logging
from .formatting_utils import format_with_nbsp

SERVER_DATA = os.getenv("DATA_NOTE_SERVER_DATA", str(Path.home() / "server_data"))


def parse_genomescope(tolid):
    """Parse GenomeScope2 results."""
    script_dir = Path(__file__).resolve().parent
    gscope_dir = Path(SERVER_DATA) / "gscope_results" / tolid
    # Try both naming conventions
    candidates = [
        gscope_dir / "fastk_genomescope_summary.txt",         # new
        gscope_dir / f"{tolid}.k31_summary.txt"               # old
    ]

    file_path = None
    for candidate in candidates:
        if candidate.exists():
            file_path = candidate
            break

    results = {
        "gscope_size": None,
        "gscope_het": None,
        "gscope_repeat": None,
        "gscope_error": None,
        "gscope_unique": None,
    }

    if file_path is None:
        logging.error(f"GenomeScope summary file not found for {tolid} in {gscope_dir}")
        return results

    try:
        with open(file_path, 'r') as file:
            size_max = None
            for line in file:
                if "Genome Haploid Length" in line:
                    match = re.search(r"(NA|\d[\d,.]*)\s*bp\s+(\d[\d,.]*)\s*bp", line)
                    if match:
                        max_value = match.group(2).replace(',', '').strip()
                        if max_value and max_value.lower() != "na":
                            size_max = float(max_value)
                            results["gscope_size"] = format_with_nbsp(round((size_max / 1e6), 2))
                        else:
                            logging.warning("Genome Haploid Length max value is NA or missing.")
                    else:
                        logging.warning("Failed to parse Genome Haploid Length line.")

                if "Heterozygous (ab)" in line:
                    match = re.search(r"([\d,.]+)%\s+([\d,.]+)%", line)
                    if match:
                        het_min = float(match.group(1).replace(',', ''))
                        het_max = float(match.group(2).replace(',', ''))
                        results["gscope_het"] = format_with_nbsp((het_min + het_max) / 2)

                if "Genome Repeat Length" in line and size_max:
                    match = re.search(r"([\d,.]+)\s*bp\s+([\d,.]+)\s*bp", line)
                    if match:
                        repeat_max = float(match.group(2).replace(',', ''))
                        results["gscope_repeat"] = format_with_nbsp(repeat_max / size_max * 100)

                if "Read Error Rate" in line:
                    match = re.search(r"([\d,.]+)%", line)
                    if match:
                        error_rate = float(match.group(1).replace(',', ''))
                        results["gscope_error"] = error_rate

                if "Genome Unique Length" in line and size_max:
                    match = re.search(r"([\d,.]+)\s*bp\s+([\d,.]+)\s*bp", line)
                    if match:
                        unique_max = float(match.group(2).replace(',', ''))
                        results["gscope_unique"] = (unique_max / size_max * 100)

            if size_max is None:
                logging.error("Genome size (size_max) could not be parsed.")

    except Exception as e:
        logging.exception(f"Error parsing the file: {e}")

    return results



def _parse_last_block(path: Path, header_pattern: str, n_rows: int):
    """
    Read all non-blank lines from `path`.
    Find the last line matching `header_pattern` (a regex),
    then collect the next `n_rows` lines of data.
    Split each line on whitespace/tabs and return as list of lists.
    """
    lines = [L for L in path.read_text().splitlines() if L.strip()]
    hdr_idxs = [i for i, L in enumerate(lines) if re.match(header_pattern, L)]
    if not hdr_idxs:
        raise ValueError(f"No header matching {header_pattern!r} in {path}")
    start = hdr_idxs[-1] + 1
    block = lines[start:start + n_rows]
    return [re.split(r"\s+", row.strip()) for row in block]

def read_merqury_results(tolid: str):
    """
    Read the final three‐row block from:
      - {tolid}.completeness.stats
      - {tolid}.qv

    Returns (df_stats, df_qv), or (None, None) on error.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    merqury_dir = Path(SERVER_DATA) / "merqury_results" / tolid
    #base = Path(__file__).resolve().parent.parent / 'server_data' / 'merqury_results' / tolid
    stats_file = merqury_dir / f"{tolid}.completeness.stats"
    qv_file    = merqury_dir / f"{tolid}.qv"

    if not stats_file.exists() or not qv_file.exists():
        logging.error(f"Missing files for {tolid}:\n"
                      f"  {stats_file}\n"
                      f"  {qv_file}")
        return None, None

    # --- completeness.stats: header "Assembly  Region  Found  Total  % Covered" + 3 rows ---
    comp_data = _parse_last_block(
        stats_file,
        header_pattern=r"^Assembly\s+Region",
        n_rows=3
    )
    df_stats = pd.DataFrame(
        comp_data,
        columns=['Assembly', 'Region', 'Found', 'Total', '% Covered']
    )

    # --- .qv: header "Assembly  No Support  Total  Error %  QV" + 3 rows ---
    qv_data = _parse_last_block(
        qv_file,
        header_pattern=r"^Assembly\s+No Support",
        n_rows=3
    )
    df_qv = pd.DataFrame(
        qv_data,
        columns=['Assembly', 'No Support', 'Total', 'Error %', 'QV']
    )

    logging.info(f"Parsed {tolid}.completeness.stats and {tolid}.qv")
    return df_stats, df_qv



def get_merqury_results_prim_alt(tolid):
    """Process Merqury metrics for prim_alt assemblies."""
    df1, df2 = read_merqury_results(tolid)
    if df1 is None or df2 is None:
        return {}

    def safe_extract(df, column, assembly, default=None):
        try:
            return df.loc[df['Assembly'] == assembly, column].iloc[0]
        except IndexError:
            return default

    return {
        'prim_QV': safe_extract(df2, 'QV', 'primary'),
        'alt_QV': safe_extract(df2, 'QV', 'alt'),
        'combined_QV': safe_extract(df2, 'QV', 'both'),
        'prim_kmer_completeness': safe_extract(df1, '% Covered', 'primary'),
        'alt_kmer_completeness': safe_extract(df1, '% Covered', 'alt'),
        'combined_kmer_completeness': safe_extract(df1, '% Covered', 'both'),
    }

def get_merqury_results_haplotype_assemblies(tolid):
    """Process Merqury metrics for haplotypes assembly."""
    df1, df2 = read_merqury_results(tolid)
    if df1 is None or df2 is None:
        return {}

    def safe_extract(df, column, assembly, default=None):
        try:
            return df.loc[df['Assembly'] == assembly, column].iloc[0]
        except IndexError:
            return default

    return {
        'hap1_QV': safe_extract(df2, 'QV', 'hap1'),
        'hap2_QV': safe_extract(df2, 'QV', 'hap2'),
        'combined_QV': safe_extract(df2, 'QV', 'both'),
        'hap1_kmer_completeness': safe_extract(df1, '% Covered', 'hap1'),
        'hap2_kmer_completeness': safe_extract(df1, '% Covered', 'hap2'),
        'combined_kmer_completeness': safe_extract(df1, '% Covered', 'both'),
    }


def main():
    tolid = "ilNymAnti1"
    download_dir = "./downloads"
    completeness_metrics = read_merqury_results(tolid)

    gscope_results = parse_genomescope(tolid)

    # Print the parsed data
    print("Parsed Merqury info:", completeness_metrics)
    print("Parsed GenomeScope info:", gscope_results)

    image_path = copy_merqury_image(tolid, download_dir)

    if image_path:
        print(f"Image downloaded to: {image_path}")
    else:
        print("Failed to download image.")

    if __name__ == "__main__":
        main()
