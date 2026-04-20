# Genome‑note auto‑intro generator
# 3 August 2025
# -------------------------------------------------------------
"""Minimal usage
>>> from data_note.models import AssemblyRecord, AssemblySelection
>>> asm = AssemblySelection(
...     assemblies_type="hap_asm",
...     hap1=AssemblyRecord(accession="GCA_964188265.1", assembly_name="ixExample1.hap1.1", role="hap1"),
...     hap2=AssemblyRecord(accession="GCA_964187955.1", assembly_name="ixExample1.hap2.1", role="hap2"),
... )
>>> sent = summarise_genomes(139089, asm, tolid="ilAgaZoeg1")
>>> sent
"""

import os
import re
import requests
from collections import defaultdict
from datetime import datetime
from typing import Any, Mapping
from num2words import num2words

from .models import AssemblyRecord, AssemblySelection

API_KEY = os.getenv("ENTREZ_API_KEY", "default_api_key")
HEADERS = {"accept": "application/json", "api-key": API_KEY}

CITATION_DATASETS = "O'Leary NA et al. Sci Data 2024;11:732. doi:10.1038/s41597-024-03571-y"

# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def text_num(n: int) -> str:
    return num2words(n) if n <= 10 else str(n)

def plural(n: int, singular: str) -> str:
    return singular if n == 1 else singular + "s"

def core_acc(acc: str) -> str:
    """Return numeric core of GCA_/GCF_ accession for de‑dup."""
    m = re.search(r"GC[AF]_(\d+)", acc)
    return m.group(1) if m else acc

# ------------------------------------------------------------------
# ncbi helpers
# ------------------------------------------------------------------

def get_lineage(species_taxid: int) -> dict:
    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{species_taxid}/dataset_report"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    cl = r.json()["reports"][0]["taxonomy"]["classification"]
    return {
        "species": cl["species"]["name"],
        "genus": cl["genus"]["name"],
        "genus_taxid": cl["genus"]["id"],
        "family": cl["family"]["name"],
        "family_taxid": cl["family"]["id"],
    }

def fetch_taxon_report(taxid: int) -> list:
    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report"
    r = requests.get(url, headers=HEADERS, params={"page_size": 1000}, timeout=60)
    r.raise_for_status()
    return r.json().get("reports", [])

_cache: dict[str, tuple[str, str, str]] = {}

def acc_info(acc: str):
    if acc in _cache:
        return _cache[acc]
    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{acc}/dataset_report"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    rep = r.json()["reports"][0]
    sp = rep.get("organism", {}).get("organism_name", "Unknown species")
    sub = rep.get("submitter", "") or rep.get("assembly_info", {}).get("submitter", "")
    rc = rep.get("assembly_info", {}).get("refseq_category", "na")
    _cache[acc] = (sp, sub.title(), rc)
    return _cache[acc]

# ------------------------------------------------------------------
# grouping
# ------------------------------------------------------------------

def group_reports(reports: list, ours: set[str], tolid: str | None):
    grouped = defaultdict(list)
    seen_core = set()
    for rep in reports:
        acc = rep["accession"]
        core = core_acc(acc)
        if core in seen_core:
            continue  # skip duplicate GCF/GCA copy
        seen_core.add(core)

        sp, sub, _ = acc_info(acc)
        key = tolid if (acc in ours or (tolid and tolid in rep.get("assembly_name", ""))) else sp
        level = rep.get("assembly_info", {}).get("assembly_level", "")
        grouped[key].append({
            "accession": acc,
            "species": sp,
            "submitter": sub,
            "level": level.lower(),  # e.g. chromosome, scaffold, contig
             })
    return grouped

# ------------------------------------------------------------------
# sentence pieces
# ------------------------------------------------------------------

def make_core_sentence(genus: str, family: str, species: str, g: int, f: int) -> str:
    date = datetime.now().strftime("%B %Y")
    # g is the number of genomes within the genus, f the number within the family
    g_word, f_word = text_num(g), text_num(f)
    cite = "[data obtained via NCBI datasets; @oleary2024NCBI]"
    if g == 1:
        return (f"This assembly is the first high‑quality genome for the genus *{genus}* and one of "
                f"{f_word} {plural(f, 'genome')} available for the family {family} as of {date} {cite}.")
    if g < 5 and f < 10:
        return (f"Only {f_word} {plural(f, 'genome')} are available for the family {family}. The present assembly is one of "
                f"{g_word} {plural(g, 'genome')} for the genus *{genus}* as of {date} {cite}.")
    if g < 10 and f < 20:
        return (f"Fewer than 20 genomes have been published for the family {family} as of {date}, including "
                f"{g_word} for the genus *{genus}*. This assembly adds chromosome‑scale data for the lineage.")
    return (f"Although numerous genomes exist for the family {family}, this assembly provides the first chromosomally "
            f"complete sequence for *{species}*, enabling comparative analyses {cite}.")


