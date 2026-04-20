#!/usr/bin/env python3

import logging
import requests
import re
from collections import Counter
from .formatting_utils import format_with_nbsp
from .text_utils import oxford_comma_list

logger = logging.getLogger(__name__)


def extract_year_from_authorship(authorship):
    """
    Extract the year from a taxonomic authorship string.
    
    Args:
        authorship (str): Authorship string like "Linnaeus, 1758" or "(Smith, 1895)"
    
    Returns:
        int or None: The year if found, None otherwise
    """
    if not authorship:
        return None
    
    # Look for 4-digit years (1700-2099)
    import re
    year_match = re.search(r'\b(17|18|19|20)\d{2}\b', authorship)
    if year_match:
        return int(year_match.group())
    return None


def find_earliest_genus(synonyms_list, current_genus, specific_epithet):
    """
    Find the chronologically earliest genus from synonyms list.
    
    Args:
        synonyms_list (list): List of synonym records from GBIF
        current_genus (str): Current accepted genus
        specific_epithet (str): Species epithet
    
    Returns:
        tuple: (original_genus, original_combination, year) or (None, None, None)
    """
    candidates = []
    
    for synonym in synonyms_list:
        syn_canonical = synonym.get("canonicalName", "")
        syn_authorship = synonym.get("authorship", "").strip()
        syn_status = synonym.get("taxonomicStatus", "")
        
        logger.info("Analyzing synonym candidate: %s (%s)", syn_canonical, syn_authorship)
        
        # Extract genus from canonical name
        if syn_canonical and ' ' in syn_canonical:
            parts = syn_canonical.split()
            if len(parts) >= 2:
                syn_genus = parts[0]
                syn_epithet = parts[1]
                
                # Only consider if it's the same species epithet but different genus
                if (syn_genus != current_genus and 
                    syn_epithet == specific_epithet and
                    syn_status in ["SYNONYM", "HETEROTYPIC_SYNONYM", "HOMOTYPIC_SYNONYM"]):
                    
                    year = extract_year_from_authorship(syn_authorship)
                    candidates.append({
                        'genus': syn_genus,
                        'combination': syn_canonical,
                        'authorship': syn_authorship,
                        'year': year,
                        'status': syn_status
                    })
                    logger.info("Found synonym candidate genus %s (year: %s)", syn_genus, year)
    
    if not candidates:
        return None, None, None
    
    # Sort by year (earliest first), handling None years
    candidates.sort(key=lambda x: x['year'] if x['year'] is not None else 9999)
    
    earliest = candidates[0]
    logger.info(
        "Earliest genus: %s from %s (was %s)",
        earliest["genus"],
        earliest["year"],
        earliest["combination"],
    )
    
    # Show other candidates for debugging
    if len(candidates) > 1:
        others = [f"{c['genus']} ({c['year']})" for c in candidates[1:]]
        logger.info("Other genera in chronological order: %s", ", ".join(others))
    
    return earliest['genus'], earliest['combination'], earliest['year']#!/usr/bin/env python3

