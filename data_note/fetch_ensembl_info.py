#!/usr/bin/env python3
"""
Ensembl search with GTF parsing and beta metadata.

Current behaviour as of 2026-04:
- Annotation files are discovered and downloaded from the legacy Ensembl FTP
  layout (`ftp.ensembl.org` / `ftp.ebi.ac.uk`).
- Beta / new-platform GraphQL is used only to look up a human-readable species
  page and matching assembly accession metadata.
- This means the script currently spans both systems, but only the legacy FTP
  side is used for the actual GTF/GFF annotation payload.

Expected future changes:
- Once Ensembl publishes a stable new-platform bulk-download path for
  annotations, replace the legacy FTP directory scraping in this module with
  that supported endpoint.
- Keep the legacy FTP path only as a fallback while it remains available for
  frozen older releases.
- Re-check usage of beta GraphQL before depending on it more heavily <- it is
  still documented by Ensembl as a beta interface.
"""

import os
import re
import json
import gzip
import argparse
import tempfile
from typing import Optional, List, Dict, Union
from collections import defaultdict
import requests

HEADERS = {"Accept": "application/json", "User-Agent": "genome-notes/1.0"}
DEBUG_ENS = bool(int(os.environ.get("GN_DEBUG_ENSEMBL", "0")))

LEGACY_ORG_BASE = "https://ftp.ebi.ac.uk/pub/ensemblorganisms/"
LEGACY_ENS_MAIN_GFF3 = "https://ftp.ensembl.org/pub/current_gff3/"
LEGACY_ENS_MAIN_GTF = "https://ftp.ensembl.org/pub/current_gtf/"
DEFAULT_BETA_GRAPHQL_URL = "https://beta.ensembl.org/data/graphql"

def debug_print(msg: str):
    if DEBUG_ENS:
        print(f"[ENSEMBL] {msg}")


def _configured_url(env_name: str, default: str, *, trailing_slash: bool = True) -> str:
    value = os.environ.get(env_name, default).strip()
    if trailing_slash:
        return value.rstrip("/") + "/"
    return value.rstrip("/")


def _organisms_base() -> str:
    return _configured_url("GN_ENSEMBL_ORGANISMS_BASE", LEGACY_ORG_BASE)


def _main_gff3_base() -> str:
    return _configured_url("GN_ENSEMBL_MAIN_GFF3_BASE", LEGACY_ENS_MAIN_GFF3)


def _main_gtf_base() -> str:
    return _configured_url("GN_ENSEMBL_MAIN_GTF_BASE", LEGACY_ENS_MAIN_GTF)


def _beta_graphql_url() -> str:
    return _configured_url("GN_ENSEMBL_GRAPHQL_URL", DEFAULT_BETA_GRAPHQL_URL, trailing_slash=False)

# Import the formatting function from your helpers module
try:
    from .formatting_utils import format_with_nbsp
except ImportError:
    def format_with_nbsp(value, as_int=True):
        """Fallback formatting function if helpers module not available."""
        if as_int:
            return f"{int(value):,}".replace(",", " ")
        else:
            return str(value)

