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

    def test_apply_known_tolid_fix(self) -> None:
        context = NoteContext()
        context["prim_accession"] = "GCA_945910005.1"
        context.apply_known_tolid_fix({"GCA_945910005.1": "ipIsoGram3"})
        self.assertEqual(context.tolid, "ipIsoGram3")


if __name__ == "__main__":
    unittest.main()
