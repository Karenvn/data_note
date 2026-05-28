"""
Automated workflow for extracting COI from an unannotated mitogenome and
querying BOLD for BIN assignments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass, asdict
from io import BytesIO, TextIOWrapper
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests
from Bio import Entrez, SeqIO
from Bio.Blast import NCBIWWW, NCBIXML
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

NCBI_TIMEOUT = 60
BOLD_TIMEOUT = 120
NCBI_DATASETS_URL = (
    "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/sequence_reports"
)
NCBI_ORGANELLE_DOWNLOAD = "https://api.ncbi.nlm.nih.gov/datasets/v2/organelle/download"
BOLD_IDS_ENDPOINT = "http://v4.boldsystems.org/index.php/Ids_xml"
BOLD_V5_SUBMISSION_ENDPOINT = "https://id.boldsystems.org/submission"
BOLD_V5_STATUS_ENDPOINT = "https://id.boldsystems.org/submission/status/{sub_id}"
BOLD_V5_RESULTS_ENDPOINT = "https://id.boldsystems.org/submission/results/{sub_id}"
PORTAL_QUERY_ENDPOINT = "https://portal.boldsystems.org/api/query"
PORTAL_DOCS_ENDPOINT = "https://portal.boldsystems.org/api/documents/{query_id}"
LCO1490 = "GGTCAACAAATCATAAAGATATTGG"
HCO2198 = "TAAACTTCAGGGTGACCAAAAAATCA"
PRIMER_MAX_MISMATCHES = 4

_ENTREZ_READY = False


def _ensure_entrez() -> None:
    """Make sure Entrez has an email/api key before hitting NCBI."""
    global _ENTREZ_READY
    if _ENTREZ_READY:
        return

    email = os.getenv("ENTREZ_EMAIL")
    if not email:
        raise RuntimeError(
            "ENTREZ_EMAIL is not set. Provide a valid email before querying NCBI."
        )

    Entrez.email = email
    api_key = os.getenv("ENTREZ_API_KEY")
    if api_key:
        Entrez.api_key = api_key

    _ENTREZ_READY = True


def _ncbi_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if getattr(Entrez, "api_key", None) and Entrez.api_key != "default_api_key":
        headers["api-key"] = Entrez.api_key
    return headers


def _infer_species_from_description(description: str) -> Optional[str]:
    """
    Try to extract a binomial from an NCBI record description.
    Assumes accession is first token; the next two tokens are Genus species.
    """
    if not description:
        return None
    parts = description.split()
    if len(parts) >= 3:
        candidate = " ".join(parts[1:3])
        # Basic sanity: capitalize genus, lower species
        return candidate.strip()
    return None


def _normalise_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return re.sub(r"\s+", " ", name).strip().lower()


def _hamming_distance(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def _find_approximate_primer(
    sequence: str,
    primer: str,
    *,
    max_mismatches: int = PRIMER_MAX_MISMATCHES,
) -> Optional[Dict[str, object]]:
    best: Optional[Dict[str, object]] = None
    primer_length = len(primer)
    for start in range(0, len(sequence) - primer_length + 1):
        candidate = sequence[start : start + primer_length]
        mismatches = _hamming_distance(candidate, primer)
        if mismatches > max_mismatches:
            continue
        if best is None or mismatches < int(best["mismatches"]):
            best = {
                "start": start,
                "end": start + primer_length,
                "mismatches": mismatches,
                "sequence": candidate,
            }
    return best


@dataclass
class WorkflowResult:
    gca_accession: str
    success: bool = False
    error: Optional[str] = None
    mt_accession: Optional[str] = None
    mt_length: Optional[int] = None
    mt_record_id: Optional[str] = None
    mt_species: Optional[str] = None
    coi_sequence: Optional[str] = None
    coi_length: Optional[int] = None
    coi_start: Optional[int] = None
    coi_end: Optional[int] = None
    coi_identity: Optional[float] = None
    coi_strand: Optional[str] = None
    coi_match_title: Optional[str] = None
    bin_number: Optional[str] = None
    bold_match: Optional[str] = None
    bold_similarity: Optional[float] = None
    bold_raw: Optional[str] = None
    bold_process_id: Optional[str] = None
    bold_self_hit: Optional[bool] = None
    bold_alt_match: Optional[str] = None
    bold_alt_similarity: Optional[float] = None
    bold_alt_process_id: Optional[str] = None
    bin_avg_distance: Optional[str] = None
    bin_nn_distance: Optional[str] = None
    bin_nearest_bin: Optional[str] = None
    bin_nearest_member: Optional[str] = None
    bin_nearest_taxonomy: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return asdict(self)


def get_mitochondrial_accession(gca_accession: str) -> Optional[str]:
    """Use NCBI Datasets sequence_reports to find the mitochondrial record."""
    _ensure_entrez()
    url = NCBI_DATASETS_URL.format(accession=gca_accession)
    resp = requests.get(url, headers=_ncbi_headers(), timeout=NCBI_TIMEOUT)
    resp.raise_for_status()

    reports = resp.json().get("reports", [])
    for report in reports:
        role = (report.get("role") or "").lower()
        chr_name = (report.get("chr_name") or "").upper()
        molecule = (report.get("assigned_molecule") or "").upper()
        is_mt = (
            role == "mitochondrion"
            or "MT" in chr_name
            or "MITO" in chr_name
            or "MITO" in molecule
        )
        if not is_mt:
            continue

        accession = report.get("refseq_accession") or report.get("genbank_accession")
        if accession:
            return accession

    return None


def fetch_mitochondrial_sequence(accession: str) -> Optional[SeqRecord]:
    """Download mitochondrial FASTA/GenBank via the organelle endpoint."""
    _ensure_entrez()
    payload = {
        "accessions": [accession],
        "include_annotation_type": ["GENOME_FASTA"],
    }
    params = {"filename": accession}
    resp = requests.post(
        NCBI_ORGANELLE_DOWNLOAD,
        json=payload,
        params=params,
        headers={
            "accept": "application/zip",
            "content-type": "application/json",
            **_ncbi_headers(),
        },
        timeout=NCBI_TIMEOUT,
    )
    resp.raise_for_status()

    with zipfile.ZipFile(BytesIO(resp.content)) as zip_ref:
        fasta_files = [
            name
            for name in zip_ref.namelist()
            if name.lower().endswith((".fa", ".fna", ".fasta"))
        ]
        if fasta_files:
            with zip_ref.open(fasta_files[0]) as handle:
                with TextIOWrapper(handle, encoding="utf-8") as text_handle:
                    return SeqIO.read(text_handle, "fasta")

        gb_files = [
            name
            for name in zip_ref.namelist()
            if name.lower().endswith((".gb", ".gbff"))
        ]
        if gb_files:
            with zip_ref.open(gb_files[0]) as text_handle:
                return SeqIO.read(text_handle, "genbank")

    return None


def locate_coi_region_by_primers(sequence: str, seq_id: str) -> Optional[Dict[str, object]]:
    """Locate the standard COI barcode region using approximate LCO/HCO primer matches."""
    clean_seq = sequence.upper().replace(" ", "").replace("\n", "")
    hco_reverse_complement = str(Seq(HCO2198).reverse_complement())

    for strand, oriented_sequence in (
        ("+", clean_seq),
        ("-", str(Seq(clean_seq).reverse_complement())),
    ):
        forward = _find_approximate_primer(oriented_sequence, LCO1490)
        reverse = _find_approximate_primer(oriented_sequence, hco_reverse_complement)
        if not forward or not reverse:
            continue
        if int(forward["start"]) >= int(reverse["end"]):
            continue

        subseq = oriented_sequence[int(forward["start"]) : int(reverse["end"])]
        if not 500 <= len(subseq) <= 850:
            continue

        if strand == "+":
            start = int(forward["start"])
            end = int(reverse["end"])
        else:
            start = len(clean_seq) - int(reverse["end"])
            end = len(clean_seq) - int(forward["start"])

        return {
            "sequence": subseq,
            "start": start,
            "end": end,
            "strand": strand,
            "identity": 1.0,
            "match_title": f"{seq_id} COI barcode region located by LCO1490/HCO2198 primer matches",
        }

    return None


def blast_for_coi_region(sequence: str, seq_id: str) -> Optional[Dict[str, object]]:
    """Identify COI by blasting the mitogenome (blastx vs nr)."""
    primer_hit = locate_coi_region_by_primers(sequence, seq_id)
    if primer_hit:
        return primer_hit

    _ensure_entrez()
    blast_handle = NCBIWWW.qblast(
        program="blastx",
        database="nr",
        sequence=sequence,
        hitlist_size=25,
        expect=0.001,
        format_type="XML",
    )
    record = NCBIXML.read(blast_handle)
    coi_hits: List[Dict[str, object]] = []
    for alignment in record.alignments:
        title = alignment.title.lower()
        if not any(
            token in title
            for token in [
                "cytochrome c oxidase subunit 1",
                "cytochrome c oxidase subunit i",
                "cytochrome oxidase subunit 1",
                "cytochrome oxidase subunit i",
                "cox1",
                "coxi",
                "coi",
            ]
        ):
            continue
        best_hsp = max(alignment.hsps, key=lambda hsp: hsp.identities)
        start = best_hsp.query_start
        end = best_hsp.query_end
        coi_hits.append(
            {
                "title": alignment.title,
                "start": min(start, end) - 1,
                "end": max(start, end),
                "identity": best_hsp.identities / best_hsp.align_length,
                "frame": best_hsp.frame[0] if hasattr(best_hsp, "frame") else 1,
            }
        )

    if not coi_hits:
        return None

    best = max(coi_hits, key=lambda hit: (hit["end"] - hit["start"], hit["identity"]))
    subseq = sequence[best["start"] : best["end"]]
    strand = "+" if best["frame"] > 0 else "-"
    if strand == "-":
        subseq = str(Seq(subseq).reverse_complement())

    return {
        "sequence": subseq,
        "start": best["start"],
        "end": best["end"],
        "strand": strand,
        "identity": best["identity"],
        "match_title": best["title"],
    }


def query_bold_v5_for_coi(sequence: str) -> Dict[str, Optional[str]]:
    """Submit the COI region to the current BOLD v5 Identification Engine."""
    fasta = f">query\n{sequence}\n"
    params = {
        "db": "public.tax-derep",
        "mi": "0.94",
        "mo": "100",
        "maxh": "25",
        "order": "3",
    }
    session = requests.Session()
    session.get("https://id.boldsystems.org/", timeout=BOLD_TIMEOUT)
    submit_resp = session.post(
        BOLD_V5_SUBMISSION_ENDPOINT,
        params=params,
        files={"fasta_file": ("submitted.fas", fasta, "text/plain")},
        timeout=BOLD_TIMEOUT,
    )
    submit_resp.raise_for_status()
    sub_id = submit_resp.json().get("sub_id")
    if not sub_id:
        raise RuntimeError("BOLD v5 submission did not return a submission id.")

    deadline = time.time() + max(BOLD_TIMEOUT, 180)
    while True:
        status_resp = session.get(
            BOLD_V5_STATUS_ENDPOINT.format(sub_id=sub_id),
            timeout=BOLD_TIMEOUT,
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("status")
        if status == "complete":
            break
        if time.time() > deadline:
            raise TimeoutError(f"BOLD v5 submission did not complete: {sub_id}")
        time.sleep(5)

    results_resp = session.get(
        BOLD_V5_RESULTS_ENDPOINT.format(sub_id=sub_id),
        timeout=BOLD_TIMEOUT,
    )
    results_resp.raise_for_status()
    text = results_resp.text

    matches: List[Dict[str, Optional[str]]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        result = json.loads(line)
        for result_id, hit in (result.get("results") or {}).items():
            fields = result_id.split("|")
            process_id = fields[0] if len(fields) > 0 else None
            bin_uri = fields[2] if len(fields) > 2 and fields[2] else None
            taxonomy = hit.get("taxonomy") or {}
            species = taxonomy.get("species") or None
            genus = taxonomy.get("genus") or None
            match_name = species or genus
            pdist = hit.get("pdist")
            similarity = None
            if pdist is not None:
                similarity = max(0.0, 100.0 - float(pdist))
            elif hit.get("pident") is not None:
                similarity = float(hit["pident"])

            matches.append(
                {
                    "process_id": process_id,
                    "bin": bin_uri,
                    "similarity": similarity,
                    "match_name": match_name,
                }
            )

    top = next((match for match in matches if match.get("match_name")), matches[0] if matches else {})
    return {
        "status": "success",
        "bin_number": top.get("bin"),
        "top_match": top.get("match_name"),
        "similarity": top.get("similarity"),
        "process_id": top.get("process_id"),
        "matches": matches,
        "raw_response": text,
    }


def query_bold_for_coi(sequence: str) -> Dict[str, Optional[str]]:
    """Submit the COI region to the BOLD identification API."""
    clean_seq = sequence.upper().replace(" ", "").replace("\n", "")
    if len(clean_seq) < 400:
        raise ValueError("COI sequence is unexpectedly short; refusing to query BOLD.")

    try:
        return query_bold_v5_for_coi(clean_seq)
    except Exception:
        pass

    resp = requests.get(
        BOLD_IDS_ENDPOINT,
        params={"db": "COX1_SPECIES_PUBLIC", "sequence": clean_seq},
        timeout=BOLD_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.text

    bin_number: Optional[str] = None
    similarity: Optional[float] = None
    match_name: Optional[str] = None
    process_id: Optional[str] = None
    matches: List[Dict[str, Optional[str]]] = []

    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(text)
        for match in root.findall(".//match"):
            pid = match.findtext("ID")
            bin_uri = match.findtext("bin_uri") or match.findtext("bin")
            sim_text = match.findtext("similarity")
            sim_val: Optional[float] = None
            if sim_text:
                sim_val = float(sim_text)
                if sim_val <= 1.0:
                    sim_val *= 100.0
            name = (
                match.findtext("species")
                or match.findtext("identification")
                or match.findtext("taxon")
                or match.findtext("taxonomicidentification")
            )
            matches.append(
                {
                    "process_id": pid,
                    "bin": bin_uri,
                    "similarity": sim_val,
                    "match_name": name,
                }
            )
        if matches:
            top = matches[0]
            process_id = top.get("process_id")
            bin_number = top.get("bin")
            similarity = top.get("similarity")
            match_name = top.get("match_name")
    except Exception:
        pass

    if not bin_number:
        bin_match = re.search(r"BOLD:[A-Z]{3}\d{4,5}", text)
        if bin_match:
            bin_number = bin_match.group(0)

    if similarity is None:
        sim_match = re.search(r"similarity[^0-9]*([0-9.]+)", text, re.IGNORECASE)
        if sim_match:
            similarity_val = float(sim_match.group(1))
            similarity = (
                similarity_val * 100.0 if similarity_val <= 1.0 else similarity_val
            )

    if not process_id:
        pid_match = re.search(r"<ID>([^<]+)</ID>", text)
        if pid_match:
            process_id = pid_match.group(1)

    if not match_name:
        species_match = re.search(
            r"<species[^>]*>([^<]+)</species>", text, flags=re.IGNORECASE
        )
        if species_match:
            match_name = species_match.group(1)
    if not match_name:
        taxon_match = re.search(
            r"<taxonomicidentification[^>]*>([^<]+)</taxonomicidentification>",
            text,
            flags=re.IGNORECASE,
        )
        if taxon_match:
            match_name = taxon_match.group(1)

    return {
        "status": "success",
        "bin_number": bin_number,
        "top_match": match_name,
        "similarity": similarity,
        "process_id": process_id,
        "matches": matches,
        "raw_response": text,
    }


def fetch_bin_metrics(bin_uri: str) -> Dict[str, Optional[str]]:
    """
    Retrieve BIN-level distance and nearest-neighbour info by scraping
    the public barcode cluster page.

    Returns a dict with average p-distance, distance to nearest neighbour,
    and the nearest neighbour BIN/member/taxonomy if available.
    """
    url = "https://v4.boldsystems.org/index.php/Public_BarcodeCluster"
    resp = requests.get(url, params={"clusteruri": bin_uri}, timeout=BOLD_TIMEOUT)
    resp.raise_for_status()
    html = resp.text

    avg_match = re.search(
        r"Average Distance:</th>\s*<td[^>]*>([^<]+)</td>", html, re.IGNORECASE
    )
    nn_match = re.search(
        r"Distance to Nearest Neighbor:</th>\s*<td[^>]*>([^<]+)</td>",
        html,
        re.IGNORECASE,
    )

    nn_details: Dict[str, Optional[str]] = {
        "nearest_bin": None,
        "nearest_member": None,
        "nearest_taxonomy": None,
    }
    nn_table = re.search(
        r"NEAREST NEIGHBOR \(NN\) DETAILS</h3>(.*?)</table>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if nn_table:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", nn_table.group(1), flags=re.DOTALL)
        for row in rows:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.DOTALL)
            cleaned = [" ".join(re.sub("<.*?>", " ", c).split()) for c in cells]
            if not cleaned:
                continue
            label = cleaned[0].lower()
            if "nearest bin uri" in label and len(cleaned) > 1:
                nn_details["nearest_bin"] = cleaned[1]
            elif "nearest member:" in label and len(cleaned) > 1:
                nn_details["nearest_member"] = cleaned[1]
            elif "nearest member taxonomy" in label and len(cleaned) > 1:
                nn_details["nearest_taxonomy"] = cleaned[1]

    return {
        "bin_uri": bin_uri,
        "avg_distance": avg_match.group(1).strip() if avg_match else None,
        "nn_distance": nn_match.group(1).strip() if nn_match else None,
        **nn_details,
    }


def lookup_bin_from_processid(process_id: str) -> Optional[str]:
    """
    Use the BOLD portal API to resolve a processid to its BIN URI.

    This calls the /api/query endpoint with ids:processid:<ID>,
    then fetches documents for the returned query_id and reads the bin_uri.
    """
    try:
        q_resp = requests.get(
            PORTAL_QUERY_ENDPOINT,
            params={"query": f"ids:processid:{process_id}", "extent": "limited"},
            timeout=BOLD_TIMEOUT,
        )
        q_resp.raise_for_status()
        query_id = q_resp.json().get("query_id")
        if not query_id:
            return None

        docs_resp = requests.get(
            PORTAL_DOCS_ENDPOINT.format(query_id=query_id),
            timeout=BOLD_TIMEOUT,
        )
        docs_resp.raise_for_status()
        docs = docs_resp.json().get("data") or []
        for doc in docs:
            bin_uri = doc.get("bin_uri")
            if bin_uri:
                return bin_uri
    except Exception:
        return None

    return None


def _select_match_and_self_flag(
    matches: List[Dict[str, Optional[str]]],
    expected_species: Optional[str] = None,
) -> Dict[str, object]:
    """
    Choose which BOLD match to report and whether the top hit looks like a self-hit.

    We treat a hit as self if the top match has very high similarity (>=99.5)
    and there is at least one additional match; in that case we pick the next match
    to report and mark bold_self_hit=True. Otherwise we keep the top hit.
    """
    if not matches:
        return {"chosen": {}, "self_hit": False, "skipped": None}

    expected = _normalise_name(expected_species)
    species_matches = [match for match in matches if match.get("match_name")]
    if expected:
        expected_matches = [
            match
            for match in species_matches
            if _normalise_name(str(match.get("match_name") or "")) == expected
        ]
        if expected_matches:
            chosen = max(expected_matches, key=lambda match: match.get("similarity") or 0.0)
            return {"chosen": chosen, "self_hit": False, "skipped": None}

    top = species_matches[0] if species_matches else matches[0]
    top_sim = top.get("similarity") or 0.0
    if top_sim >= 99.5 and len(matches) > 1:
        alternatives = [match for match in species_matches if match is not top]
        chosen = alternatives[0] if alternatives else matches[1]
        return {"chosen": chosen, "self_hit": True, "skipped": top}

    return {"chosen": top, "self_hit": False, "skipped": None}


def process_gca_accession(gca_accession: str) -> WorkflowResult:
    """Complete workflow for a single GCA accession."""
    result = WorkflowResult(gca_accession=gca_accession)
    try:
        mt_accession = get_mitochondrial_accession(gca_accession)
        if not mt_accession:
            result.error = "No mitochondrial sequence found in assembly metadata."
            return result

        result.mt_accession = mt_accession
        seq_record = fetch_mitochondrial_sequence(mt_accession)
        if not seq_record:
            result.error = "Unable to download mitochondrial sequence."
            return result

        result.mt_length = len(seq_record.seq)
        result.mt_record_id = seq_record.id
        result.mt_species = _infer_species_from_description(seq_record.description)

        coi_info = blast_for_coi_region(str(seq_record.seq), mt_accession)
        if not coi_info:
            result.error = "BLAST failed to identify a COI/COX1 region."
            return result

        result.coi_sequence = coi_info["sequence"]
        result.coi_length = len(result.coi_sequence)
        result.coi_start = int(coi_info["start"])
        result.coi_end = int(coi_info["end"])
        result.coi_strand = str(coi_info["strand"])
        result.coi_identity = float(coi_info["identity"])
        result.coi_match_title = str(coi_info["match_title"])

        bold_result = query_bold_for_coi(result.coi_sequence)
        matches = bold_result.get("matches") or []
        # Decide which match to report (skip likely self-hit if present)
        selection = _select_match_and_self_flag(matches, result.mt_species)
        chosen = selection.get("chosen") or {}

        result.bin_number = chosen.get("bin") or bold_result.get("bin_number")
        result.bold_match = chosen.get("match_name") or bold_result.get("top_match")
        sim_val = chosen.get("similarity") or bold_result.get("similarity")
        result.bold_similarity = float(sim_val) if sim_val is not None else None
        result.bold_raw = bold_result.get("raw_response")
        result.bold_process_id = chosen.get("process_id") or bold_result.get("process_id")
        # Record alt (the next best after the chosen one)
        if matches and len(matches) > 1:
            if selection.get("self_hit") and selection.get("skipped"):
                alt = selection["skipped"]
            else:
                alt = matches[1]
            result.bold_alt_match = alt.get("match_name")
            result.bold_alt_similarity = alt.get("similarity")
            result.bold_alt_process_id = alt.get("process_id")
        # Preserve whether we skipped a likely self-hit
        result.bold_self_hit = bool(selection.get("self_hit"))

        # If BOLD did not return a BIN, try to recover it via the process ID
        if not result.bin_number and result.bold_process_id:
            recovered_bin = lookup_bin_from_processid(result.bold_process_id)
            if recovered_bin:
                result.bin_number = recovered_bin

        # If we have a BIN URI, attempt to pull BIN-level metrics (p-distance, nearest neighbour)
        if result.bin_number:
            try:
                bin_info = fetch_bin_metrics(result.bin_number)
                result.bin_avg_distance = bin_info.get("avg_distance")
                result.bin_nn_distance = bin_info.get("nn_distance")
                result.bin_nearest_bin = bin_info.get("nearest_bin")
                result.bin_nearest_member = bin_info.get("nearest_member")
                result.bin_nearest_taxonomy = bin_info.get("nearest_taxonomy")
            except Exception:
                # Non-fatal; keep core workflow result even if BIN fetch fails
                pass

        result.success = True
        return result

    except requests.exceptions.Timeout as exc:
        result.error = f"Timeout contacting remote service: {exc}"
        return result
    except Exception as exc:
        result.error = str(exc)
        return result


def run_bold_workflow(
    gca_accessions: Iterable[str],
    wait_seconds: int = 5,
    output_csv: Optional[str] = None,
) -> pd.DataFrame:
    """
    Run the full workflow for a list of GCA accessions.

    Args:
        gca_accessions: list/iterable of assembly accessions.
        wait_seconds: polite pause between NCBI/BOLD queries.
        output_csv: optional path to store the table.
    """
    rows: List[Dict[str, object]] = []
    gca_list = list(gca_accessions)
    for idx, gca in enumerate(gca_list, start=1):
        print(f"[{idx}/{len(gca_list)}] Processing {gca} ...")
        result = process_gca_accession(gca)
        if result.success:
            print(
                f"  Success: {result.mt_accession} ({result.mt_length} bp) "
                f"COI {result.coi_length} bp | bin {result.bin_number}"
            )
        else:
            print(f"  Failed: {result.error}")
        rows.append(result.to_dict())
        if wait_seconds and idx < len(gca_list):
            time.sleep(wait_seconds)

    df = pd.DataFrame(rows)
    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"Wrote results to {output_csv}")
    return df


def format_result_summary(result: Dict[str, object]) -> str:
    """Generate a short prose snippet for a single workflow result."""
    if not result.get("success"):
        return f"{result.get('gca_accession')}: workflow failed ({result.get('error')})."

    bits = [
        f"Mitochondrial COI ({result.get('coi_length')} bp) extracted from {result.get('mt_accession')}."
    ]
    if result.get("coi_identity") is not None:
        bits.append(
            f"BLAST identity {(float(result['coi_identity']) * 100):.1f}% to {result.get('coi_match_title')}"
        )
    if result.get("bold_match"):
        bits.append(
            f"BOLD top match {result['bold_match']} ({result.get('bold_similarity')}% similarity)"
        )
    if result.get("bin_number"):
        bits.append(f"BIN {result['bin_number']}")

    return " ".join(bits)


def read_accessions_file(path: str) -> List[str]:
    """Read one GCA accession per line from a plain-text file."""
    accessions: List[str] = []
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            accessions.append(line)
    return accessions


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser for the workflow."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract the COI barcode from a mitochondrial genome and query BOLD "
            "for BIN assignments from one or more GCA accessions."
        )
    )
    parser.add_argument(
        "gca_accessions",
        nargs="*",
        help="One or more GCA assembly accessions, for example GCA_964291005.1.",
    )
    parser.add_argument(
        "--accessions-file",
        help="Optional text file containing one GCA accession per line.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=5,
        help="Pause between remote queries. Default: 5 seconds.",
    )
    parser.add_argument(
        "--output-csv",
        help="Optional path to write the full result table as CSV.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print one-line summaries instead of the tabular output.",
    )
    return parser


def _collect_accessions(args: argparse.Namespace) -> List[str]:
    accessions = list(args.gca_accessions)
    if args.accessions_file:
        accessions.extend(read_accessions_file(args.accessions_file))
    deduplicated = list(dict.fromkeys(accessions))
    if not deduplicated:
        raise ValueError("Provide at least one GCA accession or --accessions-file.")
    return deduplicated


def _print_cli_output(df: pd.DataFrame, summary_only: bool) -> None:
    if df.empty:
        print("No results returned.")
        return

    display_cols = [
        "gca_accession",
        "success",
        "mt_accession",
        "mt_length",
        "mt_species",
        "coi_length",
        "bin_number",
        "bold_match",
        "bold_similarity",
        "bold_process_id",
        "bold_alt_match",
        "bold_alt_similarity",
        "bold_alt_process_id",
        "bold_self_hit",
        "error",
        "bin_avg_distance",
        "bin_nn_distance",
        "bin_nearest_bin",
        "bin_nearest_member",
        "bin_nearest_taxonomy",
    ]
    if not summary_only:
        print(df[display_cols].to_string(index=False))
        print()

    print("Summaries:")
    for row in df.to_dict("records"):
        print(f"- {format_result_summary(row)}")


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the command-line interface."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        accessions = _collect_accessions(args)
    except ValueError as exc:
        parser.error(str(exc))

    df = run_bold_workflow(
        accessions,
        wait_seconds=args.wait_seconds,
        output_csv=args.output_csv,
    )
    _print_cli_output(df, summary_only=args.summary_only)

    if "success" not in df:
        return 1
    return 0 if bool(df["success"].all()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


__all__ = [
    "WorkflowResult",
    "get_mitochondrial_accession",
    "fetch_mitochondrial_sequence",
    "blast_for_coi_region",
    "query_bold_for_coi",
    "fetch_bin_metrics",
    "lookup_bin_from_processid",
    "process_gca_accession",
    "run_bold_workflow",
    "format_result_summary",
    "read_accessions_file",
    "build_arg_parser",
    "main",
]