def normalize_authorship(authorship_str, original_genus=None, current_genus=None):
    """
    Normalize taxonomic authorship formatting, trusting GBIF first but verifying against taxonomic history.
    
    Args:
        authorship_str (str): Raw authorship string from GBIF
        original_genus (str): Original genus if known AND different from current
        current_genus (str): Current genus
    
    Returns:
        tuple: (formatted_authorship, verification_status)
    """
    if not authorship_str:
        return "", "NO_AUTHORSHIP"
    
    # Clean up the authorship string - FIXED REGEX
    authorship = authorship_str.strip()
    
    # Check what GBIF provided
    gbif_has_brackets = '(' in authorship and ')' in authorship
    
    # Clean version for verification (remove any existing brackets)
    clean_authorship = re.sub(r'[\[\]()]', '', authorship).strip()
    
    # Only attempt verification if we have positive evidence of taxonomic history
    if original_genus and current_genus:
        # We have evidence that the species was moved between genera
        should_have_brackets = True
        
        if gbif_has_brackets and should_have_brackets:
            verification_status = "CORRECT_WITH_BRACKETS"
            logger.info("GBIF correctly has brackets: %s -> %s", original_genus, current_genus)
            return authorship, verification_status  # Trust GBIF's formatting
        elif not gbif_has_brackets and should_have_brackets:
            verification_status = "GBIF_WRONG_MISSING_BRACKETS"
            logger.warning("GBIF missing brackets: %s -> %s", original_genus, current_genus)
            return f"({clean_authorship})", verification_status  # Add brackets
    elif not original_genus:
        # We couldn't determine the original genus - trust GBIF
        if gbif_has_brackets:
            verification_status = "TRUST_GBIF_WITH_BRACKETS"
            logger.info("Couldn't determine original genus, trusting GBIF brackets")
            return authorship, verification_status
        else:
            verification_status = "TRUST_GBIF_NO_BRACKETS" 
            logger.info("Couldn't determine original genus, trusting GBIF without brackets")
            return clean_authorship, verification_status
    else:
        # original_genus == current_genus, so no brackets should be needed
        should_have_brackets = False
        
        if gbif_has_brackets and not should_have_brackets:
            verification_status = "GBIF_WRONG_HAS_BRACKETS"
            logger.warning("GBIF has brackets but shouldn't: species not moved from original genus")
            return clean_authorship, verification_status  # Remove brackets
        elif not gbif_has_brackets and not should_have_brackets:
            verification_status = "CORRECT_NO_BRACKETS"
            logger.info("GBIF correctly has no brackets: original placement maintained")
            return clean_authorship, verification_status


