import os
import requests
from Bio import Entrez

# updated on 17 Jan 2025 to use NCBI datasets "revision_history".

Entrez.email = os.getenv('ENTREZ_EMAIL', 'default_email')
Entrez.api_key = os.getenv('ENTREZ_API_KEY', 'default_api_key')

def get_latest_revision(accession):
    """
    Fetch the revision history for a given assembly accession and return the latest
    accession and assembly name, preserving the original prefix (GCA vs GCF).
    """
    api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/revision_history?api_key={Entrez.api_key}"

    headers = {"Accept": "application/json"}
    response = requests.get(api_url, headers=headers)
    
    if response.status_code == 200:
        try:
            data = response.json()
            # Check if there are assembly revisions
            if "assembly_revisions" in data and data["assembly_revisions"]:
                # Sort revisions by release_date to get the latest one
                revisions = sorted(data["assembly_revisions"], key=lambda x: x["release_date"], reverse=True)
                prefix = accession.split("_", 1)[0]

                latest_accession = None
                latest_assembly_name = None

                for rev in revisions:
                    if prefix == "GCA":
                        candidate = rev.get("genbank_accession")
                    elif prefix == "GCF":
                        candidate = rev.get("refseq_accession")
                    else:
                        candidate = rev.get("genbank_accession") or rev.get("refseq_accession")

                    if candidate:
                        latest_accession = candidate
                        latest_assembly_name = rev.get("assembly_name", "Unknown assembly name")
                        break

                if not latest_accession:
                    print(f"No matching {prefix} revision found for {accession}.")
                    return accession, None

                if latest_accession != accession:
                    print(f"Update found: {accession} -> {latest_accession} ({latest_assembly_name})")
                else:
                    print(f"No update needed for {accession} ({latest_assembly_name}).")

                return latest_accession, latest_assembly_name
            else:
                print(f"No revisions found for {accession}.")
                return accession, None
        except ValueError:
            print("Error processing JSON response.")
            return accession, None
    else:
        print(f"Failed to fetch revision history, status code: {response.status_code}")
        return accession, None



if __name__ == "__main__":
    current_accession = "GCA_963455315.1"
    
    updated_accession = get_latest_revision(current_accession)
    print('Final assembly accession:', updated_accession)
