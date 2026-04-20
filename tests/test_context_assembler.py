from __future__ import annotations

import unittest

from data_note.models import (
    AnnotationInfo,
    AuthorInfo,
    AssemblyBundle,
    AssemblyRecord,
    AssemblySelection,
    NoteContext,
    NoteData,
    SequencingSummary,
    TaxonomyInfo,
)
from data_note.services.context_assembler import ContextAssembler


class ContextAssemblerTests(unittest.TestCase):
    def test_merge_accepts_typed_sections_and_plain_mappings(self) -> None:
        assembler = ContextAssembler()
        context = NoteContext(species="Example species")
        assembly_bundle = AssemblyBundle(
            selection=AssemblySelection(
                assemblies_type="prim_alt",
                primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
            )
        )
        sequencing = SequencingSummary.from_legacy_parts(
            technology_data={"pacbio": {"pacbio_sample_accession": "SAMEA1"}},
            seq_data={"PacBio": [{"read_accession": "ERR1"}]},
            totals={"pacbio_reads_millions": "12.3"},
            pacbio_protocols=["PROTO1"],
            run_accessions={"pacbio_run_accessions": "ERR1"},
        )

        merged = assembler.merge(
            context,
            {"bioproject": "PRJEB1"},
            assembly_bundle,
            sequencing,
            {"custom_key": "custom_value"},
        )

        self.assertIs(merged, context)
        self.assertEqual(merged["bioproject"], "PRJEB1")
        self.assertEqual(merged["prim_accession"], "GCA_1.1")
        self.assertEqual(merged["pacbio_reads_millions"], "12.3")
        self.assertEqual(merged["custom_key"], "custom_value")

    def test_merge_raises_for_unknown_section_type(self) -> None:
        assembler = ContextAssembler()

        with self.assertRaisesRegex(TypeError, "Cannot merge context section"):
            assembler.merge(None, object())

    def test_build_accepts_note_data_bundle(self) -> None:
        assembler = ContextAssembler()
        note_data = NoteData(
            base_context={"bioproject": "PRJEB1", "species": "Example species"},
            taxonomy=TaxonomyInfo(
                tax_id="9606",
                lineage="Eukaryota; Metazoa",
                family="Hominidae",
                common_name="human",
            ),
            assembly=AssemblyBundle(
                selection=AssemblySelection(
                    assemblies_type="prim_alt",
                    primary=AssemblyRecord(accession="GCA_1.1", assembly_name="ixExample1.1", role="primary"),
                )
            ),
            sequencing=SequencingSummary.from_legacy_parts(
                technology_data={"pacbio": {"pacbio_sample_accession": "SAMEA1"}},
                seq_data={"PacBio": [{"read_accession": "ERR1"}]},
                totals={"pacbio_reads_millions": "12.3"},
                pacbio_protocols=["PROTO1"],
                run_accessions={"pacbio_run_accessions": "ERR1"},
            ),
            annotation=AnnotationInfo(
                annot_url="https://beta.ensembl.org/species/example",
                genes="12 345",
                ensembl_source="ensembl_organisms",
            ),
            author=AuthorInfo.from_legacy_parts(
                people=[
                    {
                        "given-names": "Alice",
                        "surname": "Able",
                        "roles": [{"credit": "Resources"}],
                    }
                ],
                affiliations=[
                    {
                        "id": "1",
                        "organization": "Museum of Testing",
                        "country": "GB",
                    }
                ],
                yaml_block="author:\n  - given-names: Alice\n    surname: Able\naffiliation:\n  - id: '1'\n    organization: Museum of Testing\n    country: GB",
            ),
        )

        context = assembler.build(note_data)

        self.assertIsInstance(context, NoteContext)
        self.assertEqual(context["bioproject"], "PRJEB1")
        self.assertEqual(context["tax_id"], "9606")
        self.assertEqual(context["family"], "Hominidae")
        self.assertEqual(context["prim_accession"], "GCA_1.1")
        self.assertEqual(context["pacbio_reads_millions"], "12.3")
        self.assertEqual(context["genes"], "12 345")
        self.assertEqual(context["author_people"][0]["given-names"], "Alice")


if __name__ == "__main__":
    unittest.main()
