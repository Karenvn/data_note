from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from data_note.models import FlowCytometryInfo
from data_note.services.flow_cytometry_service import FlowCytometryService


class FlowCytometryServiceTests(unittest.TestCase):
    def test_build_context_returns_none_when_file_is_missing(self) -> None:
        service = FlowCytometryService(tsv_path=Path("/tmp/does-not-exist-cyto.tsv"))
        self.assertIsNone(service.build_context("Example species"))

    def test_build_context_prefers_dtol_match_for_species(self) -> None:
        tsv_content = (
            "Project\tGenus\tSpecies \tStandard\tBuffer\tGS pg (1C)\t1C/Gbp\tDToL Specimen ID\n"
            "UK Flora\tSchoenoplectus\ttriqueter\t<Petro\tGPB3%PVPBmet\t0.71\t0.69\t\n"
            "DTOL\tSchoenoplectus\ttriqueter\t<Petro\tGPB3%PVPBmet\t0.73\t0.71\tKDTOL10283\n"
        )
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cyto_info.tsv"
            path.write_text(tsv_content)
            service = FlowCytometryService(tsv_path=path)

            result = service.build_context("Schoenoplectus triqueter")

        self.assertIsInstance(result, FlowCytometryInfo)
        assert result is not None
        self.assertEqual(result.flow_pg, 0.73)
        self.assertEqual(result.flow_mb, "710.00")
        self.assertEqual(result.flow_project, "DTOL")
        self.assertEqual(result.flow_dtol_specimen_id, "KDTOL10283")
        self.assertIn("beta-mercaptoethanol", result.buffer_desc)
        self.assertIn("Petroselinum crispum", result.standard_desc)

    def test_build_context_falls_back_to_non_dtol_match(self) -> None:
        tsv_content = (
            "Project\tGenus\tSpecies \tStandard\tBuffer\tGS pg (1C)\t1C/Gbp\tDToL Specimen ID\n"
            "UK Flora\tBlysmus\tcompressus\t>Solanum\tGPB3%PVPBmet\t2.01\t1.97\t\n"
        )
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cyto_info.tsv"
            path.write_text(tsv_content)
            service = FlowCytometryService(tsv_path=path)

            result = service.build_context("Blysmus compressus")

        self.assertIsInstance(result, FlowCytometryInfo)
        assert result is not None
        self.assertEqual(result.flow_pg, 2.01)
        self.assertEqual(result.flow_project, "UK Flora")


if __name__ == "__main__":
    unittest.main()