def _http_text(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch text content from URL."""
    try:
        debug_print(f"Fetching: {url}")
        r = requests.get(url, timeout=timeout, headers=HEADERS)
        if r.status_code == 200:
            return r.text
        else:
            debug_print(f"HTTP {r.status_code} for {url}")
            return None
    except requests.RequestException as e:
        debug_print(f"Request failed for {url}: {e}")
        return None

def _get_species_variants(species: str) -> List[str]:
    """Generate species name variants."""
    parts = species.strip().split()
    if len(parts) >= 2:
        genus, specific = parts[0], parts[1]
        return [
            f"{genus.capitalize()}_{specific.lower()}",
            f"{genus.lower()}_{specific.lower()}",
        ]
    return [species.replace(' ', '_')]

def _find_latest_version_dir(base_url: str) -> Optional[str]:
    """Find the latest version directory (like 2025_04)."""
    html = _http_text(base_url)
    if not html:
        return None
    
    # Look for date-like directories (YYYY_MM pattern)
    dirs = re.findall(r'href="(\d{4}_\d{2})/"', html)
    if dirs:
        latest = sorted(dirs)[-1]  # Take the latest date
        debug_print(f"Found latest version: {latest}")
        return latest
    
    # Fallback to numbered directories
    dirs = re.findall(r'href="(\d+)/"', html)
    if dirs:
        latest = sorted(dirs, key=int)[-1]
        debug_print(f"Found latest numbered version: {latest}")
        return latest
    
    return None

def _find_annotation_file(dir_url: str) -> Optional[str]:
    """Find the best annotation file in a directory."""
    html = _http_text(dir_url)
    if not html:
        return None
    
    # Look for annotation files
    files = re.findall(r'href="([^"]+\.(gtf|gff3?)(\.gz)?)"', html, re.IGNORECASE)
    if not files:
        debug_print(f"No annotation files in {dir_url}")
        return None
    
    debug_print(f"Found files: {[f[0] for f in files]}")
    
    # Prefer genes.gtf, then genes.gff3, then any .gtf, then any .gff3
    for pattern in [r'genes\.gtf', r'genes\.gff3?', r'\.gtf', r'\.gff3?']:
        for file_info in files:
            filename = file_info[0]
            if re.search(pattern, filename, re.IGNORECASE):
                return dir_url + filename
    
    return None


def _extract_assembly_from_url(url: str) -> Optional[str]:
    match = re.search(r"(GC[AF]_\d+\.\d+)", url)
    return match.group(1) if match else None


def _select_matching_genome(genomes: List[dict], target_accession: Optional[str]) -> Optional[dict]:
    if not genomes:
        return None
    if not target_accession:
        return genomes[0]

    target_accession = target_accession.strip()
    for genome in genomes:
        if genome.get("assembly_accession") == target_accession:
            return genome

    target_base = target_accession.split(".")[0]
    for genome in genomes:
        accession = genome.get("assembly_accession")
        if accession and accession.split(".")[0] == target_base:
            return genome

    return genomes[0]

def process_gtf(annot_file):
    """Process GTF file and extract annotation statistics."""
    gtf_dict = {}
    transcript_count = 0
    gene_count = 0
    exon_count = 0
    gene_lengths = []
    transcript_lengths = []
    exon_lengths = []
    intron_lengths = []
    cds_lengths = []
    
    protein_coding_genes = 0
    pseudogene_genes = 0
    non_coding_genes = 0

    # Treat certain immunoglobulin or T-cell receptor biotypes as coding:
    coding_like_biotypes = {
        "protein_coding", 
        "IG_V_gene", "IG_C_gene", "IG_D_gene", "IG_J_gene",
        "TR_V_gene", "TR_D_gene", "TR_J_gene", "TR_C_gene"
    }

    debug_print(f"Processing GTF file: {annot_file}")

    if annot_file.endswith('.gz'):
        f = gzip.open(annot_file, 'rt')
    else:
        f = open(annot_file, 'r')

    current_transcript = None
    transcript_exons = defaultdict(list)

    for line in f:
        if line.startswith("#"):
            continue

        columns = line.strip().split('\t')
        if len(columns) < 9:
            continue

        feature_type = columns[2]
        start = int(columns[3])
        end = int(columns[4])
        length = end - start + 1

        if feature_type == "gene":
            gene_count += 1
            gene_lengths.append(length)
            
            # Extract gene_biotype from the attributes
            match = re.search(r'gene_biotype\s+"([^"]+)"', line)
            if match:
                biotype = match.group(1)
                
                if biotype in coding_like_biotypes:
                    protein_coding_genes += 1
                elif "pseudogene" in biotype:
                    pseudogene_genes += 1
                else:
                    non_coding_genes += 1

        elif feature_type == "transcript":
            transcript_count += 1
            current_transcript = re.search(r'transcript_id\s+"([^"]+)"', line).group(1)
            transcript_lengths.append(length)

        elif feature_type == "exon":
            exon_count += 1
            exon_lengths.append(length)
            if current_transcript:
                transcript_exons[current_transcript].append((start, end))

        elif feature_type == "CDS":
            cds_lengths.append(length)

    f.close()

    # Calculate intron lengths for each transcript
    for exons in transcript_exons.values():
        exons.sort()
        for i in range(1, len(exons)):
            intron_length = exons[i][0] - exons[i-1][1] - 1
            if intron_length > 0:
                intron_lengths.append(intron_length)

    # Calculate statistics
    formatted_genes = format_with_nbsp(gene_count, as_int=True)
    formatted_transcripts = format_with_nbsp(transcript_count, as_int=True)
    av_transc = round(transcript_count / gene_count, 2) if gene_count > 0 else 0
    av_exon = round(exon_count / transcript_count, 2) if transcript_count > 0 else 0
    av_gene_length = round(sum(gene_lengths) / len(gene_lengths), 2) if gene_lengths else 0
    av_transcript_length = round(sum(transcript_lengths) / len(transcript_lengths), 2) if transcript_lengths else 0
    av_exon_length = round(sum(exon_lengths) / len(exon_lengths), 2) if exon_lengths else 0
    av_intron_length = round(sum(intron_lengths) / len(intron_lengths), 2) if intron_lengths else 0
    av_cds_length = round(sum(cds_lengths) / len(cds_lengths), 2) if cds_lengths else 0

    # Format the gene type counts
    prot_str = format_with_nbsp(protein_coding_genes, as_int=True)
    pseudo_str = format_with_nbsp(pseudogene_genes, as_int=True)
    noncoding_str = format_with_nbsp(non_coding_genes, as_int=True)

    # Build results dictionary
    gtf_dict['genes'] = formatted_genes
    gtf_dict['transcripts'] = formatted_transcripts
    gtf_dict['av_transc'] = format_with_nbsp(av_transc, as_int=False)
    gtf_dict['av_exon'] = format_with_nbsp(av_exon, as_int=False)
    gtf_dict['prot_genes'] = prot_str
    gtf_dict['pseudogenes'] = pseudo_str
    gtf_dict['non_coding'] = noncoding_str
    gtf_dict['av_gene_length'] = format_with_nbsp(av_gene_length, as_int=False)
    gtf_dict['av_transcript_length'] = format_with_nbsp(av_transcript_length, as_int=False)
    gtf_dict['av_exon_length'] = format_with_nbsp(av_exon_length, as_int=False)
    gtf_dict['av_intron_length'] = format_with_nbsp(av_intron_length, as_int=False)
    gtf_dict['av_cds_length'] = format_with_nbsp(av_cds_length, as_int=False)

    debug_print(f"Processed {gene_count} genes, {transcript_count} transcripts")
    return gtf_dict

def fetch_beta_metadata(taxon_id, target_accession=None):
    """Query the beta site GraphQL API to retrieve metadata."""
    url = _beta_graphql_url()
    query = """
    query Annotation($taxon: String) {
        genomes(by_keyword: {species_taxonomy_id: $taxon }) {
            assembly_accession
            genome_id
        }
    }
    """
    variables = {"taxon": str(taxon_id)}

    def _query_by_accession(accession: str) -> dict:
        """Best-effort lookup by assembly accession (beta sometimes indexes by accession)."""
        if not accession:
            return {}
        for key in ("assembly_accession", "assembly"):
            q = f"""
            query Annotation($acc: String) {{
                genomes(by_keyword: {{{key}: $acc }}) {{
                    assembly_accession
                    genome_id
                }}
            }}
            """
            try:
                r = requests.post(url=url, json={"query": q, "variables": {"acc": accession}}, timeout=30)
                if r.status_code != 200:
                    continue
                data = r.json()
                if "errors" in data:
                    continue
                genomes = data.get("data", {}).get("genomes", [])
                if genomes:
                    g = genomes[0]
                    if g.get("assembly_accession") and g.get("genome_id"):
                        annot_url = f"https://beta.ensembl.org/species/{g['genome_id']}"
                        return {"annot_accession": g["assembly_accession"], "annot_url": annot_url}
            except Exception:
                continue
        return {}

    try:
        response = requests.post(url=url, json={"query": query, "variables": variables}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            genomes = data.get("data", {}).get("genomes", [])
            if genomes:
                selected = _select_matching_genome(genomes, target_accession)
                if selected and selected.get("assembly_accession") and selected.get("genome_id"):
                    accession = selected["assembly_accession"]
                    species_id = selected["genome_id"]
                    annot_url = f"https://beta.ensembl.org/species/{species_id}"
                    return {"annot_accession": accession, "annot_url": annot_url}

        # If taxon-based lookup failed, try accession-based lookup (best effort)
        if target_accession:
            alt = _query_by_accession(target_accession)
            if alt:
                return alt

        debug_print(f"GraphQL query failed or returned no results for taxon {taxon_id}")
        return {}

    except Exception as e:
        debug_print(f"Error querying beta metadata: {e}")
        if target_accession:
            return _query_by_accession(target_accession)
        return {}


def search_ensembl_organisms(assembly: str, species: str) -> Optional[tuple]:
    """Direct search for BRAKER/Ensembl in organisms. Returns (url, method) tuple."""
    # TODO(ensembl-transition): this still scrapes the legacy FTP-style directory
    # layout for the real annotation files. When Ensembl provides a stable
    # supported download endpoint on the new platform, switch this lookup over.
    variants = _get_species_variants(species)
    org_base = _organisms_base()
    
    for variant in variants:
        base_url = f"{org_base}{variant}/{assembly}/"
        
        # Test both methods directly
        for method, method_name in [("braker", "BRAKER"), ("ensembl", "Ensembl Genebuild")]:
            test_url = f"{base_url}{method}/geneset/"
            debug_print(f"Testing {method_name}: {test_url}")
            
            response = requests.get(test_url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                debug_print(f"Found {method_name} geneset directory")
                
                # Look for version directories like 2024_05
                dirs = re.findall(r'href="(\d{4}_\d{2})/"', response.text)
                if dirs:
                    latest = sorted(dirs)[-1]
                    final_url = f"{test_url}{latest}/"
                    debug_print(f"Trying version {latest}: {final_url}")
                    
                    gtf_url = _find_annotation_file(final_url)
                    if gtf_url:
                        return (gtf_url, method_name)
    
    return None

def search_ensembl_main(species: str) -> Optional[tuple]:
    """Search main Ensembl site (only if organisms search failed). Returns (url, method) tuple."""
    debug_print(f"Searching main Ensembl for {species}")
    
    variants = _get_species_variants(species)
    
    for base_url in [_main_gtf_base(), _main_gff3_base()]:
        for variant in variants:
            species_url = f"{base_url}{variant}/"
            html = _http_text(species_url)
            if html:
                latest_version = _find_latest_version_dir(species_url)
                if latest_version:
                    final_path = species_url + latest_version + "/"
                    annotation_url = _find_annotation_file(final_path)
                    if annotation_url:
                        return (annotation_url, "Ensembl Genebuild")  # Main site is always Ensembl
    
    return None

def create_ensembl_dict(assembly: str, species: str, tax_id: Union[str, int]) -> Dict[str, str]:
    """
    Complete Ensembl annotation search with GTF parsing and beta metadata.

    The returned annotation statistics still come from the legacy FTP-hosted
    annotation files. Beta GraphQL is currently supplemental metadata only.
    """
    assembly = assembly.strip().rstrip("/")
    species = species.strip()
    
    debug_print(f"Starting search for {species} ({assembly})")
    
    # Strategy 1: Try Ensembl Organisms first (most genomes are here)
    organisms_result = search_ensembl_organisms(assembly, species)
    if organisms_result:
        annotation_file_url, method = organisms_result
        source = "ensembl_organisms"
    else:
        # Strategy 2: Try main Ensembl only if organisms failed
        main_result = search_ensembl_main(species)
        if main_result:
            annotation_file_url, method = main_result
            source = "ensembl_main"
        else:
            debug_print(f"No annotation found for {species} ({assembly})")
            return {}
    
    debug_print(f"SUCCESS: Found annotation at {annotation_file_url} using {method}")

    resolved_assembly = _extract_assembly_from_url(annotation_file_url) or assembly

    # Try to get beta site metadata if we have a tax_id
    beta_metadata = {}
    if tax_id:
        debug_print(f"Fetching beta metadata for tax_id: {tax_id}")
        beta_metadata = fetch_beta_metadata(tax_id, resolved_assembly)
        if beta_metadata:
            debug_print(f"Got beta metadata: {beta_metadata['annot_url']}")

    # Prefer a human-readable beta Ensembl species page for readers.
    reader_annotation_url = beta_metadata.get("annot_url", annotation_file_url)
    
    # Download and process the GTF file
    try:
        debug_print("Downloading and processing GTF file...")
        with tempfile.TemporaryDirectory() as tempdirname:
            gtf_path = os.path.join(tempdirname, "annotation.gtf.gz")
            
            response = requests.get(annotation_file_url, timeout=120)  # Longer timeout for large files
            if response.status_code == 200:
                with open(gtf_path, "wb") as f:
                    f.write(response.content)
                
                # Process the GTF file to extract statistics
                gtf_stats = process_gtf(gtf_path)
                
                # Build the complete result dictionary
                result = gtf_stats.copy()  # Start with GTF statistics
                
                # Add metadata
                result.update({
                    "ensembl_annotation_url": reader_annotation_url,
                    "ensembl_annotation_file_url": annotation_file_url,
                    "ensembl_source": source,
                    "ensembl_species": species,
                    "ensembl_search_strategy": "Ensembl Organisms" if source == "ensembl_organisms" else "Ensembl Main Site",
                    "annot_method": method  # Add the annotation method
                })
                
                # Add beta metadata if available (this provides the annot_url for templates)
                if beta_metadata:
                    result["annot_url"] = beta_metadata["annot_url"]
                    result["annot_accession"] = beta_metadata["annot_accession"]
                    result["source"] = "beta"  # Mark as beta source for template compatibility

                # Fallback so templates can render even without beta metadata
                if "annot_url" not in result:
                    result["annot_url"] = reader_annotation_url
                    result["annot_accession"] = resolved_assembly
                    result["source"] = "ensembl_ftp"
                
                debug_print("GTF processing completed successfully")
                return result
            else:
                debug_print(f"Failed to download GTF file: HTTP {response.status_code}")
                # Return basic info even if download failed
                result = {
                    "ensembl_annotation_url": reader_annotation_url,
                    "ensembl_annotation_file_url": annotation_file_url,
                    "ensembl_source": source,
                    "ensembl_species": species,
                    "ensembl_search_strategy": "Ensembl Organisms" if source == "ensembl_organisms" else "Ensembl Main Site",
                    "annot_method": method,
                    "download_error": f"HTTP {response.status_code}"
                }
                
                if beta_metadata:
                    result["annot_url"] = beta_metadata["annot_url"]
                    result["annot_accession"] = beta_metadata["annot_accession"]
                    result["source"] = "beta"

                # Fallback so templates can render even without beta metadata
                if "annot_url" not in result:
                    result["annot_url"] = reader_annotation_url
                    result["annot_accession"] = resolved_assembly
                    result["source"] = "ensembl_ftp"
                
                return result
    
    except Exception as e:
        debug_print(f"Error processing GTF file: {e}")
        # Return basic info even if processing failed
        result = {
            "ensembl_annotation_url": reader_annotation_url,
            "ensembl_annotation_file_url": annotation_file_url,
            "ensembl_source": source,
            "ensembl_species": species,
            "ensembl_search_strategy": "Ensembl Organisms" if source == "ensembl_organisms" else "Ensembl Main Site",
            "annot_method": method,
            "processing_error": str(e)
        }
        
        if beta_metadata:
            result["annot_url"] = beta_metadata["annot_url"]
            result["annot_accession"] = beta_metadata["annot_accession"]
            result["source"] = "beta"

        # Fallback so templates can render even without beta metadata
        if "annot_url" not in result:
            result["annot_url"] = reader_annotation_url
            result["annot_accession"] = resolved_assembly
            result["source"] = "ensembl_ftp"
        
        return result

def _cli() -> int:
    """CLI for testing."""
    p = argparse.ArgumentParser(description="Complete Ensembl annotation finder with GTF parsing.")
    p.add_argument("--assembly", required=True, help="Assembly accession")
    p.add_argument("--species", required=True, help="Species name")
    p.add_argument("--tax-id", default="", help="NCBI TaxID (optional)")
    p.add_argument("--debug", action="store_true", help="Enable debug output")
    args = p.parse_args()
    
    if args.debug:
        os.environ["GN_DEBUG_ENSEMBL"] = "1"
        global DEBUG_ENS
        DEBUG_ENS = True
    
    result = create_ensembl_dict(args.assembly, args.species, args.tax_id)
    
    if result:
        print(json.dumps(result, indent=2))
        return 0
    else:
        print('{"error": "No annotation found"}')
        return 1

if __name__ == "__main__":
    raise SystemExit(_cli())
