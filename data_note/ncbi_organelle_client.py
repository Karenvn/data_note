from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

from Bio import Entrez
import requests

from .ncbi_datasets_client import safe_ncbi_request

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NcbiOrganelleClient:
    request_get: Callable[..., Any] = requests.get
    timeout: int = 30

    def fetch_organelle_info(self, accession: str) -> dict[str, Any]:
        reports = self.fetch_sequence_reports(accession)
        if not reports:
            raise RuntimeError("No reports found in the response.")

        mitochondria = []
        plastids = []

        for report in reports:
            if report.get("role") != "assembled-molecule":
                continue

            location_type = str(report.get("assigned_molecule_location_type", ""))
            chr_name = str(report.get("chr_name", "")).upper()
            length_kb = round(float(report.get("length", 0)) / 1000, 2)
            genbank_acc = report.get("genbank_accession", "N/A")
            refseq_acc = report.get("refseq_accession", "N/A")
            chosen_accession = genbank_acc if genbank_acc != "N/A" else refseq_acc
            organelle_data = {
                "length_kb": length_kb,
                "accession": chosen_accession,
                "chr_name": report.get("chr_name", ""),
                "gc_percent": report.get("gc_percent"),
                "description": location_type,
            }

            if location_type == "Mitochondrion" or chr_name in {"MT", "MITO"}:
                mitochondria.append(organelle_data)
            elif (
                location_type in {"Chloroplast", "Plastid"}
                or chr_name in {"PLTD", "CP", "CHLO"}
                or "plastid" in location_type.lower()
            ):
                plastids.append(organelle_data)

        result: dict[str, Any] = {}
        if mitochondria:
            result["mitochondria"] = mitochondria
            if len(mitochondria) == 1:
                result["length_mito_kb"] = f"{mitochondria[0]['length_kb']}"
                result["mito_accession"] = mitochondria[0]["accession"]
            else:
                result["length_mito_kb"] = [m["length_kb"] for m in mitochondria]
                result["mito_accessions"] = [m["accession"] for m in mitochondria]

        if plastids:
            result["plastids"] = plastids
            if len(plastids) == 1:
                result["length_plastid_kb"] = f"{plastids[0]['length_kb']}"
                result["plastid_accession"] = plastids[0]["accession"]
            else:
                result["length_plastid_kb"] = [p["length_kb"] for p in plastids]
                result["plastid_accessions"] = [p["accession"] for p in plastids]

        if not result:
            result["message"] = "No organelles found"
        return result

    @staticmethod
    def format_organelle_text(organelle_info: dict[str, Any]) -> dict[str, str]:
        formatted: dict[str, str] = {}
        if "mitochondria" in organelle_info:
            mito_list = organelle_info["mitochondria"]
            if len(mito_list) == 1:
                mitochondrion = mito_list[0]
                formatted["mito_text"] = (
                    f"length {mitochondrion['length_kb']} kb ({mitochondrion['accession']})"
                )
            else:
                mito_parts = [f"{m['length_kb']} kb ({m['accession']})" for m in mito_list]
                formatted["mito_text"] = "lengths " + ", ".join(mito_parts)

        if "plastids" in organelle_info:
            plastid_list = organelle_info["plastids"]
            if len(plastid_list) == 1:
                plastid = plastid_list[0]
                formatted["plastid_text"] = f"length {plastid['length_kb']} kb ({plastid['accession']})"
            else:
                plastid_parts = [f"{p['length_kb']} kb ({p['accession']})" for p in plastid_list]
                formatted["plastid_text"] = "lengths " + ", ".join(plastid_parts)

        return formatted

    def fetch_organelle_template_data(self, accession: str) -> dict[str, Any]:
        try:
            organelle_info = self.fetch_organelle_info(accession)
            formatted = self.format_organelle_text(organelle_info)
            return {
                "has_mitochondria": "mitochondria" in organelle_info,
                "has_plastids": "plastids" in organelle_info,
                "mito_display": formatted.get("mito_text", ""),
                "plastid_display": formatted.get("plastid_text", ""),
                "raw_organelle_data": organelle_info,
            }
        except Exception as exc:
            logger.warning("Error fetching organelle data for %s: %s", accession, exc)
            return {
                "has_mitochondria": False,
                "has_plastids": False,
                "error": str(exc),
            }

    def fetch_organelle_table(self, accession: str) -> list[dict[str, Any]]:
        organelle_list = []
        for report in self.fetch_sequence_reports(accession):
            location_type = str(report.get("assigned_molecule_location_type", ""))
            chr_name = str(report.get("chr_name", "")).upper()
            if report.get("role") != "assembled-molecule":
                continue
            is_organelle = (
                location_type in {"Mitochondrion", "Chloroplast", "Plastid"}
                or chr_name in {"MT", "MITO", "PLTD", "CP", "CHLO"}
                or "plastid" in location_type.lower()
            )
            if is_organelle:
                organelle_list.append(
                    {
                        "INSDC": report.get("genbank_accession", "N/A"),
                        "molecule": report.get("chr_name", ""),
                        "length": round(float(report.get("length", 0)) / 1e6, 3),
                        "GC": report.get("gc_percent"),
                        "type": location_type,
                    }
                )
        return organelle_list

    def fetch_sequence_reports(self, accession: str) -> list[dict[str, Any]]:
        api_url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/sequence_reports"
        response = safe_ncbi_request(
            api_url,
            self._headers(),
            request_get=self.request_get,
            timeout=self.timeout,
        )
        data = response.json() or {}
        return data.get("reports", [])

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "accept": "application/json",
            "User-Agent": f"Python script; {Entrez.email}",
        }


__all__ = ["NcbiOrganelleClient"]
