#!/usr/bin/env python3



import requests
import json
import pandas as pd
from .formatting_utils import format_with_nbsp, clean_numeric_string, safe_convert

def fetch_biosample_info(biosample_acc):
    """
    Fetch biosample information for a given biosample_acc from BioSamples.

    :param biosample_acc: The accession ID of the biosample to fetch information for.

    :return: A dictionary containing the biosample information or an empty dictionary if not found.
    """

    base_url = 'https://www.ebi.ac.uk/biosamples/samples/'
    url = f"{base_url}{biosample_acc}.json"
    #print(url)

    try:
        response = requests.get(url)
        response.encoding = 'utf-8' 
        response.raise_for_status()  # Ensure we raise an error for bad responses
        data = response.json()
        #print(data)
    except requests.RequestException as e:
        print(f"Request failed for biosample_acc {biosample_acc}: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON response for {biosample_acc}. Error: {e}")
        return {}


    characteristics = data.get('characteristics', {})

    biosample_info = {}
    for key, value in characteristics.items():
        if value and isinstance(value, list) and 'text' in value[0]:
            biosample_info[key.replace(' ', '_').lower()] = value[0]['text']

    #print(f"Fetched data from BioSamples for {biosample_acc}: {json.dumps(biosample_info, indent=2)}")
    return biosample_info

def fetch_tolid_from_biosamples(biosample_acc):
    """
    Fetch only the tolid from BioSamples for a given biosample_acc.
    
    :param biosample_acc: The accession ID of the biosample to fetch tolid for.
    :return: The tolid if found, otherwise None.
    """
    try:
        biosample_info = fetch_biosample_info(biosample_acc)
        tolid = biosample_info.get('tolid')
        if tolid:
            print(f"Fetched tolid from BioSamples for {biosample_acc}: {tolid}")
        return tolid
    except Exception as e:
        print(f"Failed to fetch tolid from BioSamples for {biosample_acc}. Error: {e}")
        return None

def get_biosample_tolid_map(biosample_ids):
    """
    For a list of biosample IDs, return a dictionary mapping each to its ToLID.
    If no ToLID is found, the value is None.
    """
    tolid_map = {}
    for biosample_id in biosample_ids:
        tolid = fetch_tolid_from_biosamples(biosample_id)
        tolid_map[biosample_id] = tolid  # Can be None
    return tolid_map

def process_biosamples_sample_dict(row, tech_prefix):
    """
    Process the sample dictionary from BioSamples to limit and format the data.
    """
    # First determine the source individual BioSample (biospecimen)
    source_sample = row.get('sample_derived_from') or row.get('sample_same_as') or ''

    processed_dict = {
        f'{tech_prefix}_collector': row.get('collected_by', '').title(),
        f'{tech_prefix}_collector_institute': row.get('collecting_institution', '').title(),
        f'{tech_prefix}_gal_name': row.get('gal', '').title(),
        f'{tech_prefix}_coll_date': row.get('collection_date', ''),
        f'{tech_prefix}_coll_location': format_location(
            row.get('geographic_location_(region_and_locality)', ''),
            row.get('geographic_location_(country_and/or_sea)', '')).title(),
        f'{tech_prefix}_coll_lat': round(safe_convert(row.get('geographic_location_(latitude)', 0), float, 0.0), 4),
        f'{tech_prefix}_coll_long': round(safe_convert(row.get('geographic_location_(longitude)', 0), float, 0.0), 4),
        f'{tech_prefix}_identifier': row.get('identified_by', '').title(),
        f'{tech_prefix}_identifier_affiliation': row.get('identifier_affiliation', '').title(),
        f'{tech_prefix}_identified_how': row.get('identified_how', '').lower(),
        f'{tech_prefix}_sample_derived_from': source_sample,
        f'{tech_prefix}_sex': row.get('sex', '').lower(),
        f'{tech_prefix}_lifestage': row.get('lifestage', '').lower(),
        f'{tech_prefix}_specimen_id': row.get('specimen_id', ''),
        f'{tech_prefix}_organism_part': row.get('organism_part', '').lower(),
        f'{tech_prefix}_coll_method': row.get('description_of_collection_method', '').lower(),
        f'{tech_prefix}_preserv_method': row.get('preservation_approach', '').lower(),
        f'{tech_prefix}_preservative_solution': row.get('preservative_solution', '').lower(),
        f'{tech_prefix}_species': row.get('scientific_name', ''),
        f'{tech_prefix}_elevation_m': format_with_nbsp(
            safe_convert(clean_numeric_string(row.get('elevation', '0')), float, 0.0),
            as_int=True)
    }

    # Explicitly get `{tech_prefix}_tolid`
    tolid_key = f"{tech_prefix}_tolid"
    processed_dict[tolid_key] = row.get(tolid_key, '')

    return processed_dict



