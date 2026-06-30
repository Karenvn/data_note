from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data_note.local_metadata_provider import FileProjectProvenanceMetadataProvider
from data_note.services.project_provenance_service import ProjectProvenanceService


class ProjectProvenanceServiceTests(unittest.TestCase):
    def test_build_context_reads_file_metadata_by_tolid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            provenance_path = Path(tmpdir) / "project_provenance.yaml"
            provenance_path.write_text(
                """
tolid:
  drAstAlpi1:
    funding_projects:
      - AEGIS
    funding_statement: "Additional RNA-seq data were generated through AEGIS."
    project_provenance_source: "manual audit"
""",
                encoding="utf-8",
            )
            provider = FileProjectProvenanceMetadataProvider(provenance_path)
            service = ProjectProvenanceService(provider_factory=lambda: provider)

            context = service.build_context("PRJEB73944", tolid="drAstAlpi1", species="Astragalus alpinus")

        self.assertEqual(context["funding_projects"][0]["accession"], "PRJEB80366")
        self.assertEqual(context["formatted_funding_projects"], "AEGIS (PRJEB80366)")
        self.assertEqual(context["funding_statement"], "Additional RNA-seq data were generated through AEGIS.")
        self.assertEqual(context["project_provenance_source"], "manual audit")


if __name__ == "__main__":
    unittest.main()
