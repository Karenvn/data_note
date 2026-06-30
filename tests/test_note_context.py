from __future__ import annotations

import unittest

from data_note.models import NoteContext


class NoteContextTests(unittest.TestCase):
    def test_ensure_tolid_from_assembly_name(self) -> None:
        context = NoteContext(assembly_name="icDenLine1.1")
        context.ensure_tolid()
        self.assertEqual(context.tolid, "icDenLine1")

    def test_format_parent_projects(self) -> None:
        context = NoteContext(
            parent_projects=[
                {"project_name": "Project A", "accession": "PRJEB1"},
                {"project_name": "Project B", "accession": "PRJEB2"},
            ]
        )
        context.set_formatted_parent_projects()
        self.assertEqual(context.formatted_parent_projects, "Project A (PRJEB1) and Project B (PRJEB2)")

    def test_format_parent_projects_treats_aegis_as_supplemental_without_explicit_funding(self) -> None:
        context = NoteContext(
            parent_projects=[
                {"project_name": "Darwin Tree of Life Project", "accession": "PRJEB40665"},
                {"project_name": "Sanger Institute Tree of Life Programme", "accession": "PRJEB43745"},
                {"project_name": "AEGIS", "accession": "PRJEB80366"},
            ]
        )

        context.set_formatted_parent_projects()

        self.assertEqual(
            context.formatted_parent_projects,
            "Darwin Tree of Life Project (PRJEB40665) and Sanger Institute Tree of Life Programme (PRJEB43745)",
        )
        self.assertEqual(context.formatted_supplemental_parent_projects, "AEGIS (PRJEB80366)")

    def test_format_parent_projects_keeps_aegis_when_explicitly_funded(self) -> None:
        context = NoteContext(
            parent_projects=[
                {"project_name": "Darwin Tree of Life Project", "accession": "PRJEB40665"},
                {"project_name": "AEGIS", "accession": "PRJEB80366"},
            ],
            funding_projects=[{"project_name": "AEGIS", "accession": "PRJEB80366"}],
        )

        context.set_formatted_parent_projects()

        self.assertEqual(
            context.formatted_parent_projects,
            "Darwin Tree of Life Project (PRJEB40665) and AEGIS (PRJEB80366)",
        )
        self.assertIsNone(context.formatted_supplemental_parent_projects)

if __name__ == "__main__":
    unittest.main()