def format_location(region_or_locality, country_or_sea=''):
    """
    Format the collection location using region/locality and country/sea if available.
    Reverses parts in the region string if separated by '|'.
    """
    region_or_locality = region_or_locality.strip() if region_or_locality else ''
    country_or_sea = country_or_sea.strip() if country_or_sea else ''

    # Reverse region components if separated by '|'
    if '|' in region_or_locality:
        parts = [part.strip() for part in region_or_locality.split('|')]
        region_or_locality = ', '.join(reversed(parts))
    elif region_or_locality:
        region_or_locality = region_or_locality.strip()

    if region_or_locality and country_or_sea:
        return f"{region_or_locality}, {country_or_sea}"
    elif region_or_locality:
        return region_or_locality
    elif country_or_sea:
        return country_or_sea
    else:
        return ''




def create_biosample_dict(technology_data):
    """
    Create biosample dictionaries for different technologies.
    For technologies with multiple samples, fetch tissue info from all samples.
    """
    tech_keys = {
        'pacbio': 'pacbio_sample_accession',
        'rna': 'rna_sample_accession',
        'hic': 'hic_sample_accession',
        'isoseq': 'isoseq_sample_accession'
    }

    sample_dicts = {}

    for tech_name, sample_key in tech_keys.items():
        if tech_name in technology_data and sample_key in technology_data[tech_name]:
            biosample_acc_str = technology_data[tech_name][sample_key]

            # Split multiple sample accessions
            if isinstance(biosample_acc_str, str) and ';' in biosample_acc_str:
                biosample_list = [s.strip() for s in biosample_acc_str.split(';')]
            else:
                biosample_list = [biosample_acc_str.strip()] if biosample_acc_str else []

            if not biosample_list:
                continue

            print(f"Fetching data for {tech_name} with {len(biosample_list)} sample(s)")

            try:
                # Fetch primary sample for all shared metadata
                primary_biosample_acc = biosample_list[0]
                sample_dict = fetch_biosample_info(primary_biosample_acc)
                tolid = fetch_tolid_from_biosamples(primary_biosample_acc)

                # Set tolid
                tolid_key = f"{tech_name}_tolid"
                sample_dict[tolid_key] = tolid if tolid else "N/A"

                # If multiple samples, collect all tissue types
                if len(biosample_list) > 1:
                    tissues = []
                    for biosample_acc in biosample_list:
                        info = fetch_biosample_info(biosample_acc)
                        tissue = info.get('organism_part', '')
                        if tissue:
                            tissues.append(tissue.lower())

                    if tissues:
                        unique_tissues = list(dict.fromkeys(tissues))  # Remove duplicates, preserve order
                        sample_dict['organism_part'] = "; ".join(unique_tissues)

                if sample_dict:
                    processed_sample_dict = process_biosamples_sample_dict(sample_dict, tech_name)
                    sample_dicts[tech_name] = processed_sample_dict

            except Exception as e:
                print(f"Failed to fetch data for {biosample_acc_str}. Error: {e}")


    return (
        sample_dicts.get('pacbio', {}),
        sample_dicts.get('rna', {}),
        sample_dicts.get('hic', {}),
        sample_dicts.get('isoseq', {})
    )