def fetch_taxonomy_info(species_name, include_history=True):
    """
    Finds the taxonomic authority and common name(s) for a given species.
    
    Args:
        species_name (str): The species name in the format 'Genus species'
        include_history (bool): Whether to fetch taxonomic history for proper bracketing
    
    Returns:
        dict: A dictionary containing taxonomic authority, common name, GBIF usage key, and GBIF URL
              Same format as original function - fully backward compatible
    """
    tax_dict = {
        "tax_auth": "",
        "common_name": "",
        "gbif_url": "",
        "gbif_usage_key": "",
        "original_combination": "",  # New field - won't break existing code
        "current_combination": species_name  # New field - won't break existing code
    }

    try:
        current_genus, specific_epithet = species_name.split(" ")
    except ValueError:
        return tax_dict

    # Step 1: Get the basic species match
    match_url = f"https://api.gbif.org/v1/species/match?specificEpithet={specific_epithet}&strict=true&genus={current_genus}"
    
    try:
        response = requests.get(match_url, timeout=10)
        response.raise_for_status()
        match_data = response.json()
        
        usage_key = match_data.get("usageKey")
        if not usage_key:
            return tax_dict
            
        logger.info("GBIF usage key: %s", usage_key)
        
        # Step 2: Get detailed species information
        species_url = f"https://api.gbif.org/v1/species/{usage_key}"
        species_response = requests.get(species_url, timeout=10)
        species_response.raise_for_status()
        species_data = species_response.json()
        
        # Extract basic information
        raw_authorship = species_data.get("authorship", "").strip()
        tax_dict["common_name"] = species_data.get("vernacularName", "")
        tax_dict["gbif_url"] = species_url
        tax_dict["gbif_usage_key"] = usage_key
        
        # Step 3: Try to get nomenclatural/taxonomic history for proper bracketing
        original_genus = current_genus  # Default assumption
        
        if include_history:
            # Method 1: Check if there's a basionym (original name) - but only if it's actually different
            basionym_key = species_data.get("basionymKey")
            if basionym_key and basionym_key != usage_key:
                basionym_url = f"https://api.gbif.org/v1/species/{basionym_key}"
                try:
                    basionym_response = requests.get(basionym_url, timeout=10)
                    basionym_response.raise_for_status()
                    basionym_data = basionym_response.json()
                    
                    basionym_genus = basionym_data.get("genus", current_genus)
                    basionym_species = basionym_data.get("species", "")
                    
                    # Only use basionym if it has a different genus (indicating a real transfer)
                    if basionym_genus and basionym_genus != current_genus:
                        original_genus = basionym_genus
                        if basionym_species:
                            tax_dict["original_combination"] = basionym_species
                            logger.info("Found basionym with different genus: %s", basionym_species)
                        
                        # Use basionym authorship if available
                        basionym_authorship = basionym_data.get("authorship", "")
                        if basionym_authorship:
                            raw_authorship = basionym_authorship
                    else:
                        logger.info("Basionym has same genus (%s), ignoring...", basionym_genus)
                        
                except requests.RequestException as e:
                    logger.warning("Could not fetch basionym information: %s", e)
            
            # Method 2: Check synonyms API for historical information
            if original_genus == current_genus:  # Only if we haven't found original genus yet
                try:
                    synonyms_url = f"https://api.gbif.org/v1/species/{usage_key}/synonyms"
                    synonyms_response = requests.get(synonyms_url, timeout=10)
                    synonyms_response.raise_for_status()
                    synonyms_data = synonyms_response.json()
                    
                    synonyms_list = synonyms_data.get("results", [])
                    logger.info("Found %s synonyms", len(synonyms_list))
                    
                    # Find the chronologically earliest genus
                    earliest_genus, earliest_combination, earliest_year = find_earliest_genus(
                        synonyms_list, current_genus, specific_epithet
                    )
                    
                    if earliest_genus:
                        original_genus = earliest_genus
                        tax_dict["original_combination"] = earliest_combination
                        logger.info(
                            "Found original genus from chronological analysis: %s (was %s, %s)",
                            original_genus,
                            earliest_combination,
                            earliest_year,
                        )
                        
                except requests.RequestException as e:
                    logger.warning("Could not fetch synonyms: %s", e)
        
        logger.info("Taxonomic history: %s -> %s", original_genus, current_genus)
        
        # Step 4: Apply verification-based bracketing
        formatted_authorship, verification = normalize_authorship(
            raw_authorship, 
            original_genus if original_genus != current_genus else None,  # Only pass original_genus if it's actually different
            current_genus
        )
        
        tax_dict["tax_auth"] = formatted_authorship
        tax_dict["verification_status"] = verification  # New field for debugging
        
        logger.info("Final authorship result: %r (Status: %s)", formatted_authorship, verification)
        
        return tax_dict
        
    except requests.RequestException as e:
        logger.warning("Error fetching taxonomy info for %s: %s", species_name, e)
        return tax_dict


def get_multiple_authority_sources(species_name):
    """
    Cross-reference multiple sources for taxonomic authority to improve reliability.
    
    Args:
        species_name (str): The species name in the format 'Genus species'
    
    Returns:
        dict: Combined information from multiple sources
    """
    try:
        genus, specific_epithet = species_name.split(" ")
    except ValueError:
        return {}
    
    sources = {}
    
    # GBIF
    gbif_info = fetch_taxonomy_info(species_name)
    if gbif_info["tax_auth"]:
        sources["GBIF"] = gbif_info["tax_auth"]
    
    # You could add other sources here:
    # - Catalogue of Life API
    # - WoRMS (World Register of Marine Species) for marine species
    # - ITIS (Integrated Taxonomic Information System)
    # - Tropicos (for plants)
    
    # Example placeholder for additional sources:
    # sources["COL"] = fetch_col_authority(species_name)
    # sources["WoRMS"] = fetch_worms_authority(species_name)
    
    return {
        "species_name": species_name,
        "authorities": sources,
        "consensus": gbif_info["tax_auth"],  # You could implement consensus logic here
        "gbif_full_info": gbif_info
    }


