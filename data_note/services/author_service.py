from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

import yaml

from ..models import AuthorInfo

logger = logging.getLogger(__name__)


AUTHOR_SLOT_ORDER: tuple[tuple[str, str], ...] = (
    ("pacbio", "collector"),
    ("pacbio", "identifier"),
    ("hic", "collector"),
    ("hic", "identifier"),
    ("rna", "collector"),
    ("rna", "identifier"),
)

ROLE_CREDITS = {
    "collector": ("Resources", "Investigation"),
    "identifier": ("Resources", "Investigation"),
}


class _IndentedYamlDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):  # type: ignore[override]
        return super().increase_indent(flow, False)


@dataclass(slots=True)
class AuthorService:
    db_path: Path | None = None

    def build_context(self, context: Mapping[str, Any]) -> AuthorInfo:
        db_path = self._resolved_db_path()
        if not db_path.exists():
            logger.warning("Author DB not found at %s; leaving author block empty.", db_path)
            return self._empty_context()

        slot_refs = self._build_slot_refs(context)
        if not slot_refs:
            return self._empty_context()

        authors = self._fetch_authors(slot_refs, db_path)
        affiliations = self._build_affiliations(authors)
        author_entries = self._author_yaml_entries(authors, affiliations)
        affiliation_entries = [item["yaml"] for item in affiliations]

        return AuthorInfo.from_legacy_parts(
            people=author_entries,
            affiliations=affiliation_entries,
            yaml_block=self._render_yaml_block(author_entries, affiliation_entries),
        )

    def _resolved_db_path(self) -> Path:
        if self.db_path is not None:
            return self.db_path
        default_assets = os.getenv("DATA_NOTE_GN_ASSETS") or os.getenv("DATA_NOTE_SERVER_DATA") or str(Path.home() / "gn_assets")
        default_db = str(Path(default_assets).expanduser() / "author_db.sqlite3")
        return Path(os.getenv("DATA_NOTE_AUTHOR_DB", default_db)).expanduser()

    def _build_slot_refs(self, context: Mapping[str, Any]) -> list[dict[str, Any]]:
        technology_data = context.get("technology_data") or {}
        refs: list[dict[str, Any]] = []

        for tech, role in AUTHOR_SLOT_ORDER:
            tech_data = technology_data.get(tech) or {}
            accession_key = f"{tech}_sample_accession"
            specimen_key = f"{tech}_specimen_id"
            biosample_accessions = self._split_accessions(
                tech_data.get(accession_key) or context.get(accession_key) or ""
            )
            specimen_id = self._clean_string(context.get(specimen_key))
            raw_names = self._split_raw_names(context.get(f"{tech}_{role}"))
            if biosample_accessions or specimen_id:
                refs.append(
                    {
                        "tech": tech,
                        "role": role,
                        "biosample_accessions": biosample_accessions,
                        "specimen_id": specimen_id,
                        "raw_names": raw_names,
                    }
                )

        return refs

    @staticmethod
    def _split_accessions(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, (list, tuple, set)):
            items = value
        else:
            items = str(value).replace(",", ";").split(";")
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            cleaned = str(item).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @staticmethod
    def _clean_string(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    def _fetch_authors(self, slot_refs: list[dict[str, Any]], db_path: Path) -> list[dict[str, Any]]:
        ordered_authors: list[dict[str, Any]] = []
        authors_by_key: dict[tuple[str, str], dict[str, Any]] = {}

        with closing(sqlite3.connect(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            for slot_ref in slot_refs:
                slot_rows = self._fetch_slot_rows(connection, slot_ref)
                for row in slot_rows:
                    author = self._matched_author_from_row(row)
                    self._merge_author(
                        author,
                        slot_ref,
                        ordered_authors,
                        authors_by_key,
                    )

                self._merge_raw_name_fallbacks(
                    connection,
                    slot_ref,
                    ordered_authors,
                    authors_by_key,
                )

        return ordered_authors

    def _fetch_slot_rows(self, connection: sqlite3.Connection, slot_ref: Mapping[str, Any]) -> list[sqlite3.Row]:
        rows: list[sqlite3.Row] = []
        for accession in slot_ref["biosample_accessions"]:
            rows.extend(self._query_rows(connection, "biosample_accession", accession, slot_ref["role"]))

        if rows:
            return rows

        specimen_id = slot_ref.get("specimen_id")
        if specimen_id:
            return self._query_rows(connection, "specimen_id", specimen_id, slot_ref["role"])

        return rows

    @staticmethod
    def _query_rows(
        connection: sqlite3.Connection,
        lookup_field: str,
        lookup_value: str,
        role: str,
    ) -> list[sqlite3.Row]:
        query = f"""
            SELECT
                sr.sample_role_id,
                s.sample_id,
                s.specimen_id,
                s.biosample_accession,
                s.tolid,
                rt.code AS role,
                sr.raw_name,
                p.person_id,
                p.canonical_name,
                p.given_names,
                p.family_name,
                p.orcid,
                c.value AS email,
                a.name AS affiliation
            FROM sample_role sr
            JOIN sample s ON s.sample_id = sr.sample_id
            JOIN role_type rt ON rt.role_type_id = sr.role_type_id
            JOIN person p ON p.person_id = sr.person_id
            LEFT JOIN contact c
                ON c.person_id = p.person_id
               AND c.type = 'email'
               AND c.is_primary = 1
            LEFT JOIN person_affiliation pa
                ON pa.person_id = p.person_id
               AND pa.is_current = 1
            LEFT JOIN affiliation a ON a.affiliation_id = pa.affiliation_id
            WHERE s.{lookup_field} = ?
              AND rt.code = ?
              AND p.is_active = 1
            ORDER BY sr.sample_role_id
        """
        return list(connection.execute(query, (lookup_value, role)).fetchall())

    def _matched_author_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        given_names, family_name = self._split_person_name(
            row["given_names"], row["family_name"], row["canonical_name"]
        )
        return {
            "person_id": int(row["person_id"]),
            "canonical_name": row["canonical_name"],
            "given_names": given_names,
            "family_name": family_name,
            "email": row["email"] or "",
            "orcid": row["orcid"] or "",
            "affiliation_name": row["affiliation"] or "",
            "credit_roles": [],
            "sample_roles": [],
            "source_slots": [],
            "is_placeholder": False,
            "raw_name": row["raw_name"] or row["canonical_name"],
        }

    def _merge_raw_name_fallbacks(
        self,
        connection: sqlite3.Connection,
        slot_ref: Mapping[str, Any],
        ordered_authors: list[dict[str, Any]],
        authors_by_key: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        for raw_name in slot_ref.get("raw_names", []):
            matched_author = self._lookup_person_by_name(connection, raw_name)
            if matched_author is not None:
                author = matched_author
            else:
                author = self._placeholder_author(raw_name)
            self._merge_author(author, slot_ref, ordered_authors, authors_by_key)

    def _merge_author(
        self,
        author: dict[str, Any],
        slot_ref: Mapping[str, Any],
        ordered_authors: list[dict[str, Any]],
        authors_by_key: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        key = self._author_key(author)
        existing = authors_by_key.get(key)

        if existing is None and author.get("person_id") is not None:
            existing = self._match_existing_alias(author, authors_by_key)
            if existing is not None and existing.get("is_placeholder"):
                authors_by_key[key] = existing
                self._upgrade_placeholder(existing, author)

        if existing is None and author.get("is_placeholder"):
            existing = self._match_existing_alias(author, authors_by_key)
            if existing is not None:
                authors_by_key[key] = existing

        if existing is None:
            existing = author
            ordered_authors.append(existing)
            authors_by_key[key] = existing
        elif existing is not author and author.get("person_id") is not None and existing.get("is_placeholder"):
            self._upgrade_placeholder(existing, author)
            authors_by_key[key] = existing

        self._register_aliases(existing, authors_by_key)

        credit_roles = ROLE_CREDITS.get(slot_ref["role"], ())
        for credit_role in credit_roles:
            if credit_role not in existing["credit_roles"]:
                existing["credit_roles"].append(credit_role)
        if slot_ref["role"] not in existing["sample_roles"]:
            existing["sample_roles"].append(slot_ref["role"])
        slot_name = f'{slot_ref["tech"]}_{slot_ref["role"]}'
        if slot_name not in existing["source_slots"]:
            existing["source_slots"].append(slot_name)

    @staticmethod
    def _author_key(author: Mapping[str, Any]) -> tuple[str, str]:
        person_id = author.get("person_id")
        if person_id is not None:
            return ("person", str(person_id))
        return ("raw", AuthorService._normalize_name(author.get("raw_name") or author.get("canonical_name") or ""))

    def _match_existing_alias(
        self,
        author: Mapping[str, Any],
        authors_by_key: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any] | None:
        for alias_key in self._author_alias_keys(author):
            existing = authors_by_key.get(alias_key)
            if existing is not None:
                return existing
        return None

    def _register_aliases(
        self,
        author: Mapping[str, Any],
        authors_by_key: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        for alias_key in self._author_alias_keys(author):
            existing = authors_by_key.get(alias_key)
            if existing is None or existing.get("is_placeholder"):
                authors_by_key[alias_key] = author

    def _author_alias_keys(self, author: Mapping[str, Any]) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for field in ("raw_name", "canonical_name"):
            normalized = self._normalize_name(author.get(field) or "")
            if normalized:
                keys.add(("raw", normalized))
        return keys

    @staticmethod
    def _upgrade_placeholder(target: dict[str, Any], source: Mapping[str, Any]) -> None:
        target["person_id"] = source.get("person_id")
        target["canonical_name"] = source.get("canonical_name", target["canonical_name"])
        target["given_names"] = source.get("given_names", target["given_names"])
        target["family_name"] = source.get("family_name", target["family_name"])
        target["email"] = source.get("email", target["email"])
        target["orcid"] = source.get("orcid", target["orcid"])
        target["affiliation_name"] = source.get("affiliation_name", target["affiliation_name"])
        target["is_placeholder"] = False

    def _lookup_person_by_name(self, connection: sqlite3.Connection, raw_name: str) -> dict[str, Any] | None:
        normalized = self._normalize_name(raw_name)
        if not normalized:
            return None

        direct_query = """
            SELECT
                p.person_id,
                p.canonical_name,
                p.given_names,
                p.family_name,
                p.orcid,
                c.value AS email,
                a.name AS affiliation
            FROM person p
            LEFT JOIN person_alias pa2
                ON pa2.person_id = p.person_id
            LEFT JOIN contact c
                ON c.person_id = p.person_id
               AND c.type = 'email'
               AND c.is_primary = 1
            LEFT JOIN person_affiliation pa
                ON pa.person_id = p.person_id
               AND pa.is_current = 1
            LEFT JOIN affiliation a
                ON a.affiliation_id = pa.affiliation_id
            WHERE p.is_active = 1
              AND (
                    lower(p.canonical_name) = lower(?)
                 OR replace(replace(lower(p.canonical_name), '.', ''), ',', '') = ?
                 OR pa2.norm_alias = ?
              )
            ORDER BY
                CASE
                    WHEN lower(p.canonical_name) = lower(?) THEN 0
                    WHEN replace(replace(lower(p.canonical_name), '.', ''), ',', '') = ? THEN 1
                    ELSE 2
                END,
                p.person_id
        """
        rows = list(
            connection.execute(
                direct_query,
                (
                    raw_name.strip(),
                    normalized,
                    normalized,
                    raw_name.strip(),
                    normalized,
                ),
            ).fetchall()
        )
        if rows:
            exact_person_ids = {int(row["person_id"]) for row in rows}
            if len(exact_person_ids) > 1:
                return None
            return self._author_from_person_row(rows[0], raw_name)

        staged_query = """
            SELECT DISTINCT srn.matched_person_id
            FROM staging_role_name srn
            WHERE srn.matched_person_id IS NOT NULL
              AND srn.match_status != 'unmatched'
              AND (
                    lower(srn.raw_name) = lower(?)
                 OR replace(replace(lower(srn.raw_name), '.', ''), ',', '') = ?
                 OR lower(srn.cleaned_name) = lower(?)
                 OR replace(replace(lower(srn.cleaned_name), '.', ''), ',', '') = ?
              )
        """
        staged_person_ids = [
            int(row[0])
            for row in connection.execute(
                staged_query,
                (raw_name.strip(), normalized, raw_name.strip(), normalized),
            ).fetchall()
        ]
        staged_person_ids = list(dict.fromkeys(staged_person_ids))
        if len(staged_person_ids) != 1:
            return None

        person_query = """
            SELECT
                p.person_id,
                p.canonical_name,
                p.given_names,
                p.family_name,
                p.orcid,
                c.value AS email,
                a.name AS affiliation
            FROM person p
            LEFT JOIN contact c
                ON c.person_id = p.person_id
               AND c.type = 'email'
               AND c.is_primary = 1
            LEFT JOIN person_affiliation pa
                ON pa.person_id = p.person_id
               AND pa.is_current = 1
            LEFT JOIN affiliation a
                ON a.affiliation_id = pa.affiliation_id
            WHERE p.person_id = ?
              AND p.is_active = 1
        """
        row = connection.execute(person_query, (staged_person_ids[0],)).fetchone()
        if row is None:
            return None
        return self._author_from_person_row(row, raw_name)

    def _author_from_person_row(self, row: sqlite3.Row, raw_name: str) -> dict[str, Any]:
        given_names, family_name = self._split_person_name(
            row["given_names"], row["family_name"], row["canonical_name"]
        )
        return {
            "person_id": int(row["person_id"]),
            "canonical_name": row["canonical_name"],
            "given_names": given_names,
            "family_name": family_name,
            "email": row["email"] or "",
            "orcid": row["orcid"] or "",
            "affiliation_name": row["affiliation"] or "",
            "credit_roles": [],
            "sample_roles": [],
            "source_slots": [],
            "is_placeholder": False,
            "raw_name": raw_name,
        }

    def _placeholder_author(self, raw_name: str) -> dict[str, Any]:
        given_names, family_name = self._split_person_name(None, None, raw_name)
        return {
            "person_id": None,
            "canonical_name": raw_name.strip(),
            "given_names": given_names,
            "family_name": family_name,
            "email": "",
            "orcid": "",
            "affiliation_name": "",
            "credit_roles": [],
            "sample_roles": [],
            "source_slots": [],
            "is_placeholder": True,
            "raw_name": raw_name.strip(),
        }

    @staticmethod
    def _split_person_name(given_names: str | None, family_name: str | None, canonical_name: str | None) -> tuple[str, str]:
        clean_given = (given_names or "").strip()
        clean_family = (family_name or "").strip()
        if clean_given and clean_family:
            return clean_given, clean_family

        full_name = (canonical_name or "").strip()
        if not full_name:
            return "", ""
        if " " not in full_name:
            return full_name, ""

        parts = full_name.rsplit(" ", 1)
        return parts[0], parts[1]

    @staticmethod
    def _split_raw_names(value: Any) -> list[str]:
        if not value:
            return []
        text = str(value).strip()
        if not text:
            return []
        parts = re.split(r"\s*\|\s*|\s*;\s*", text)
        seen: set[str] = set()
        result: list[str] = []
        for part in parts:
            cleaned = " ".join(part.split()).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @staticmethod
    def _normalize_name(value: str) -> str:
        lowered = value.lower().strip()
        lowered = lowered.replace(".", "").replace(",", "")
        return " ".join(lowered.split())

    def _build_affiliations(self, authors: list[dict[str, Any]]) -> list[dict[str, Any]]:
        affiliations: list[dict[str, Any]] = []
        by_name: dict[str, dict[str, Any]] = {}

        for author in authors:
            affiliation_name = author["affiliation_name"].strip()
            if not affiliation_name:
                continue
            if affiliation_name not in by_name:
                affiliation_id = str(len(affiliations) + 1)
                parsed_affiliation = self._parse_affiliation(affiliation_name)
                record = {
                    "name": affiliation_name,
                    "id": affiliation_id,
                    "yaml": {"id": affiliation_id, **parsed_affiliation},
                }
                by_name[affiliation_name] = record
                affiliations.append(record)

        return affiliations

    @staticmethod
    def _parse_affiliation(affiliation_name: str) -> dict[str, str]:
        parts = [part.strip() for part in affiliation_name.split(",") if part.strip()]
        if not parts:
            return {"organization": affiliation_name}
        if len(parts) >= 5:
            organization = ", ".join(parts[:-4])
            city = ", ".join(parts[-4:-2])
            state, country = parts[-2:]
            return {
                "organization": organization,
                "city": city,
                "state": state,
                "country": country,
            }
        if len(parts) >= 4:
            organization = ", ".join(parts[:-3])
            city, state, country = parts[-3:]
            return {
                "organization": organization,
                "city": city,
                "state": state,
                "country": country,
            }
        if len(parts) == 3:
            return {
                "organization": parts[0],
                "city": parts[1],
                "country": parts[2],
            }
        return {"organization": affiliation_name}

    def _author_yaml_entries(
        self,
        authors: list[dict[str, Any]],
        affiliations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        affiliation_map = {item["name"]: item["id"] for item in affiliations}
        entries: list[dict[str, Any]] = []

        for author in authors:
            entry: dict[str, Any] = {
                "given-names": author["given_names"],
                "surname": author["family_name"],
            }
            if author.get("is_placeholder"):
                entry["email"] = ""
                entry["affiliation"] = ""
            elif author["email"]:
                entry["email"] = author["email"]
            if author["orcid"]:
                entry["orcid"] = author["orcid"]
            affiliation_id = affiliation_map.get(author["affiliation_name"])
            if affiliation_id:
                entry["affiliation"] = affiliation_id
            entry["roles"] = [{"credit": credit} for credit in author["credit_roles"]]
            entries.append(entry)

        return entries

    @staticmethod
    def _render_yaml_block(author_entries: list[dict[str, Any]], affiliation_entries: list[dict[str, Any]]) -> str:
        return yaml.dump(
            {"author": author_entries, "affiliation": affiliation_entries},
            Dumper=_IndentedYamlDumper,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).strip()

    def _empty_context(self) -> AuthorInfo:
        author_entries: list[dict[str, Any]] = []
        affiliation_entries: list[dict[str, Any]] = []
        return AuthorInfo.from_legacy_parts(
            people=author_entries,
            affiliations=affiliation_entries,
            yaml_block=self._render_yaml_block(author_entries, affiliation_entries),
        )
