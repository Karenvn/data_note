from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthorityFormatting:
    authority: str
    status: str
    original_combination: str | None = None


def extract_year_from_authorship(authorship: str | None) -> int | None:
    match = re.search(r"\b(17|18|19|20)\d{2}\b", str(authorship or ""))
    return int(match.group()) if match else None


def genus_from_name(name: str | None) -> str | None:
    parts = str(name or "").strip().split()
    return parts[0] if len(parts) >= 2 else None


def specific_epithet_from_name(name: str | None) -> str | None:
    parts = str(name or "").strip().split()
    return parts[1] if len(parts) >= 2 else None


def clean_authorship(authorship: str) -> str:
    return re.sub(r"[\[\]()]", "", authorship).strip()


def has_wrapping_parentheses(authorship: str) -> bool:
    text = authorship.strip()
    return text.startswith("(") and text.endswith(")")


def format_taxonomic_authority(
    authorship: str | None,
    *,
    current_name: str | None,
    original_name: str | None = None,
) -> AuthorityFormatting:
    raw_authorship = str(authorship or "").strip()
    if not raw_authorship:
        return AuthorityFormatting("", "NO_AUTHORSHIP", original_name or None)

    current_genus = genus_from_name(current_name)
    original_genus = genus_from_name(original_name)
    clean = clean_authorship(raw_authorship)
    has_brackets = has_wrapping_parentheses(raw_authorship)

    if original_genus and current_genus:
        if original_genus != current_genus:
            if has_brackets:
                return AuthorityFormatting(raw_authorship, "CORRECT_WITH_BRACKETS", original_name)
            return AuthorityFormatting(f"({clean})", "SOURCE_MISSING_BRACKETS", original_name)

        if has_brackets:
            return AuthorityFormatting(clean, "SOURCE_UNNEEDED_BRACKETS", original_name)
        return AuthorityFormatting(clean, "CORRECT_NO_BRACKETS", original_name)

    if has_brackets:
        return AuthorityFormatting(raw_authorship, "TRUST_SOURCE_WITH_BRACKETS", original_name or None)
    return AuthorityFormatting(clean, "TRUST_SOURCE_NO_BRACKETS", original_name or None)


def find_earliest_original_combination(
    synonym_records: list[dict[str, Any]],
    current_name: str,
) -> str | None:
    current_genus = genus_from_name(current_name)
    current_epithet = specific_epithet_from_name(current_name)
    if not current_genus or not current_epithet:
        return None

    candidates: list[tuple[int, str]] = []
    for synonym in synonym_records:
        status = str(synonym.get("taxonomicStatus") or "").upper()
        if status not in {"SYNONYM", "HETEROTYPIC_SYNONYM", "HOMOTYPIC_SYNONYM"}:
            continue

        canonical = str(synonym.get("canonicalName") or "").strip()
        genus = genus_from_name(canonical)
        epithet = specific_epithet_from_name(canonical)
        if not genus or genus == current_genus or epithet != current_epithet:
            continue

        year = extract_year_from_authorship(synonym.get("authorship"))
        candidates.append((year if year is not None else 9999, canonical))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]
