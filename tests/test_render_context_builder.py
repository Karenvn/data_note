from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from data_note.io_utils import load_and_apply_corrections
from data_note.models import (
    AssemblyBundle,
    AssemblyRecord,
    AssemblySelection,
    BaseNoteInfo,
    NoteContext,
    NoteData,
    SequencingSummary,
    TaxonomyInfo,
)
from data_note.profiles import DarwinProfile
from data_note.services.render_context_builder import RenderContextBuilder


class _DatasetsStub:
    def to_context_dict(self) -> dict[str, object]:
        return {
            "assembly_level": "chromosome",
            "contig_N50": 2.5,
            "scaffold_N50": 10.0,
            "perc_assembled": 95.0,
            "prim_QV": 47.0,
            "total_length": "512.3",
            "chromosome_count": "12",
            "num_contigs": "34",
            "num_scaffolds": "20",
            "length_mito_kb": "16.4",
        }


class RenderContextBuilderTests(unittest.TestCase):
    def test_derive_note_fields_updates_parent_projects_and_tolid(self) -> None:
        builder = RenderContextBuilder()
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping(
                {
                    "bioproject": "PRJEB1",
                    "parent_projects": [
                        {"project_name": "Parent One", "accession": "PRJEB10"},
                        {"project_name": "Parent Two", "accession": "PRJEB11"},
                    ],
                }
            ),
            assembly=AssemblyBundle(
                selection=AssemblySelection(
                    assemblies_type="prim_alt",
                    primary=AssemblyRecord(
                        accession="GCA_1.1",
                        assembly_name="ixExample1.1",
                        role="primary",
                    ),
                )
            ),
        )

        context = builder.derive_note_fields(note_data)

        self.assertEqual(context.formatted_parent_projects, "Parent One (PRJEB10) and Parent Two (PRJEB11)")
        self.assertEqual(context.tolid, "ixExample1")
        self.assertEqual(note_data.base.formatted_parent_projects, "Parent One (PRJEB10) and Parent Two (PRJEB11)")
        self.assertEqual(note_data.base.tolid, "ixExample1")

    def test_build_applies_corrections_metric_and_profile_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            corrections_path = Path(tmpdir) / "corrections.json"
            corrections_path.write_text(
                json.dumps(
                    {
                        "specific_replacements": {"species": {"Example species": "Corrected species"}},
                        "generic_replacements": {"automatic": "automated"},
                    }
                )
            )

            builder = RenderContextBuilder(correction_loader=load_and_apply_corrections)
            note_data = NoteData(
                base=BaseNoteInfo.from_mapping(
                    {
                        "bioproject": "PRJEB1",
                        "tolid": "ixExample1",
                        "assemblies_type": "prim_alt",
                        "auto_text": "Example automatic summary.",
                    }
                ),
                taxonomy=TaxonomyInfo(
                    tax_id="9606",
                    species="Example species",
                    lineage="Eukaryota; Metazoa",
                ),
                assembly=AssemblyBundle(
                    selection=AssemblySelection(
                        assemblies_type="prim_alt",
                        primary=AssemblyRecord(
                            accession="GCA_1.1",
                            assembly_name="ixExample1.1",
                            role="primary",
                        ),
                    ),
                    datasets=_DatasetsStub(),
                ),
                sequencing=SequencingSummary.from_legacy_parts(
                    technology_data={"pacbio": {"pacbio_sample_accession": "SAMEA1"}},
                    seq_data={"PacBio": [{"read_accession": "ERR1"}]},
                    totals={"pacbio_reads_millions": "12.3"},
                    pacbio_protocols=["PROTO1"],
                    run_accessions={"pacbio_run_accessions": "ERR1"},
                ),
            )

            context = builder.build(
                note_data,
                DarwinProfile(),
                corrections_file=str(corrections_path),
            )

            self.assertIsInstance(context, NoteContext)
            self.assertEqual(context["species"], "Corrected species")
            self.assertEqual(context["auto_text"], "Example automated summary.")
            self.assertEqual(context["ebp_metric"], "6.C.Q47")
            self.assertEqual(tuple(context["tables"].keys()), ("table1", "table2", "table3", "table4", "table5"))


if __name__ == "__main__":
    unittest.main()
