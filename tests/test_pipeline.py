from __future__ import annotations

import unittest
from unittest.mock import Mock

from data_note.models import AssemblySelectionInput
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


if __name__ == "__main__":
    unittest.main()