def validate_authorship_format(authorship):
    """
    Validate that an authorship string follows standard formats.
    
    Args:
        authorship (str): The authorship string to validate
    
    Returns:
        tuple: (is_valid, issues, suggestions)
    """
    issues = []
    suggestions = []
    
    if not authorship:
        return True, [], []
    
    # Check for common formatting issues
    if authorship.count('(') != authorship.count(')'):
        issues.append("Unmatched parentheses")
        suggestions.append("Check parentheses matching")
    
    # Check for double brackets or mixed bracket types
    if '((' in authorship or '))' in authorship:
        issues.append("Double parentheses found")
    
    if '[' in authorship or ']' in authorship:
        issues.append("Square brackets found (should use parentheses)")
        suggestions.append("Replace square brackets with parentheses")
    
    # Check for year patterns that might indicate formatting issues
    year_pattern = r'\b(17|18|19|20)\d{2}\b'
    years = re.findall(year_pattern, authorship)
    if len(years) > 1:
        issues.append("Multiple years found")
        suggestions.append("Check if year should be included in authorship")
    
    is_valid = len(issues) == 0
    return is_valid, issues, suggestions



def summarise_gbif_distribution_all(usage_key: int) -> str:
    url = "https://api.gbif.org/v1/occurrence/search"
    params = {
        "taxonKey": usage_key,
        "limit": 300,
        "offset": 0,
        "hasCoordinate": "true",
    }

    all_continents = []
    all_countries = []
    total_records = 0

    while True:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        for rec in results:
            cont = rec.get("continent")
            country = rec.get("country")
            if cont: all_continents.append(cont)
            if country: all_countries.append(country)
        total_records += len(results)
        if data.get("endOfRecords"):
            break
        params["offset"] += params["limit"]

    c_continents = Counter(all_continents)
    c_countries = Counter(all_countries)

    lines = [f"A total of {format_with_nbsp(total_records, as_int=True)} GBIF occurrence records with coordinates are available for this species."]

    if c_continents:
        if len(c_continents) == 1:
            only_continent = next(iter(c_continents))
            lines.append(f"All the records are from {only_continent}.")
        else:
            top_conts_items = [f"{k} ({format_with_nbsp(v, as_int=True)})" for k, v in c_continents.most_common()]
            top_conts = oxford_comma_list(top_conts_items)
            lines.append(f"The species has been observed on the following continents: {top_conts}.")

    if c_countries:
        num_countries = len(c_countries)
        if num_countries == 1:
            only_country = next(iter(c_countries))
            lines.append(f"All records are from {only_country}.")
        elif num_countries <= 12:
            top_country_items = [f"{k} ({format_with_nbsp(v, as_int=True)})" for k, v in c_countries.most_common()]
            top_countries = oxford_comma_list(top_country_items)
            lines.append(f"It has been most frequently recorded in {top_countries}.")
        else:
            total = sum(c_countries.values())
            running_total = 0
            top_countries_list = []
            for country, count in c_countries.most_common():
                running_total += count
                top_countries_list.append(country)
                if running_total / total >= 0.8:
                    break
            lines.append(
                f"The species has been recorded in several countries, most frequently in {oxford_comma_list(top_countries_list)}."
            )

    lines.append(f"(Source: [GBIF](https://www.gbif.org/species/{usage_key}))")
    return " ".join(lines)



# Enhanced main function for testing
if __name__ == "__main__":
    test_species = [
        "Neovison vison",  # American mink
        "Homo sapiens",    # Human
        "Mus musculus",    # House mouse
        "Canis lupus"      # Gray wolf
    ]
    
    for species_name in test_species:
        print(f"\n--- Testing: {species_name} ---")
        
        # Get basic info
        tax_info = fetch_taxonomy_info(species_name)
        print(f"Taxonomic authority: '{tax_info['tax_auth']}'")
        print(f"Common name: {tax_info['common_name']}")
        print(f"Original combination: {tax_info['original_combination']}")
        
        # Validate the result
        is_valid, issues, suggestions = validate_authorship_format(tax_info['tax_auth'])
        if not is_valid:
            print(f"⚠️  Formatting issues: {', '.join(issues)}")
            print(f"💡 Suggestions: {', '.join(suggestions)}")
        else:
            print("✅ Authorship format looks good")
        
        # Cross-reference (if implemented)
        # multi_source = get_multiple_authority_sources(species_name)
        # print(f"Multiple sources: {multi_source['authorities']}")
