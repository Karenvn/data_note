from __future__ import annotations

import unittest

from data_note.models import BaseNoteInfo


class BaseNoteInfoTests(unittest.TestCase):
    def test_from_mapping_splits_core_fields_and_extras(self) -> None:
        info = BaseNoteInfo.from_mapping(
            {
                "bioproject": "PRJEB1",
                "study_title": "Example study",
                "tax_id": "12345",
                "child_bioprojects": ["PRJEB2"],
                "custom_flag": "keep me",
            }
        )

        self.assertEqual(info.bioproject, "PRJEB1")
        self.assertEqual(info.study_title, "Example study")
        self.assertEqual(info.tax_id, "12345")
        self.assertEqual(info.child_bioprojects, ["PRJEB2"])
        self.assertEqual(info.extras["custom_flag"], "keep me")

    def test_to_context_dict_includes_core_fields_and_extras(self) -> None:
        info = BaseNoteInfo(
            bioproject="PRJEB1",
            formatted_parent_projects="Project A (PRJEB2)",
            extras={"auto_text_error": "something went wrong"},
        )

        context = info.to_context_dict()

        self.assertEqual(context["bioproject"], "PRJEB1")
        self.assertEqual(context["formatted_parent_projects"], "Project A (PRJEB2)")
        self.assertEqual(context["auto_text_error"], "something went wrong")


if __name__ == "__main__":
    unittest.main()
