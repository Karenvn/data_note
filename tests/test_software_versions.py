from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data_note.software_versions import (
    canonical_version_key,
    normalise_software_versions,
    parse_software_versions_file,
    read_local_software_versions,
)
from data_note.services.software_version_service import SoftwareVersionService
from data_note.tables.darwin import make_table5_rows
from data_note.tables.psyche import make_table5_rows as make_psyche_table5_rows


class SoftwareVersionTests(unittest.TestCase):
    def test_normalise_treeval_software_yaml_shape(self) -> None:
        versions = normalise_software_versions(
            {
                "BWAMEM2_MEM": {"bwa-mem2": "2.2.1"},
                "FASTK_FASTK": {"FastK": "1.1"},
                "MINIMAP2_ALIGN": {"minimap2": ["2.28", "2.28"]},
                "pipeline": [
                    {"software": "TreeVal", "version": "1.4.7"},
                    {"tool": "Nextflow", "version": "24.10.5"},
                ],
            }
        )

        self.assertEqual(versions["bwa_mem2_version"], "2.2.1")
        self.assertEqual(versions["fastk_version"], "1.1")
        self.assertEqual(versions["minimap2_version"], "2.28")
        self.assertEqual(versions["treeval_version"], "1.4.7")
        self.assertEqual(versions["nextflow_version"], "24.10.5")

    def test_reads_local_versions_from_gn_assets_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "software_versions" / "ixExample1" / "ixExample1.software_versions.yml"
            path.parent.mkdir(parents=True)
            path.write_text(
                """
TreeVal: 1.4.7
bwa-mem2: 2.2.2
genomescope_version: 2.0.1
"""
            )

            versions = read_local_software_versions("ixExample1", tmp)

        self.assertEqual(versions["treeval_version"], "1.4.7")
        self.assertEqual(versions["bwa_mem2_version"], "2.2.2")
        self.assertEqual(versions["genomescope_version"], "2.0.1")

    def test_parses_delimited_software_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "versions.tsv"
            path.write_text("software\tversion\nTreeVal\t1.4.6\nYaHS\t1.2a.2\n")

            versions = parse_software_versions_file(path)

        self.assertEqual(versions["treeval_version"], "1.4.6")
        self.assertEqual(versions["yahs_version"], "1.2a.2")

    def test_service_returns_empty_mapping_without_tolid(self) -> None:
        service = SoftwareVersionService()

        self.assertEqual(service.build_context(None), {})

    def test_table_uses_context_version_before_fallback(self) -> None:
        table = make_table5_rows({"species": "Example species", "treeval_version": "1.4.7"})

        self.assertIn("TreeVal,1.4.7", "\n".join(table["rows"]))

    def test_table_displays_fastk_release_for_commit_hash(self) -> None:
        table = make_table5_rows(
            {
                "species": "Example species",
                "fastk_version": "427104ea91c78c3b8b8b49f1a7d6bbeaa869ba1c",
            }
        )

        self.assertIn("FastK,1.1", "\n".join(table["rows"]))
        self.assertNotIn("427104ea91c78c3b8b8b49f1a7d6bbeaa869ba1c", "\n".join(table["rows"]))

    def test_merquryfk_uses_manual_module_version_not_assembly_context(self) -> None:
        context = {"species": "Example species", "merquryfk_version": "assembly-derived-hash"}

        darwin_table = make_table5_rows(context)
        psyche_table = make_psyche_table5_rows(context)

        self.assertIn("MerquryFK,1.1.0-c1", "\n".join(darwin_table["rows"]))
        self.assertIn("MerquryFK,1.1.0-c1", "\n".join(psyche_table["rows"]))
        self.assertNotIn("MerquryFK,assembly-derived-hash", "\n".join(darwin_table["rows"]))
        self.assertNotIn("MerquryFK,assembly-derived-hash", "\n".join(psyche_table["rows"]))

    def test_canonical_key_maps_known_tool_names(self) -> None:
        self.assertEqual(canonical_version_key("sanger-tol/treeval"), "treeval_version")
        self.assertEqual(canonical_version_key("merian-busco-painter"), "merian_busco_painter_version")
        self.assertEqual(canonical_version_key("MERQURY.FK"), "merquryfk_version")
        self.assertEqual(canonical_version_key("GTDB-Tk"), "gtdbtk_version")
        self.assertEqual(canonical_version_key("DAS Tool"), "dastool_version")
        self.assertEqual(canonical_version_key("MetaMDBG"), "metamdbg_version")


if __name__ == "__main__":
    unittest.main()
