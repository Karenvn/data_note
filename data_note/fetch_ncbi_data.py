import os
import pandas as pd
import requests
from Bio import Entrez
import xml.etree.ElementTree as ET
import json
from .formatting_utils import format_with_nbsp
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


Entrez.email = os.getenv('ENTREZ_EMAIL', 'default_email')
Entrez.api_key = os.getenv('ENTREZ_API_KEY', 'default_api_key')

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.exceptions.RequestException,))
)
def safe_ncbi_request(url, headers, params=None, timeout=30):
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code in RETRY_STATUS_CODES:
        print(f"Retryable HTTP error {response.status_code}, will retry...")
        raise requests.exceptions.RequestException(f"Status: {response.status_code}")
    response.raise_for_status()
    return response



def parse_ncbi_tax_xml(response_content):
    """Parse the NCBI XML response for taxonomy data."""
    root = ET.fromstring(response_content)
    lineage = []
    ranks = {'class': None, 'family': None, 'order': None, 'phylum': None, 'species': None}
    for taxon in root.iter('Taxon'):
        rank = taxon.find('Rank').text if taxon.find('Rank') is not None else None
        scientific_name = taxon.find('ScientificName').text if taxon.find('ScientificName') is not None else None
        
        # Assign scientific names to their respective ranks
        if rank in ranks:
            ranks[rank] = scientific_name

        # Extract lineage information
        lineage_ex = taxon.find('LineageEx')
        if lineage_ex is not None:
            for element in lineage_ex:
                lineage.append(element.find('ScientificName').text)

    # Remove "cellular organisms" if present at the start of the lineage
    if lineage and lineage[0] == "cellular organisms":
        lineage = lineage[1:]

    return {'lineage': '; '.join(lineage), **ranks}


def get_taxonomy_lineage_and_ranks(taxid):
    """Fetch taxonomic classification and lineage from NCBI."""
    url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=taxonomy&id={taxid}&retmode=xml&api_key={Entrez.api_key}'
    headers = {'User-Agent': f'Python script; {Entrez.email}'}
    response = requests.get(url, headers=headers)
    time.sleep(1) 

    if response.status_code == 200 and response.content:
        try:
            return parse_ncbi_tax_xml(response.content)
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return {}
    else:
        print(f"Failed to fetch data for taxid {taxid}, status code: {response.status_code}")
        return {}
    

def get_datasets_params():
    api_key = Entrez.api_key
    if api_key and api_key != 'default_api_key':
        return {'api_key': api_key}
    return {}