def _normalise_assembly_input(assembly_input: AssemblySelection | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(assembly_input, AssemblySelection):
        return assembly_input.to_context_dict()
    return dict(assembly_input)


# ------------------------------------------------------------------
# main driver
# ------------------------------------------------------------------

def summarise_genomes(
    species_taxid: int,
    assembly_input: AssemblySelection | Mapping[str, Any],
    tolid: str | None = None,
    show_tables: bool = True) -> str:
    asm_dict = _normalise_assembly_input(assembly_input)
    lineage = get_lineage(species_taxid)

    # --- determine our accessions first ---
    if asm_dict.get("assemblies_type") == "hap_asm":
        ours = {asm_dict.get("hap1_accession"), asm_dict.get("hap2_accession")} - {None}
    else:
        ours = {asm_dict.get("prim_accession"), asm_dict.get("alt_accession")} - {None}

    # --- optional RefSeq designation note ---
    ref_note = ""
    if asm_dict.get("include_refseq", True) and ours:
        _, _, refcat = acc_info(next(iter(ours)))
        if refcat == "reference genome":
            ref_note = " This assembly is the RefSeq reference assembly for this species."
        elif refcat == "representative genome":
            ref_note = " This assembly is the RefSeq representative assembly for this species."

    # --- fetch & group reports ---
    results = {}
    for lvl, tx in (("genus", lineage["genus_taxid"]), ("family", lineage["family_taxid"])):
        reps = fetch_taxon_report(tx)
        grouped = group_reports(reps, ours, tolid)
        results[lvl] = {"reports": reps, "grouped": grouped}

    g = len(results["genus"]["grouped"])
    f = len(results["family"]["grouped"])
    sentence = make_core_sentence(lineage["genus"], lineage["family"], lineage["species"], g, f)

    # species clause
    sp_records = results["genus"]["grouped"].get(lineage["species"], [])
    other = [r for r in sp_records if core_acc(r["accession"]) not in {core_acc(a) for a in ours}]

    # choose core sentence *after* knowing whether other assemblies exist
    if other:
        # describe the *highest* assembly level among the other records
        level_map = {"chromosome": 3, "scaffold": 2, "contig": 1}
        best_other = max(other, key=lambda r: level_map.get(r["level"], 0))
        label = best_other["level"] if best_other["level"] else "non‑chromosome"

        sentence = (
            f"A chromosomally complete genome sequence for *{lineage['species']}* is presented, "
            f"enabling comparative analyses [data obtained via NCBI datasets; @oleary2024NCBI]."
        )
    else:
        sentence = make_core_sentence(lineage["genus"], lineage["family"], lineage["species"], g, f)

    if other:
        accs = ", ".join(r["accession"] for r in other)
        subs = ", ".join(sorted({r["submitter"] for r in other if r["submitter"]}))
        sentence += (
                  f" Another {label}-level assembly for this species is also available "
                  f"({accs}; submitted by {subs})."
                  )

    else:
        if not (g == 1 or (g < 5 and f < 10)):
            sentence += " This is currently the only genome assembly available for this species."

    sentence += ref_note
        
    return sentence


# ------------------------------------------------------------------
# example run
# ------------------------------------------------------------------
if __name__ == "__main__":
    example_asm = AssemblySelection(
        assemblies_type="hap_asm",
        hap1=AssemblyRecord(accession="GCA_964188265.1", assembly_name="ixExample1.hap1.1", role="hap1"),
        hap2=AssemblyRecord(accession="GCA_964187955.1", assembly_name="ixExample1.hap2.1", role="hap2"),
    )
    intro = summarise_genomes(
        species_taxid=139089,   # Agapeta zoegana
        assembly_input=example_asm,
        tolid="ilAgaZoeg1",
        show_tables=False,
    )
    print("\nIntro sentence:\n", intro)
