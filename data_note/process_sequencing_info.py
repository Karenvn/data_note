#!/usr/bin/env python

# Modified to ensure that the technology_data and seq_data and summarised variables are all added to the context dictionary
# seq_data is iterated through in the template to dynamically list all the read accessions
# technology_data is used to access summary variables and is also used to find biosample details
# summary gives totals of sequencing information for direct variable replacement
# For Markdown output, need to call format_sequencing_rows_for_markdown
# 12 April 2025 Extract "library_name"  to link to extraction_id
# 4 May 2025 Ensuring that PacBio reads from other individuals are not included. 
# 5 May switching to using non-breaking spaces rather than commas as thousands separators to prevent 
# 3 September 2025 The ENA Portal API has changed


import requests
import pandas as pd
import csv
import io
import xml.etree.ElementTree as ET
from .formatting_utils import format_with_nbsp, bytes_to_gb, format_scientific

# Fields to request from ENA Portal API for each result type
include_fields = {
    'read_run': (
        'run_accession,sample_accession,submitted_bytes,read_count,base_count,'
        'library_strategy,library_name,library_construction_protocol,'
        'instrument_platform,instrument_model,study_accession,secondary_study_accession'
    ),
    # 'read_study' no longer used for downstream needs
}

# Fetch study links
def fetch_study_links(bioproject, result_type="read_study"):
    url = "https://www.ebi.ac.uk/ena/portal/api/links/study"
    params = {
        'accession': bioproject,
        'limit': 300,
        'result': result_type,
        'format': 'json',
        'download': 'false'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return {item['study_accession']: item['description'] for item in data if 'study_accession' in item}
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return None

def fetch_study_details(study_acc, result):
    """Fetch ENA Portal API records for a study.

    Returns a list of dict rows (preferred) so callers can extend a list and
    build a DataFrame once at the end.
    """
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    query = f"(study_accession={study_acc} OR secondary_study_accession={study_acc})"
    fields = include_fields[result]
    fmt = "json"

    print("DEBUG study query:",
          {"result": result, "query": query, "fields": fields, "format": fmt, "dataPortal": "ena"})

    params = {
        "result": result,
        "query": query,
        "fields": fields,
        "format": fmt,
        "limit": 0,
        "dataPortal": "ena",
    }

    # 1) Preferred: search (JSON)
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200 and response.text.strip():
            try:
                rows = response.json()
                if isinstance(rows, list):
                    return rows
            except ValueError:
                pass  # fall through to filereport
    except Exception as e:
        print(f"Search request failed for study {study_acc}: {e}")

    # 2) Fallback: filereport (TSV)
    try:
        fr_url = "https://www.ebi.ac.uk/ena/portal/api/filereport"
        fr_params = {
            "accession": study_acc,
            "result": result,
            "fields": fields,
            "format": "tsv",
            "limit": 0,
            "dataPortal": "ena",
        }
        fr_resp = requests.get(fr_url, params=fr_params, timeout=30)
        if fr_resp.status_code == 200 and fr_resp.text.strip():
            import csv, io
            return list(csv.DictReader(io.StringIO(fr_resp.text), delimiter='	'))
        else:
            print(f"Filereport returned no data for study {study_acc}. Status code: {fr_resp.status_code}")
    except Exception as e:
        print(f"Filereport request failed for study {study_acc}: {e}")

    return []

def process_read_study(study_accessions_dict):
    read_study_list = []
    for study_accession in study_accessions_dict:
        # Use read_run (verified to return the needed columns)
        details = fetch_study_details(study_accession, 'read_run')
        if details:
            read_study_list.extend(details)
        else:
            print(f"No run records returned for study {study_accession}.")
    return pd.DataFrame(read_study_list) if read_study_list else pd.DataFrame()


def fetch_read_runs_for_bioproject(bioproject):
    """
    Fetch read_run records directly for a BioProject accession via ENA filereport.
    This is useful when links/study returns no study accessions.
    Returns a list of dict rows.
    """
    url = "https://www.ebi.ac.uk/ena/portal/api/filereport"
    params = {
        "accession": bioproject,
        "result": "read_run",
        "fields": include_fields["read_run"],
        "format": "tsv",
        "limit": 0,
        "dataPortal": "ena",
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"Filereport failed for {bioproject}: HTTP {resp.status_code}")
            return []
        if not resp.text.strip():
            return []
        lines = resp.text.strip().splitlines()
        if len(lines) < 2:
            return []
        return list(csv.DictReader(io.StringIO(resp.text), delimiter="\\t"))
    except Exception as e:
        print(f"Filereport request failed for {bioproject}: {e}")
        return []


def fetch_read_runs_for_bioprojects(bioprojects):
    """
    Fetch read_run records for multiple BioProjects and return a DataFrame.
    """
    rows = []
    for bp in bioprojects:
        rows.extend(fetch_read_runs_for_bioproject(bp))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def fetch_runinfo_rows_for_accession(accession):
    """
    Fetch SRA RunInfo rows for a given accession (BioProject or SRA study).
    Returns a list of dicts in ENA-like column names expected downstream.
    """
    url = "https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/runinfo"
    exp_protocol_cache = {}
    try:
        resp = requests.get(url, params={"acc": accession}, timeout=30)
        if resp.status_code != 200 or not resp.text.strip():
            return []
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = []
        for row in reader:
            size_mb = _safe_float(row.get("size_MB"), 0.0)
            exp_acc = row.get("Experiment", "")
            protocol = ""
            if exp_acc:
                if exp_acc in exp_protocol_cache:
                    protocol = exp_protocol_cache[exp_acc]
                else:
                    protocol = fetch_experiment_protocol(exp_acc)
                    exp_protocol_cache[exp_acc] = protocol
            rows.append({
                "run_accession": row.get("Run", ""),
                "sample_accession": row.get("BioSample", "") or row.get("Sample", ""),
                "submitted_bytes": int(size_mb * 1_000_000),
                "read_count": _safe_int(row.get("spots"), 0),
                "base_count": _safe_int(row.get("bases"), 0),
                "library_strategy": row.get("LibraryStrategy", ""),
                "library_name": row.get("LibraryName", ""),
                "library_construction_protocol": protocol,
                "instrument_platform": row.get("Platform", ""),
                "instrument_model": row.get("Model", ""),
                "study_accession": row.get("BioProject", "") or accession,
                "secondary_study_accession": row.get("SRAStudy", ""),
            })
        return rows
    except Exception as e:
        print(f"RunInfo request failed for {accession}: {e}")
        return []


def fetch_runinfo_for_bioprojects(bioprojects):
    """
    Fetch and combine RunInfo rows for multiple accessions.
    Returns a DataFrame ready for select_columns().
    """
    rows = []
    for acc in bioprojects:
        rows.extend(fetch_runinfo_rows_for_accession(acc))
    if not rows:
        return pd.DataFrame()
    # De-duplicate by run_accession if needed
    seen = set()
    deduped = []
    for row in rows:
        run = row.get("run_accession")
        if run and run in seen:
            continue
        if run:
            seen.add(run)
        deduped.append(row)
    return pd.DataFrame(deduped)


def fetch_experiment_protocol(experiment_accession):
    """
    Fetch LIBRARY_CONSTRUCTION_PROTOCOL for an experiment accession (ERX/SRX).
    Returns empty string if not available.
    """
    url = "https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/exp"
    try:
        resp = requests.get(url, params={"acc": experiment_accession}, timeout=30)
        if resp.status_code != 200 or not resp.text.strip():
            return ""
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return ""
        elem = root.find(".//LIBRARY_CONSTRUCTION_PROTOCOL")
        if elem is not None and elem.text:
            return elem.text.strip()
    except Exception as e:
        print(f"Experiment protocol fetch failed for {experiment_accession}: {e}")
    return ""


def filter_pacbio_rows_by_tolid(read_study_df, tolid, biosample_tolid_map):


    is_pacbio = (
        (read_study_df['library_strategy'] == 'WGS') &
        (read_study_df['instrument_platform'] == 'PACBIO_SMRT')
    )

    def keep_row(row):
        if not is_pacbio.loc[row.name]:
            return True  # Keep non-PacBio rows
        biosample_id = row['sample_accession']
        tolid_in_record = biosample_tolid_map.get(biosample_id)
        return tolid_in_record is None or tolid_in_record == tolid

    filtered_df = read_study_df[read_study_df.apply(keep_row, axis=1)]
    return filtered_df


def select_columns(df):
    numeric_cols = ['fastq_bytes', 'submitted_bytes', 'read_count', 'base_count']
    # Ensure all expected numeric columns exist
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # Ensure required text columns exist
    for col in ['library_construction_protocol', 'library_name', 'instrument_model',
                'instrument_platform', 'study_accession', 'run_accession', 'sample_accession']:
        if col not in df.columns:
            df[col] = ''

    return df[['study_accession', 'run_accession', 'sample_accession',
               'fastq_bytes', 'submitted_bytes', 'read_count',
               'instrument_model', 'base_count', 'library_strategy', 'library_name',
               'library_construction_protocol', 'instrument_platform']]

def extract_technology_data(df):
    tech_data = {
        'pacbio': {},
        'hic': {},
        'chromium': {},
        'rna': {}
    }
    prefix_map = {
        ('PACBIO_SMRT', 'WGS'): 'pacbio',
        ('ILLUMINA', 'Hi-C'): 'hic',
        ('ILLUMINA', 'WGS'): 'chromium',
        ('ILLUMINA', 'RNA-Seq'): 'rna'
    }
    for _, row in df.iterrows():
        tech_key = prefix_map.get((row['instrument_platform'], row['library_strategy']))
        if tech_key:
            tech_dict = tech_data[tech_key]
            tech_dict[f'{tech_key}_sample_accession'] = row['sample_accession']
            tech_dict[f'{tech_key}_instrument_model'] = row['instrument_model']
            tech_dict[f'{tech_key}_library_construction_protocol'] = row['library_construction_protocol']
            tech_dict[f'{tech_key}_library_name'] = row['library_name']
            tech_dict[f'{tech_key}_base_count_gb'] = format_with_nbsp(round((row['base_count']) / 1e9, 2))
            tech_dict[f'{tech_key}_read_count_millions'] = format_with_nbsp(round((row['read_count']) / 1e6, 2))
            
    return tech_data

# Organise sequencing data
def organise_sequencing_data(df):
    platforms = {
        'Hi-C': [],
        'PacBio': [],
        'Chromium': [],
        'RNA': []
    }

    for _, row in df.iterrows():
        entry = {
            'read_accession': row['run_accession'],
            'sample_accession': row['sample_accession'],
            'fastq_bytes': str(round(bytes_to_gb(row['fastq_bytes']), 2)), 
            'submitted_bytes': str(round(bytes_to_gb(row['submitted_bytes']), 2)), 
            'read_count': str(format_scientific(row['read_count'])), 
            'instrument_model': row['instrument_model'],
            'base_count_gb': str(round((row['base_count']) / 1e9, 2))
        }

        if row['library_strategy'] == 'WGS' and row['instrument_platform'] == 'PACBIO_SMRT':
            platforms['PacBio'].append(entry)
        elif row['library_strategy'] == 'WGS' and row['instrument_platform'] == 'ILLUMINA':
            platforms['Chromium'].append(entry)
        elif row['library_strategy'] == 'RNA-Seq' and row['instrument_platform'] == 'ILLUMINA':
            platforms['RNA'].append(entry)
        elif row['library_strategy'] == 'Hi-C' and row['instrument_platform'] == 'ILLUMINA':
            platforms['Hi-C'].append(entry)
        else:
            print(f"Row not processed: {row}")

    return platforms


def summarise_sequencing_totals(df, technology_data):
    """
    Summarise sequencing totals and include sample accessions for each technology.

    Args:
        df (DataFrame): Dataframe containing sequencing data.
        technology_data (dict): Technology-specific data, including sample accessions.

    Returns:
        dict: A dictionary summarising sequencing totals and sample accessions.
    """
    summary = {
        'pacbio_total_reads': 0,
        'pacbio_total_bases': 0,
        'pacbio_reads_millions': 0,
        'pacbio_bases_gb': 0,
        'hic_total_reads': 0,
        'hic_total_bases': 0,
        'hic_reads_millions': 0,
        'hic_bases_gb': 0,
        #'chromium_total_reads': 0,
        #'chromium_total_bases': 0,
        #'chromium_reads_millions': 0,
        #'chromium_bases_gb': 0,
        'rna_total_reads': 0,
        'rna_total_bases': 0,
        'rna_reads_millions': 0,
        'rna_bases_gb': 0
    }

    # Include sample accessions from technology_data
    if 'pacbio' in technology_data:
        summary['pacbio_sample_accession'] = technology_data['pacbio'].get('pacbio_sample_accession', '')
    if 'hic' in technology_data:
        summary['hic_sample_accession'] = technology_data['hic'].get('hic_sample_accession', '')
    if 'rna' in technology_data:
        summary['rna_sample_accession'] = technology_data['rna'].get('rna_sample_accession', '')

    for _, row in df.iterrows():
        read_count = row['read_count'] if pd.notnull(row['read_count']) else 0
        base_count = row['base_count'] if pd.notnull(row['base_count']) else 0

        if row['library_strategy'] == 'WGS' and row['instrument_platform'] == 'PACBIO_SMRT':
            summary['pacbio_total_reads'] += read_count
            summary['pacbio_total_bases'] += base_count
        elif row['library_strategy'] == 'Hi-C' and row['instrument_platform'] == 'ILLUMINA':
            summary['hic_total_reads'] += read_count
            summary['hic_total_bases'] += base_count
        #elif row['library_strategy'] == 'WGS' and row['instrument_platform'] == 'ILLUMINA':
            #summary['chromium_total_reads'] += read_count
            #summary['chromium_total_bases'] += base_count
        elif row['library_strategy'] == 'RNA-Seq' and row['instrument_platform'] == 'ILLUMINA':
            summary['rna_total_reads'] += read_count
            summary['rna_total_bases'] += base_count

    # Calculate reads in millions and bases in gigabases
    summary['pacbio_reads_millions'] = summary['pacbio_total_reads'] / 1e6
    summary['pacbio_bases_gb'] = summary['pacbio_total_bases'] / 1e9
    summary['hic_reads_millions'] = summary['hic_total_reads'] / 1e6
    summary['hic_bases_gb'] = summary['hic_total_bases'] / 1e9
    #summary['chromium_reads_millions'] = summary['chromium_total_reads'] / 1e6
    #summary['chromium_bases_gb'] = summary['chromium_total_bases'] / 1e9
    summary['rna_reads_millions'] = summary['rna_total_reads'] / 1e6
    summary['rna_bases_gb'] = summary['rna_total_bases'] / 1e9

    # Apply format_with_nbsp to the totals
    for key in summary:
        if isinstance(summary[key], (int, float)):
            summary[key] = format_with_nbsp(summary[key])

    return summary

def summarise_sequencing_totals(df, technology_data):
    """
    Summarise sequencing totals, include sample accessions, and extract instruments for each technology.

    Args:
        df (DataFrame): Dataframe containing sequencing data.
        technology_data (dict): Technology-specific data, including sample accessions.

    Returns:
        dict: A dictionary summarising sequencing totals, sample accessions, and instruments.
    """
    summary = {
        'pacbio_total_reads': 0,
        'pacbio_total_bases': 0,
        'pacbio_reads_millions': 0,
        'pacbio_bases_gb': 0,
        'hic_total_reads': 0,
        'hic_total_bases': 0,
        'hic_reads_millions': 0,
        'hic_bases_gb': 0,
        #'chromium_bases_gb': 0,
        #'chromium_total_reads': 0,
        #'chromium_total_bases': 0,
        #'chromium_reads_millions': 0,
        'rna_total_reads': 0,
        'rna_total_bases': 0,
        'rna_reads_millions': 0,
        'rna_bases_gb': 0,
        'pacbio_instrument': '',
        'hic_instrument': '',
        'rna_instrument': ''
    }

    # Include sample accessions from technology_data
    if 'pacbio' in technology_data:
        summary['pacbio_sample_accession'] = technology_data['pacbio'].get('pacbio_sample_accession', '')
        summary['pacbio_instrument'] = technology_data['pacbio'].get('pacbio_instrument_model', '')
    if 'hic' in technology_data:
        summary['hic_sample_accession'] = technology_data['hic'].get('hic_sample_accession', '')
        summary['hic_instrument'] = technology_data['hic'].get('hic_instrument_model', '')
    if 'rna' in technology_data:
        summary['rna_sample_accession'] = technology_data['rna'].get('rna_sample_accession', '')
        summary['rna_instrument'] = technology_data['rna'].get('rna_instrument_model', '')

    # Summarise reads and bases by technology
    for _, row in df.iterrows():
        read_count = row['read_count'] if pd.notnull(row['read_count']) else 0
        base_count = row['base_count'] if pd.notnull(row['base_count']) else 0

        if row['library_strategy'] == 'WGS' and row['instrument_platform'] == 'PACBIO_SMRT':
            summary['pacbio_total_reads'] += read_count
            summary['pacbio_total_bases'] += base_count
        elif row['library_strategy'] == 'Hi-C' and row['instrument_platform'] == 'ILLUMINA':
            summary['hic_total_reads'] += read_count
            summary['hic_total_bases'] += base_count
        elif row['library_strategy'] == 'RNA-Seq' and row['instrument_platform'] == 'ILLUMINA':
            summary['rna_total_reads'] += read_count
            summary['rna_total_bases'] += base_count

    # Calculate reads in millions and bases in gigabases
    summary['pacbio_reads_millions'] = summary['pacbio_total_reads'] / 1e6
    summary['pacbio_bases_gb'] = summary['pacbio_total_bases'] / 1e9
    summary['hic_reads_millions'] = summary['hic_total_reads'] / 1e6
    summary['hic_bases_gb'] = summary['hic_total_bases'] / 1e9
    summary['rna_reads_millions'] = summary['rna_total_reads'] / 1e6
    summary['rna_bases_gb'] = summary['rna_total_bases'] / 1e9

    # Apply format_with_nbsp to the totals
    for key in summary:
        if isinstance(summary[key], (int, float)):
            summary[key] = format_with_nbsp(summary[key])

    return summary

def check_pacbio_protocol(df):
    """
    Extract all unique PacBio library construction protocols.

    Args:
        df (DataFrame): DataFrame containing sequencing data.

    Returns:
        list: A list of unique PacBio library construction protocols used.
    """
    # Make a copy of the DataFrame to avoid modifying the original
    df = df.copy()

    # Ensure data consistency: strip and uppercase relevant columns
    df.loc[:, 'library_strategy'] = df['library_strategy'].str.strip().str.upper()
    df.loc[:, 'instrument_platform'] = df['instrument_platform'].str.strip().str.upper()
    df.loc[:, 'library_construction_protocol'] = df['library_construction_protocol'].astype(str)

    # Filter rows for PacBio WGS data
    pacbio_df = df[
        (df['library_strategy'] == 'WGS') & 
        (df['instrument_platform'] == 'PACBIO_SMRT')
    ]

    # Extract and return all unique library construction protocols
    pacbio_protocols = pacbio_df['library_construction_protocol'].unique().tolist()

    # Debug: Print the extracted protocols
    print("Identified PacBio protocols:", pacbio_protocols)

    return pacbio_protocols


def get_run_accession_lists(seq_data):
    # To produce lists of read accessions
    key_map = {
        'PacBio': 'pacbio',
        'Hi-C': 'hic',
        'RNA': 'rna'
    }
    run_accessions = {}
    for original_key, new_key in key_map.items():
        runs = seq_data.get(original_key, [])
        run_ids = [run['read_accession'] for run in runs if 'read_accession' in run]
        run_accessions[f"{new_key}_run_accessions"] = "; ".join(run_ids)

    return run_accessions

# Format sequencing rows for Markdown
def format_sequencing_rows_for_markdown(seq_data):
    rows = []
    for technology, runs in seq_data.items():
        for run in runs:
            formatted_row = (
                f'"{run["library_construction_protocol"]} {run["instrument_model"]}",'
                f'"{run["read_accession"]}",'
                f'"{run["read_count"]} million reads",'
                f'"{run["base_count_gb"]} Gb"'
            )
            rows.append(formatted_row)
    return "\n".join(rows)


if __name__ == "__main__":
    def main():

        def process_sequencing_workflow(bioproject):
            print(f"Processing sequencing information for bioproject {bioproject}.")
            study_accessions_dict = fetch_study_links(bioproject)
            print("DEBUG study_accessions_dict:", study_accessions_dict)
            if not study_accessions_dict:
                print("No study accessions found.")
                return {}  

            read_study_df = process_read_study(study_accessions_dict)
            technology_df = select_columns(read_study_df)
            technology_data = extract_technology_data(technology_df)
            seq_data = organise_sequencing_data(technology_df)
            summary = summarise_sequencing_totals(technology_df, technology_data)
            
            pacbio_protocols = check_pacbio_protocol(technology_df)
            summary['pacbio_protocols'] = pacbio_protocols 
            print("Technology_data: ", technology_data, "seq_data:", seq_data)
            
            return {"technology_data": technology_data, "seq_data": seq_data, **summary}


        bioproject = "PRJEB70970"
        result = process_sequencing_workflow(bioproject)
        print("\n✅ Output from process_sequencing_workflow:")
        for key, value in result.items():
            print(f"{key}: {value}")
    
    main()
