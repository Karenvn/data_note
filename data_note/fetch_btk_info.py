#!/usr/bin/env python3

# Script to access images, BUSCO scores and software information for a BlobToolKit run

import os
import subprocess
import requests
import json
from .formatting_utils import format_with_nbsp


def build_btk_urls(assembly_accession, prefix=""):
    """
    Generate correct view and download URLs for BlobToolKit.
    Ensures that both 'view' and 'dataset' links are correctly assigned.
    """
    base_view_url = f"https://blobtoolkit.genomehubs.org/view/{assembly_accession}/dataset/{assembly_accession}"
    
    view_urls = {
        f"{prefix}btk_view_summary": f"{base_view_url}/summary",
        f"{prefix}btk_view_blob": f"{base_view_url}/blob",
        f"{prefix}btk_view_snail": f"{base_view_url}/snail"  
        }

    download_urls = {
        f"{prefix}btk_download_summary": f"{base_view_url}/summary",
        f"{prefix}btk_download_blob": f"{base_view_url}/blob",
       f"{prefix}btk_download_snail": f"{base_view_url}/snail"
               }

    return view_urls, download_urls




def fetch_and_parse_summary(assembly_accession, prefix=''):
    """
    Fetch BlobToolKit summary and extract BUSCO metrics:
      - {prefix}BUSCO_lineage   (lineage name)
      - {prefix}BUSCO_n         (total gene count, nbsp separator)
      - {prefix}BUSCO_string    (percentages with semicolons, space before F)
      - {prefix}BUSCO_c, _s, _d, _f, _m  (each as percentage)
    Uses the first lineage returned by the BTK API (most granular).
    """
    url = f"https://blobtoolkit.genomehubs.org/api/v1/summary/{assembly_accession}"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch BTK summary for {assembly_accession}: {e}")
        return {}

    busco_data = data.get("summaryStats", {}).get("busco", {})
    if not busco_data:
        print(f"No BUSCO data for {assembly_accession}")
        return {}

    # Use the first lineage returned by the API — BTK returns the most granular lineage first
    lineage = next(iter(busco_data))

    vals = busco_data[lineage]

    # raw counts
    c_count = vals.get('c', 0)
    s_count = vals.get('s', 0)
    d_count = vals.get('d', 0)
    f_count = vals.get('f', 0)
    m_count = vals.get('m', 0)
    t = vals.get('t', 0)

    # helper: compute percentage to one decimal
    def pct(count):
        return round((count / t * 100) if t else 0, 1)

    # prepare output dict
    busco_dict = {f'{prefix}BUSCO_lineage': lineage}

    # total count with non-breaking space
    if t:
        nbsp_n = format_with_nbsp(t, as_int=True)
        busco_dict[f'{prefix}BUSCO_n'] = nbsp_n
    else:
        nbsp_n = "N/A"
        busco_dict[f'{prefix}BUSCO_n'] = nbsp_n

    # percentage fields
    busco_dict[f'{prefix}BUSCO_c'] = pct(c_count)
    busco_dict[f'{prefix}BUSCO_s'] = pct(s_count)
    busco_dict[f'{prefix}BUSCO_d'] = pct(d_count)
    busco_dict[f'{prefix}BUSCO_f'] = pct(f_count)
    busco_dict[f'{prefix}BUSCO_m'] = pct(m_count)

    # rebuild BUSCO summary string
    busco_dict[f'{prefix}BUSCO_string'] = (
        f"C:{busco_dict[f'{prefix}BUSCO_c']}% "
        f"[S:{busco_dict[f'{prefix}BUSCO_s']}%, D:{busco_dict[f'{prefix}BUSCO_d']}%], "
        f"F:{busco_dict[f'{prefix}BUSCO_f']}%, "
        f"M:{busco_dict[f'{prefix}BUSCO_m']}%, "
        f"n:{nbsp_n}"
    )

    return busco_dict


def fetch_software_versions(assembly_accession):
    # Use the full settings URL to access both software_versions and the pipeline release
    url = f"https://blobtoolkit.genomehubs.org/api/v1/dataset/id/{assembly_accession}/settings"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Get the pipeline version from the settings (release key)
        pipeline_version = data.get("release")

        # Get software versions from the nested software_versions object
        sv = data.get("software_versions", {})

        versions = {
            "blobtk_version": sv.get("blobtk"),
            "blobtoolkit_version": sv.get("blobtoolkit"),
            "busco_version": sv.get("busco"),
            "diamond_version": sv.get("diamond"),
            "minimap2_version": sv.get("minimap2"),
            "samtools_version": sv.get("samtools"),
            "nextflow_version": sv.get("Nextflow"),
            "btk_pipeline_version": pipeline_version
        }
        return versions

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch software versions: {e}")
        return None


# Example usage
if __name__ == "__main__":
    accession = "GCA_964261665.1"
    result_dict = fetch_and_parse_summary(accession)
    print(result_dict)
    versions = fetch_software_versions(accession)
    if versions:
        print("Software Versions:")
        for key, value in versions.items():
            print(f"{key}: {value}")