def fetch_and_extract_data(accession):
    """
    Fetch data for the given accession and extract necessary fields including tolid and wgs_project_accession.
    """
    api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/dataset_report"
    headers = {
        'accept': 'application/json',
        'User-Agent': f'Python script; {Entrez.email}'
    }
    params = get_datasets_params()
    response = safe_ncbi_request(api_url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Failed to fetch data for {accession}: HTTP {response.status_code}")
        return None
    
    data = response.json()
    if not data or 'reports' not in data or len(data['reports']) == 0:
        print(f"No valid report data found for {accession}")
        return None

    report = data['reports'][0]
    parsed_assembly_data = {}

    try:
        assembly_stats = report['assembly_stats']

        parsed_assembly_data['assembly_level'] = report['assembly_info']['assembly_level'].lower()
        parsed_assembly_data['total_length'] = format_with_nbsp(round(float(assembly_stats.get('total_sequence_length', 0)) / 1e6, 2))
        parsed_assembly_data['num_contigs'] = format_with_nbsp(int(assembly_stats.get('number_of_contigs', 0)), as_int=True)
        parsed_assembly_data['contig_N50'] = round(float(assembly_stats.get('contig_n50', 0)) / 1e6, 2)
        parsed_assembly_data['num_scaffolds'] = format_with_nbsp(int(assembly_stats.get('number_of_scaffolds', 0)), as_int=True)
        parsed_assembly_data['scaffold_N50'] = round(float(assembly_stats.get('scaffold_n50', 0)) / 1e6, 2)
        parsed_assembly_data['chromosome_count'] = int(assembly_stats.get('total_number_of_chromosomes', 0))
        parsed_assembly_data['genome_length_unrounded'] = float(assembly_stats.get('total_sequence_length', 0))
        parsed_assembly_data['coverage'] = assembly_stats.get('genome_coverage')

    except KeyError as e:
        print(f"Missing key in response data: {e}")
    
    # Extracting tolid from attributes if available
    biosample = report.get('assembly_info', {}).get('biosample', {})
    attributes = biosample.get('attributes', [])
    for attribute in attributes:
        if attribute.get('name') == 'tolid':
            parsed_assembly_data['tolid'] = attribute.get('value')
            break
    
    # Extracting wgs_project_accession from wgs_info if available
    wgs_info = report.get('wgs_info', {})
    parsed_assembly_data['wgs_project_accession'] = wgs_info.get('wgs_project_accession', 'N/A')

    return parsed_assembly_data


def fetch_prim_assembly_info(accession):
    prim_data = fetch_and_extract_data(accession)

    return prim_data


def fetch_assembly_info(hap1_accession, hap2_accession):
    hap1_info = fetch_and_extract_data(hap1_accession)
    hap2_info = fetch_and_extract_data(hap2_accession)

    if hap1_info is None:
        hap1_info = {}
    if hap2_info is None:
        hap2_info = {}

    combined_info = {}
    for key, value in hap1_info.items():
        combined_info[f'hap1_{key}'] = value
    for key, value in hap2_info.items():
        combined_info[f'hap2_{key}'] = value

    # Include tolid and wgs_project_accession in the combined info
    combined_info['tolid'] = hap1_info.get('tolid', 'N/A')
    combined_info['wgs_project_accession'] = hap1_info.get('wgs_project_accession', 'N/A')

    return combined_info

def get_organelle_info(accession):
    """
    Fetch organelle information including lengths and accessions from NCBI sequence reports.
    Returns a dictionary with organelle data structured for easy template insertion.
    """
    api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/sequence_reports"
    headers = {
        'accept': 'application/json',
        'User-Agent': f'Python script; {Entrez.email}'
    }
    params = get_datasets_params()
    response = safe_ncbi_request(api_url, headers=headers, params=params)
    
    data = response.json()
    reports = data.get('reports', [])
    
    if not reports:
        raise Exception("No reports found in the response.")
    
    mitochondria = []
    plastids = []

    for report in reports:
        # Check if this is an organelle based on assigned_molecule_location_type
        location_type = report.get("assigned_molecule_location_type", "")
        chr_name = report.get("chr_name", "").upper()
        
        # Only process assembled-molecule organelles
        if report.get("role") != "assembled-molecule":
            continue
            
        length_kb = round(float(report.get("length", 0)) / 1000, 2)
        genbank_acc = report.get("genbank_accession", "N/A")
        refseq_acc = report.get("refseq_accession", "N/A")
        accession = genbank_acc if genbank_acc != "N/A" else refseq_acc
        
        organelle_data = {
            'length_kb': length_kb,
            'accession': accession,
            'chr_name': report.get("chr_name", ""),
            'gc_percent': report.get("gc_percent", None),
            'description': location_type
        }

        # Identify organelle type by location_type or chr_name
        if location_type == "Mitochondrion" or chr_name in ["MT", "MITO"]:
            mitochondria.append(organelle_data)
        elif location_type == "Chloroplast" or chr_name in ["PLTD", "CP", "CHLO"]:
            plastids.append(organelle_data)
        elif location_type == "Plastid" or "plastid" in location_type.lower():
            plastids.append(organelle_data)

    result = {}
    
    # Store mitochondria info
    if mitochondria:
        result['mitochondria'] = mitochondria
        # For backward compatibility, also include formatted strings
        if len(mitochondria) == 1:
            result['length_mito_kb'] = f"{mitochondria[0]['length_kb']}"
            result['mito_accession'] = mitochondria[0]['accession']
        else:
            # Multiple mitochondria - store as lists
            result['length_mito_kb'] = [m['length_kb'] for m in mitochondria]
            result['mito_accessions'] = [m['accession'] for m in mitochondria]
    
    # Store plastid info
    if plastids:
        result['plastids'] = plastids
        # For backward compatibility, also include formatted strings
        if len(plastids) == 1:
            result['length_plastid_kb'] = f"{plastids[0]['length_kb']}"
            result['plastid_accession'] = plastids[0]['accession']
        else:
            # Multiple plastids - store as lists
            result['length_plastid_kb'] = [p['length_kb'] for p in plastids]
            result['plastid_accessions'] = [p['accession'] for p in plastids]
    
    if not result:
        result['message'] = "No organelles found"
    
    return result


def format_organelle_text(organelle_info):
    """
    Format organelle information for display in templates.
    Returns formatted strings ready for insertion into Jinja2 templates.
    """
    formatted = {}
    
    # Format mitochondria
    if 'mitochondria' in organelle_info:
        mito_list = organelle_info['mitochondria']
        if len(mito_list) == 1:
            m = mito_list[0]
            formatted['mito_text'] = f"length {m['length_kb']} kb ({m['accession']})"
        else:
            mito_parts = [f"{m['length_kb']} kb ({m['accession']})" for m in mito_list]
            formatted['mito_text'] = "lengths " + ", ".join(mito_parts)
    
    # Format plastids
    if 'plastids' in organelle_info:
        plastid_list = organelle_info['plastids']
        if len(plastid_list) == 1:
            p = plastid_list[0]
            formatted['plastid_text'] = f"length {p['length_kb']} kb ({p['accession']})"
        else:
            plastid_parts = [f"{p['length_kb']} kb ({p['accession']})" for p in plastid_list]
            formatted['plastid_text'] = "lengths " + ", ".join(plastid_parts)
    
    return formatted


def get_organelle_template_data(accession):
    """
    Get organelle data formatted for direct use in Jinja2 templates.
    Returns a dictionary with ready-to-use strings.
    """
    try:
        organelle_info = get_organelle_info(accession)
        formatted = format_organelle_text(organelle_info)
        
        # Create template-ready dictionary
        template_data = {
            'has_mitochondria': 'mitochondria' in organelle_info,
            'has_plastids': 'plastids' in organelle_info,
            'mito_display': formatted.get('mito_text', ''),
            'plastid_display': formatted.get('plastid_text', ''),
            'raw_organelle_data': organelle_info  # Include raw data if needed
        }
        
        return template_data
    except Exception as e:
        print(f"Error fetching organelle data: {e}")
        return {
            'has_mitochondria': False,
            'has_plastids': False,
            'error': str(e)
        }


# Optional: If you want to keep similar functionality to the chromosome functions
def get_organelle_table(accession):
    """
    Return a list of organelles similar to the chromosome table format.
    Each entry has: {'INSDC', 'molecule', 'length'(Mb), 'GC'}
    """
    api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/sequence_reports"
    headers = {
        'accept': 'application/json',
        'User-Agent': f'Python script; {Entrez.email}'
    }
    params = get_datasets_params()
    response = safe_ncbi_request(api_url, headers=headers, params=params)
    
    reports = response.json().get('reports', [])
    organelle_list = []
    
    for report in reports:
        location_type = report.get("assigned_molecule_location_type", "")
        chr_name = report.get("chr_name", "").upper()
        
        # Only process assembled-molecule organelles
        if report.get("role") != "assembled-molecule":
            continue
        
        # Check if it's an organelle
        is_organelle = (
            location_type in ["Mitochondrion", "Chloroplast", "Plastid"] or
            chr_name in ["MT", "MITO", "PLTD", "CP", "CHLO"] or
            "plastid" in location_type.lower()
        )
        
        if is_organelle:
            organelle_list.append({
                'INSDC': report.get("genbank_accession", "N/A"),
                'molecule': report.get("chr_name", ""),
                'length': round(float(report.get("length", 0)) / 1e6, 3),  # In Mb, more precision for small organelles
                'GC': report.get("gc_percent", None),
                'type': location_type
            })
    
    return organelle_list

if __name__ == "__main__":

    prim_accession = 'GCA_945910005.1'
    #hap1_accession = 'GCA_964106545.1'
    #hap2_accession  =  'GCA_964106205.1'
    	
    # Fetching primary assembly information
    #assembly_lengths = fetch_prim_assembly_info(prim_accession)

    # Fetching haplotype assembly information
    #assembly_lengths= fetch_assembly_info(hap1_accession, hap2_accession)
    #print(assembly_lengths)


    assembly_info = fetch_prim_assembly_info(prim_accession)
    print(assembly_info)
