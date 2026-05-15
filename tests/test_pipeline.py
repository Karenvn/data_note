from __future__ import annotations

import unittest
from unittest.mock import Mock

from data_note.models import AssemblySelectionInput, BaseNoteInfo, NoteData
from data_note.orchestrator import ProcessedGenomeNote
from data_note.pipeline import DataNotePipeline


class PipelineTests(unittest.TestCase):
    def test_run_rejects_assembly_override_for_bioproject_list(self) -> None:
        config = Mock()
        config.assembly_selection_input.return_value = AssemblySelectionInput(
            assembly_accession="GCA_123456789.1"
        )
        pipeline = DataNotePipeline(config=config)
        pipeline._orchestrator = Mock()
        pipeline._orchestrator.read_bioproject_input.return_value = ["PRJEB12345", "PRJEB67890"]

        with self.assertRaises(ValueError):
            pipeline.run("bioprojects.txt", "template.md")

    def test_run_writes_context_csv_and_json_after_note_generation(self) -> None:
        config = Mock()
        config.assembly_selection_input.return_value = None
        pipeline = DataNotePipeline(config=config)
        pipeline._orchestrator = Mock()
        pipeline._orchestrator.read_bioproject_input.return_value = ["PRJEB12345"]
        note_data = NoteData(base=BaseNoteInfo(bioproject="PRJEB12345"))
        context = {"assemblies_type": "prim_alt", "species": "Example species"}
        pipeline._orchestrator.process_bioproject_result.return_value = ProcessedGenomeNote(
            context=context,
            note_data=note_data,
        )
        pipeline._orchestrator.write_note.return_value = "/tmp/Example_species"

        result = pipeline.run("PRJEB12345", "template.md")

        self.assertEqual(result, 0)
        pipeline._orchestrator.write_context_csv.assert_called_once_with(
            context,
            "/tmp/Example_species/PRJEB12345_context.csv",
        )
        pipeline._orchestrator.write_context_json.assert_called_once_with(
            context,
            "/tmp/Example_species/PRJEB12345_context.json",
        )
        pipeline._orchestrator.write_note_data_json.assert_called_once_with(
            note_data,
            "/tmp/Example_species/PRJEB12345_note_data.json",
        )


if __name__ == "__main__":
    unittest.main()
