from __future__ import annotations

from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import yaml

from data_note.models import AuthorInfo
from data_note.services.author_service import AuthorService


def _build_test_db(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE sample (
                sample_id TEXT PRIMARY KEY,
                sample_type TEXT,
                specimen_id TEXT,
                biosample_accession TEXT,
                tolid TEXT,
                species TEXT,
                project TEXT,
                collection_country TEXT,
                collection_locality TEXT,
                collection_date TEXT,
                gal_name TEXT,
                informatics_status_summary TEXT,
                assembly_status TEXT,
                has_role_names INTEGER DEFAULT 0
            );

            CREATE TABLE role_type (
                role_type_id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                description TEXT
            );

            CREATE TABLE person (
                person_id INTEGER PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                given_names TEXT,
                family_name TEXT,
                orcid TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE person_alias (
                alias_id INTEGER PRIMARY KEY,
                person_id INTEGER,
                alias_name TEXT,
                norm_alias TEXT,
                source TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE contact (
                contact_id INTEGER PRIMARY KEY,
                person_id INTEGER,
                type TEXT,
                value TEXT,
                is_primary INTEGER
            );

            CREATE TABLE affiliation (
                affiliation_id INTEGER PRIMARY KEY,
                name TEXT,
                ror_id TEXT,
                institution TEXT,
                city TEXT,
                state TEXT,
                country TEXT
            );

            CREATE TABLE person_affiliation (
                person_affiliation_id INTEGER PRIMARY KEY,
                person_id INTEGER,
                affiliation_id INTEGER,
                is_current INTEGER
            );

            CREATE TABLE sample_role (
                sample_role_id INTEGER PRIMARY KEY,
                sample_id TEXT NOT NULL,
                person_id INTEGER NOT NULL,
                role_type_id INTEGER NOT NULL,
                raw_name TEXT,
                normalized_name TEXT,
                source_field TEXT,
                source TEXT,
                evidence TEXT,
                confidence REAL,
                decided_by TEXT,
                decided_at TEXT
            );

            CREATE TABLE staging_role_name (
                staging_id INTEGER PRIMARY KEY,
                sample_id TEXT NOT NULL,
                specimen_id TEXT,
                role_code TEXT NOT NULL,
                raw_name TEXT NOT NULL,
                cleaned_name TEXT,
                norm_raw_name TEXT NOT NULL,
                source_field TEXT,
                source TEXT,
                matched_person_id INTEGER,
                match_status TEXT NOT NULL DEFAULT 'unmatched',
                loaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        connection.executemany(
            "INSERT INTO role_type(role_type_id, code, description) VALUES (?, ?, ?)",
            [
                (1, "collector", "Collected the specimen"),
                (2, "identifier", "Identified the specimen"),
                (3, "preserver", "Preserved the specimen"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO sample(sample_id, specimen_id, biosample_accession, tolid, species, project)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("1", "SPEC-P", "BS-P", "tol1", "Species one", "DTOL"),
                ("2", "SPEC-H", "BS-H", "tol1", "Species one", "DTOL"),
                ("3", "SPEC-R", "BS-R", "tol1", "Species one", "DTOL"),
                ("4", "SPEC-F", "", "tol1", "Species one", "DTOL"),
                ("5", "SPEC-S", "BS-S", "tol2", "Species two", "DTOL"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO person(person_id, canonical_name, given_names, family_name, orcid)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "Alice Able", "Alice", "Able", "0000-0000-0000-0001"),
                (2, "Bob Baker", "Bob", "Baker", ""),
                (3, "Cara Cole", "Cara", "Cole", ""),
                (4, "Dan Drew", "Dan", "Drew", ""),
                (5, "Eve Ellis", "Eve", "Ellis", ""),
                (6, "Fran Frost", "Fran", "Frost", ""),
                (7, "Liam M. Crowley", "Liam M.", "Crowley", "0000-0001-6380-0329"),
                (8, "Susan C. Taylor", "Susan C.", "Taylor", ""),
                (9, "David Geoffrey Long", "David Geoffrey", "Long", "0000-0003-0816-0124"),
            ],
        )

        connection.executemany(
            "INSERT INTO contact(contact_id, person_id, type, value, is_primary) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, "email", "alice@example.org", 1),
                (2, 2, "email", "bob@example.org", 1),
                (3, 3, "email", "cara@example.org", 1),
                (4, 4, "email", "dan@example.org", 1),
                (5, 5, "email", "eve@example.org", 1),
                (6, 6, "email", "fran@example.org", 1),
                (7, 7, "email", "liam@example.org", 1),
                (8, 8, "email", "susan@example.org", 1),
                (9, 9, "email", "david.long@example.org", 1),
            ],
        )

        connection.executemany(
            "INSERT INTO affiliation(affiliation_id, name, institution, city, state, country) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "Museum of Testing, London, England, GB", "Museum of Testing", "London", "England", "GB"),
                (2, "Institute of Examples, Edinburgh, Scotland, GB", "Institute of Examples", "Edinburgh", "Scotland", "GB"),
                (3, "University of Oxford, Oxford, Oxfordshire, England, GB", "University of Oxford", "Oxford", "Oxfordshire", "GB"),
                (4, "Independent researcher, Berkhamsted, Hertfordshire, England, GB", "Independent researcher", "Berkhamsted", "Hertfordshire", "GB"),
            ],
        )

        connection.executemany(
            "INSERT INTO person_affiliation(person_affiliation_id, person_id, affiliation_id, is_current) VALUES (?, ?, ?, ?)",
            [
                (1, 1, 1, 1),
                (2, 2, 1, 1),
                (3, 3, 2, 1),
                (4, 4, 2, 1),
                (5, 5, 2, 1),
                (6, 6, 2, 1),
                (7, 7, 3, 1),
                (8, 8, 4, 1),
                (9, 9, 2, 1),
            ],
        )

        connection.executemany(
            """
            INSERT INTO sample_role(sample_role_id, sample_id, person_id, role_type_id, raw_name, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "1", 1, 1, "Alice Able", "test"),
                (2, "1", 2, 2, "Bob Baker", "test"),
                (3, "2", 1, 1, "Alice Able", "test"),
                (4, "2", 3, 2, "Cara Cole", "test"),
                (5, "3", 4, 1, "Dan Drew", "test"),
                (6, "3", 5, 2, "Eve Ellis", "test"),
                (7, "4", 6, 1, "Fran Frost", "test"),
                (8, "4", 6, 2, "Fran Frost", "test"),
                (9, "5", 8, 1, "Sue Taylor", "test"),
                (10, "5", 8, 2, "Sue Taylor", "test"),
            ],
        )

        connection.execute(
            """
            INSERT INTO staging_role_name(
                staging_id, sample_id, specimen_id, role_code, raw_name, cleaned_name,
                norm_raw_name, source_field, source, matched_person_id, match_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1, "1", "SPEC-P", "preserver", "Liam Crowley", "Liam M. Crowley",
                "liam crowley", "test_field", "test", 7, "exact"
            ),
        )


class AuthorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "author_db.sqlite3"
        _build_test_db(self.db_path)
        self.service = AuthorService(self.db_path)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_orders_and_deduplicates_authors_across_slots(self) -> None:
        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "BS-P"},
                "hic": {"hic_sample_accession": "BS-H"},
                "rna": {"rna_sample_accession": "BS-R"},
            }
        }

        result = self.service.build_context(context)
        self.assertIsInstance(result, AuthorInfo)
        author_names = [f"{author.given_names} {author.surname}" for author in result.people]
        self.assertEqual(
            author_names,
            ["Alice Able", "Bob Baker", "Cara Cole", "Dan Drew", "Eve Ellis"],
        )

        parsed_yaml = yaml.safe_load(result.yaml_block)
        first_author = parsed_yaml["author"][0]
        self.assertEqual(
            first_author["roles"],
            [{"credit": "Resources"}, {"credit": "Investigation"}],
        )
        self.assertEqual(first_author["affiliation"], "1")
        self.assertEqual(
            parsed_yaml["affiliation"][0],
            {
                "id": "1",
                "organization": "Museum of Testing",
                "city": "London",
                "state": "England",
                "country": "GB",
            },
        )

    def test_merges_collector_and_identifier_credits_for_same_person(self) -> None:
        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "missing-accession"},
            },
            "pacbio_specimen_id": "SPEC-F",
        }

        result = self.service.build_context(context)
        self.assertEqual(len(result.people), 1)
        self.assertEqual(result.people[0].given_names, "Fran")
        self.assertEqual(
            result.people[0].roles,
            [{"credit": "Resources"}, {"credit": "Investigation"}],
        )

    def test_preserves_multiple_affiliations_for_single_author(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.execute(
                """
                INSERT INTO person_affiliation(person_affiliation_id, person_id, affiliation_id, is_current)
                VALUES (?, ?, ?, ?)
                """,
                (10, 1, 4, 0),
            )

        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "BS-P"},
            }
        }

        result = self.service.build_context(context)
        self.assertEqual(result.people[0].affiliation, ["1", "2"])

        parsed_yaml = yaml.safe_load(result.yaml_block)
        self.assertEqual(parsed_yaml["author"][0]["affiliation"], ["1", "2"])
        self.assertEqual(
            parsed_yaml["affiliation"][1],
            {
                "id": "2",
                "organization": "Independent researcher",
                "city": "Berkhamsted",
                "state": "Hertfordshire",
                "country": "GB",
            },
        )

    def test_uses_raw_name_fallback_and_placeholder_for_unmatched_people(self) -> None:
        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "missing-accession"},
            },
            "pacbio_collector": "Alice Able | Unmatched Person",
        }

        result = self.service.build_context(context)
        self.assertEqual(
            [f"{author.given_names} {author.surname}".strip() for author in result.people],
            ["Alice Able", "Unmatched Person"],
        )
        self.assertEqual(result.people[0].email, "alice@example.org")
        self.assertEqual(result.people[1].email, "")

        parsed_yaml = yaml.safe_load(result.yaml_block)
        self.assertEqual(parsed_yaml["author"][1]["email"], "")
        self.assertEqual(parsed_yaml["author"][1]["affiliation"], "")
        self.assertEqual(
            parsed_yaml["author"][1]["roles"],
            [{"credit": "Resources"}, {"credit": "Investigation"}],
        )

    def test_raw_name_fallback_applies_multi_person_semicolon_expansions(self) -> None:
        corrections_path = Path(self.tmpdir.name) / "name_corrections.json"
        corrections_path.write_text(
            json.dumps(
                {
                    "multi_person_expansions": {
                        "Roger Vila, Joan Carles Hinojosa": "Roger Vila; Joan Carles Hinojosa"
                    }
                }
            ),
            encoding="utf-8",
        )
        service = AuthorService(self.db_path, corrections_path)
        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "missing-accession"},
            },
            "pacbio_collector": "Roger Vila, Joan Carles Hinojosa",
        }

        result = service.build_context(context)

        self.assertEqual(
            [f"{author.given_names} {author.surname}" for author in result.people],
            ["Roger Vila", "Joan Carles Hinojosa"],
        )

    def test_biosamples_raw_name_order_takes_precedence_over_partial_db_rows(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.execute(
                """
                INSERT INTO sample(sample_id, specimen_id, biosample_accession, tolid, species, project)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("6", "SPEC-RAW", "BS-RAW", "tol3", "Species three", "DTOL"),
            )
            connection.execute(
                """
                INSERT INTO sample_role(sample_role_id, sample_id, person_id, role_type_id, raw_name, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (20, "6", 3, 1, "Cara Cole", "test"),
            )

        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "BS-RAW"},
            },
            "pacbio_collector": "Alice Able | Bob Baker | Cara Cole",
        }

        result = self.service.build_context(context)
        self.assertEqual(
            [f"{author.given_names} {author.surname}" for author in result.people],
            ["Alice Able", "Bob Baker", "Cara Cole"],
        )

        parsed_yaml = yaml.safe_load(result.yaml_block)
        self.assertEqual(
            [
                f"{author['given-names']} {author['surname']}"
                for author in parsed_yaml["author"]
            ],
            ["Alice Able", "Bob Baker", "Cara Cole"],
        )

    def test_uses_staged_name_match_for_corrected_raw_names(self) -> None:
        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "missing-accession"},
            },
            "pacbio_collector": "Liam Crowley",
        }

        result = self.service.build_context(context)
        self.assertEqual(
            [person.to_mapping() for person in result.people],
            [
                {
                    "given-names": "Liam M.",
                    "surname": "Crowley",
                    "email": "liam@example.org",
                    "orcid": "0000-0001-6380-0329",
                    "affiliation": "1",
                    "roles": [{"credit": "Resources"}, {"credit": "Investigation"}],
                }
            ],
        )

    def test_deduplicates_placeholder_when_sample_role_raw_name_matches_existing_person(self) -> None:
        context = {
            "technology_data": {
                "hic": {"hic_sample_accession": "BS-S"},
            },
            "hic_collector": "Sue Taylor",
            "hic_identifier": "Sue Taylor",
        }

        result = self.service.build_context(context)
        self.assertEqual(
            [person.to_mapping() for person in result.people],
            [
                {
                    "given-names": "Susan C.",
                    "surname": "Taylor",
                    "email": "susan@example.org",
                    "affiliation": "1",
                    "roles": [{"credit": "Resources"}, {"credit": "Investigation"}],
                }
            ],
        )

    def test_matches_shortened_given_names_to_unique_person(self) -> None:
        context = {
            "technology_data": {
                "pacbio": {"pacbio_sample_accession": "missing-accession"},
            },
            "pacbio_collector": "David Long",
        }

        result = self.service.build_context(context)
        self.assertEqual(
            [person.to_mapping() for person in result.people],
            [
                {
                    "given-names": "David Geoffrey",
                    "surname": "Long",
                    "email": "david.long@example.org",
                    "orcid": "0000-0003-0816-0124",
                    "affiliation": "1",
                    "roles": [{"credit": "Resources"}, {"credit": "Investigation"}],
                }
            ],
        )

    def test_returns_empty_yaml_block_when_database_is_missing(self) -> None:
        service = AuthorService(Path(self.tmpdir.name) / "does-not-exist.sqlite3")
        result = service.build_context(
            {
                "technology_data": {
                    "pacbio": {"pacbio_sample_accession": "BS-P"},
                }
            }
        )

        self.assertEqual(result.people, [])
        self.assertEqual(yaml.safe_load(result.yaml_block), {"author": [], "affiliation": []})


if __name__ == "__main__":
    unittest.main()
