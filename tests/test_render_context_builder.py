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
    BtkSummary,
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
            self.assertEqual(context["ebp_reference_standard"], "6.C.Q40")
            self.assertTrue(context["ebp_reference_standard_met"])
            self.assertEqual(tuple(context["tables"].keys()), ("table1", "table2", "table3", "table4", "table5"))

    def test_build_prefers_btk_busco_version_for_text_and_keeps_all_table_versions(self) -> None:
        builder = RenderContextBuilder()
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping(
                {
                    "bioproject": "PRJEB1",
                    "tolid": "ixExample1",
                    "assemblies_type": "prim_alt",
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
                btk=BtkSummary(
                    assemblies_type="prim_alt",
                    shared_fields={
                        "busco_version": "5.8.0",
                        "btk_busco_version": "5.8.0",
                    },
                ),
            ),
            extra_sections=[
                {
                    "busco_version": "5.7.1",
                    "local_busco_version": "5.7.1",
                }
            ],
        )

        context = builder.build(note_data, DarwinProfile())
        versions = {row[0]: row[1] for row in context["tables"]["table5"]["native_rows"]}

        self.assertEqual(context["busco_version"], "5.8.0")
        self.assertEqual(versions["BUSCO"], "5.8.0; 5.7.1")

    def test_build_applies_haploid_context_override_and_suppresses_alt_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            corrections_path = Path(tmpdir) / "corrections.json"
            corrections_path.write_text(
                json.dumps(
                    {
                        "context_overrides": {
                            "bioproject": {
                                "PRJEB70980": {
                                    "is_haploid": True,
                                }
                            }
                        }
                    }
                )
            )

            builder = RenderContextBuilder(correction_loader=load_and_apply_corrections)
            note_data = NoteData(
                base=BaseNoteInfo.from_mapping(
                    {
                        "bioproject": "PRJEB70980",
                        "tolid": "cbBryCale10",
                        "assemblies_type": "prim_alt",
                    }
                ),
                taxonomy=TaxonomyInfo(
                    tax_id="1988022",
                    species="Bryoerythrophyllum caledonicum",
                    lineage="Eukaryota; Viridiplantae",
                ),
                assembly=AssemblyBundle(
                    selection=AssemblySelection(
                        assemblies_type="prim_alt",
                        primary=AssemblyRecord(
                            accession="GCA_963971425.1",
                            assembly_name="cbBryCale10.1",
                            role="primary",
                        ),
                    ),
                    datasets=_DatasetsStub(),
                ),
            )
            note_data.quality = type(
                "_QualityStub",
                (),
                {
                    "to_context_dict": staticmethod(
                        lambda: {
                            "prim_QV": "47.0",
                            "alt_QV": "46.5",
                            "prim_kmer_completeness": "98.2",
                            "alt_kmer_completeness": "97.9",
                        }
                    )
                },
            )()

            context = builder.build(
                note_data,
                DarwinProfile(),
                corrections_file=str(corrections_path),
            )

            self.assertTrue(context["is_haploid"])
            self.assertFalse(context["has_alternate_assembly"])
            self.assertEqual(context["single_assembly_label"], "Haploid assembly")
            self.assertEqual(context["single_assembly_phrase"], "haploid genome assembly")
            self.assertTrue(context["hifiasm_primary_mode"])
            self.assertTrue(context["hifiasm_internal_purging_disabled"])
            self.assertEqual(context["hifiasm_options"], "--primary -l0")
            self.assertIn("switches off internal Hifiasm purging", context["hifiasm_options_sentence"])
            self.assertNotIn("alt_QV", context)
            self.assertNotIn("alt_kmer_completeness", context)
            self.assertEqual(context["tables"]["table2"]["native_headers"][1], "**Haploid assembly**")

    def test_build_infers_haploid_context_for_single_assembly_moss(self) -> None:
        builder = RenderContextBuilder()
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping(
                {
                    "bioproject": "PRJEB65217",
                    "tolid": "cbNecPumi1",
                    "assemblies_type": "prim_alt",
                }
            ),
            taxonomy=TaxonomyInfo(
                tax_id="3214",
                species="Neckera pumila",
                lineage="Eukaryota; Viridiplantae",
                extras={"group_name_ncbi": "mosses"},
            ),
            assembly=AssemblyBundle(
                selection=AssemblySelection(
                    assemblies_type="prim_alt",
                    primary=AssemblyRecord(
                        accession="GCA_963969595.1",
                        assembly_name="cbNecPumi1.1",
                        role="primary",
                    ),
                ),
                datasets=_DatasetsStub(),
            ),
        )
        note_data.quality = type(
            "_QualityStub",
            (),
            {
                "to_context_dict": staticmethod(
                    lambda: {
                        "prim_QV": "66.9",
                        "alt_QV": "65.1",
                        "prim_kmer_completeness": "91.13",
                        "alt_kmer_completeness": "90.42",
                    }
                )
            },
        )()

        context = builder.build(note_data, DarwinProfile())

        self.assertTrue(context["is_haploid"])
        self.assertFalse(context["has_alternate_assembly"])
        self.assertEqual(context["single_assembly_label"], "Haploid assembly")
        self.assertEqual(context["hifiasm_options"], "--primary -l0")
        self.assertNotIn("alt_QV", context)
        self.assertNotIn("alt_kmer_completeness", context)
        self.assertEqual(context["tables"]["table2"]["native_headers"][1], "**Haploid assembly**")

    def test_build_infers_haploid_context_for_single_assembly_male_hymenopteran(self) -> None:
        builder = RenderContextBuilder()
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping(
                {
                    "bioproject": "PRJEB00001",
                    "tolid": "ihExample1",
                    "assemblies_type": "prim_alt",
                    "observed_sex": "male",
                }
            ),
            taxonomy=TaxonomyInfo(
                tax_id="7399",
                species="Example hymenopteran",
                lineage="Eukaryota; Arthropoda",
                order="Hymenoptera",
            ),
            assembly=AssemblyBundle(
                selection=AssemblySelection(
                    assemblies_type="prim_alt",
                    primary=AssemblyRecord(
                        accession="GCA_000000001.1",
                        assembly_name="ihExample1.1",
                        role="primary",
                    ),
                ),
                datasets=_DatasetsStub(),
            ),
        )
        note_data.quality = type(
            "_QualityStub",
            (),
            {
                "to_context_dict": staticmethod(
                    lambda: {
                        "prim_QV": "52.0",
                        "alt_QV": "50.8",
                        "prim_kmer_completeness": "97.4",
                        "alt_kmer_completeness": "96.9",
                    }
                )
            },
        )()

        context = builder.build(note_data, DarwinProfile())

        self.assertTrue(context["is_haploid"])
        self.assertFalse(context["has_alternate_assembly"])
        self.assertEqual(context["hifiasm_options"], "--primary -l0")
        self.assertNotIn("alt_QV", context)
        self.assertEqual(context["tables"]["table2"]["native_headers"][1], "**Haploid assembly**")


if __name__ == "__main__":
    unittest.main()
