#! usr/bin/env python3

# Rewritten to use ENA Portal API exclusively
# Updated to eliminate dependency on ENA Browser API
# Uses robust field-based queries for all operations

import requests
import pandas as pd
import os
from . import assembly_version_checker, taxonomy_mapper

pd.set_option('display.max_rows', 10)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 120)
pd.set_option('display.max_colwidth', None)

def fetch_data(bioproject_id):
    """Fetches umbrella project data using Portal API."""
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    params = {
        'result': 'study',
        'query': f'study_accession={bioproject_id}',
        'fields': 'study_accession,study_title,tax_id,study_description',
        'format': 'json'
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to get data for project {bioproject_id}")
        return None
    
    data = response.json()
    if not data:
        print(f"No data found for project {bioproject_id}")
        return None
    
    # Return the first matching study (should be exact match)
    for study in data:
        if study.get('study_accession') == bioproject_id:
            return study
    
    # If no exact match, return the first one
    return data[0]

def get_umbrella_project_details(umbrella_data, bioproject_id):
    """Parses the study_title and tax_id for the umbrella bioproject."""
    return {
        'bioproject': bioproject_id,
        'study_title': umbrella_data.get('study_title', umbrella_data.get('study_description', 'No description available')),
        'tax_id': str(umbrella_data.get('tax_id', ''))
    }

def get_child_accessions_for_bioproject(umbrella_data):
    """Gets child project accessions using parent_study_accession field."""
    bioproject_id = umbrella_data.get('study_accession')
    if not bioproject_id:
        return []
    
    print(f"  → Searching for child projects of {bioproject_id}...")
    
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    params = {
        'result': 'study',
        'query': f'parent_study_accession={bioproject_id}',
        'fields': 'study_accession,parent_study_accession,study_title',
        'format': 'json'
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"    ✗ Failed to get child projects for {bioproject_id}")
        return []
    
    data = response.json()
    
    # Extract child projects that have this bioproject as parent
    child_projects = []
    for study in data:
        parent_studies = study.get('parent_study_accession', '')
        # parent_study_accession can contain multiple parents separated by semicolon
        if bioproject_id in parent_studies.split(';'):
            child_projects.append(study['study_accession'])
    
    print(f"    → Found {len(child_projects)} child projects: {child_projects}")
    return child_projects

def fetch_and_update_assembly_details(bioproject):
    """Fetch assembly details for a given BioProject using Portal API."""
    print(f"  → Fetching assemblies for bioproject: {bioproject}")
    
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    params = {
        'result': 'assembly',
        'query': f'study_accession={bioproject}',
        'fields': 'accession,assembly_name,assembly_set_accession,tax_id,study_accession',
        'format': 'json'
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"    ✗ Failed to get assemblies for project {bioproject}")
        return None

    assemblies = response.json()
    print(f"    → Found {len(assemblies)} assemblies")
    
    if assemblies:
        print(f"    → Assembly tax_ids found: {[asm.get('tax_id') for asm in assemblies]}")

    # Update assembly accessions to latest versions
    updated_assemblies = []
    for assembly in assemblies:
        current_accession = assembly.get('assembly_set_accession')
        if current_accession:
            latest_accession, latest_assembly_name = assembly_version_checker.get_latest_revision(current_accession)
            if latest_accession != current_accession:
                print(f"    → Updated assembly_set_accession: {current_accession} -> {latest_accession}")
                assembly['assembly_set_accession'] = latest_accession
            if latest_assembly_name:
                assembly['assembly_name'] = latest_assembly_name
        updated_assemblies.append(assembly)

    return updated_assemblies

def fetch_assembly_details(bioproject):
    """Fetch assembly details and update accession versions."""
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    params = {
        'result': 'assembly',
        'query': f'study_accession={bioproject}',
        'fields': 'accession,assembly_name,assembly_set_accession,tax_id',
        'format': 'json'
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Failed to get data for project {bioproject}")
        return None

    assemblies = response.json()

    # Update each assembly accession to the latest version
    updated_assemblies = []
    for assembly in assemblies:
        current_accession = assembly['accession']
        latest_accession = assembly_version_checker.get_latest_revision(current_accession)
        if latest_accession != current_accession:
            print(f"Updated accession: {current_accession} -> {latest_accession}")
        assembly['accession'] = latest_accession
        updated_assemblies.append(assembly)

    return updated_assemblies

def determine_assembly_type(assembly_dicts, required_tax_id):
    allowed_tax_ids = taxonomy_mapper.get_allowed_tax_ids(required_tax_id)

    # Filter assemblies based on the correct tax_id
    relevant_assemblies = [
        assembly
        for assembly in assembly_dicts
        if assembly.get('tax_id') in allowed_tax_ids
        and not taxonomy_mapper.should_exclude_by_name(assembly.get('assembly_name', ''))
    ]

    primary_assemblies = []
    
    # Check if any assembly contains hap1 or hap2 in its name
    for assembly in relevant_assemblies:
        name = assembly['assembly_name']
        if "hap1" in name or "hap2" in name:
            return 'hap_asm'
    
    # If no haplotypes, check whether there are multiple primary assemblies
    for assembly in relevant_assemblies:
        name = assembly['assembly_name']
        if "alternate haplotype" not in name:  # Primary assemblies exclude alternate haplotypes
            primary_assemblies.append(assembly)
    
    # Otherwise, it must be a prim_alt assembly type
    return 'prim_alt'

def extract_prim_alt_assemblies(assembly_dicts, tax_id, allowed_tax_ids=None):
    """Extract primary and alternate haplotypes from assembly data."""
    primary_assembly_dict = {}
    alternate_haplotype_dict = {}
    allowed_tax_ids = allowed_tax_ids or {tax_id}

    for assembly_dict in assembly_dicts:
        if assembly_dict.get('tax_id') not in allowed_tax_ids:
            continue  # Skip assemblies with mismatched tax_id

        assembly_set_accession = assembly_dict['assembly_set_accession']
        assembly_name = assembly_dict['assembly_name']

        if 'alternate haplotype' in assembly_name.lower():
            alternate_haplotype_dict = {
                "alt_accession": assembly_set_accession,
                "alt_assembly_name": assembly_name,
            }
        else:
            primary_assembly_dict = {
                "prim_accession": assembly_set_accession,
                "prim_assembly_name": assembly_name.replace("alternate haplotype", "").strip(),
            }

    return primary_assembly_dict, alternate_haplotype_dict

def extract_haplotype_assemblies(assembly_dicts, tax_id):
    """Extract the latest haplotype assemblies from the assembly data."""
    hap1_dict = {}
    hap2_dict = {}
    
    for assembly_dict in assembly_dicts:
        name = assembly_dict['assembly_name'].lower()
        accession = assembly_dict['assembly_set_accession']
        
        # Identify haplotype 1 and select the latest version
        if "hap1" in name:
            if not hap1_dict or accession > hap1_dict["hap1_accession"]:
                hap1_dict = {
                    "hap1_accession": accession,
                    "hap1_assembly_name": assembly_dict['assembly_name']
                }
        
        # Identify haplotype 2 and select the latest version
        elif "hap2" in name:
            if not hap2_dict or accession > hap2_dict["hap2_accession"]:
                hap2_dict = {
                    "hap2_accession": accession,
                    "hap2_assembly_name": assembly_dict['assembly_name']
                }

    return hap1_dict, hap2_dict

def extract_multiple_assemblies(assembly_dicts, tax_id):
    """Placeholder function to extract multiple primary assemblies."""
    return {'multiple_assemblies_info': 'Placeholder for multiple assemblies extraction.'}

def get_parent_bioprojects(bioproject_id):
    """Fetches parent projects using Portal API."""
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    params = {
        'result': 'study',
        'query': f'study_accession={bioproject_id}',
        'fields': 'study_accession,parent_study_accession',
        'format': 'json'
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to get data for project {bioproject_id}")
        return {}

    data = response.json()
    if not data:
        return {}
    
    study_info = data[0]
    parent_studies = study_info.get('parent_study_accession', '')
    
    if not parent_studies:
        return {}
    
    parent_project_dict = {}
    parent_projects = []
    
    # parent_study_accession can contain multiple parents separated by semicolon
    parent_accessions = [p.strip() for p in parent_studies.split(';') if p.strip()]
    
    for index, parent_accession in enumerate(parent_accessions, start=1):
        # Get details for each parent project
        parent_params = {
            'result': 'study',
            'query': f'study_accession={parent_accession}',
            'fields': 'study_accession,study_title,project_name',
            'format': 'json'
        }
        
        parent_response = requests.get(url, params=parent_params)
        if parent_response.status_code == 200:
            parent_data = parent_response.json()
            if parent_data:
                parent_info = parent_data[0]
                project_title = parent_info.get('study_title', 'No title available')
                project_name = parent_info.get('project_name', project_title)
                
                # Use project_name if available, otherwise use study_title
                best_name = project_name if project_name else project_title
                
                parent_projects.append({
                    "accession": parent_accession,
                    "name": project_name if project_name else "No name available",
                    "title": project_title,
                    "project_name": best_name
                })
                
                parent_project_dict[f"parentproject{index}_accession"] = parent_accession
                parent_project_dict[f"parentproject{index}_project_name"] = best_name
        else:
            print(f"Failed to fetch parent project details for accession {parent_accession}")
    
    parent_project_dict["parent_projects"] = parent_projects
    return parent_project_dict

if __name__ == "__main__":
    bioproject = "PRJEB71568"  # Example BioProject ID
    print(f"BioProject: {bioproject}")

    context = {}
    umbrella_data = fetch_data(bioproject)
    umbrella_project_dict = get_umbrella_project_details(umbrella_data, bioproject)
    tax_id = umbrella_project_dict['tax_id']
    context.update(umbrella_project_dict)

    # Fetch and update assembly details
    child_accessions = get_child_accessions_for_bioproject(umbrella_data)
    assembly_dicts = [assembly for bioproject_acc in child_accessions for assembly 
                      in (fetch_and_update_assembly_details(bioproject_acc) or [])]

    assemblies_type = determine_assembly_type(assembly_dicts, tax_id)
    context["assemblies_type"] = assemblies_type

    print(f"This is a {assemblies_type} assembly.")
