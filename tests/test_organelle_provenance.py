from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data_note.organelle_provenance import (
    normalise_organelle_provenance,
    parse_organelle_provenance_file,
    read_local_organelle_provenance,
)
from data_note.services.organelle_provenance_service import OrganelleProvenanceService


class OrganelleProvenanceTests(unittest.TestCase):
    def test_normalise_flat_mitohifi_reference_fields(self) -> None:
        context = normalise_organelle_provenance(
            {
                "mitohifi_reference_accession": "NC_072246.1",
                "mitohifi_reference_organism": "Pseudeustrotia carneola",
                "unrelated": "ignored",
            }
        )

        self.assertEqual(context["mitohifi_reference_accession"], "NC_072246.1")
        self.assertEqual(context["mitohifi_reference_organism"], "Pseudeustrotia carneola")
        self.assertEqual(context["mitohifi_reference_text"], "Pseudeustrotia carneola (NC_072246.1)")
        self.assertNotIn("unrelated", context)

    def test_normalise_nested_mitohifi_reference(self) -> None:
        context = normalise_organelle_provenance(
            {
                "mitohifi_reference": {
                    "accession": "NC_072246.1",
                    "organism": "Pseudeustrotia carneola",
                    "selection_taxa": ["Acontia lucida", "Acontia", "Acontiinae"],
                }
            }
        )

        self.assertEqual(context["mitohifi_reference_accession"], "NC_072246.1")
        self.assertEqual(context["mitohifi_reference_selection_taxa"], "Acontia lucida; Acontia; Acontiinae")

    def test_normalise_derives_mito_reference_from_legacy_fields(self) -> None:
        context = normalise_organelle_provenance(
            {
                "mitohifi_reference_accession": "NC_058734.1",
                "mitohifi_reference_definition": "Salix dunnii mitochondrion, complete genome.",
                "mitohifi_reference_file": (
                    "/lustre/species/working/ddHypPulc1.hifiasm/oatk/mito/"
                    "ddHypPulc1.oatk.mito.mitohifi/NC_058734.1.gb"
                ),
                "mitohifi_reference_organism": "Salix dunnii",
                "mitohifi_reference_source": "mitochondrion Salix dunnii",
            }
        )

        self.assertEqual(context["mito_reference_accession"], "NC_058734.1")
        self.assertEqual(context["mito_reference_organism"], "Salix dunnii")
        self.assertEqual(context["mito_reference_organelle_label"], "mitochondrial genome")
        self.assertNotIn("plastid_reference_accession", context)

    def test_normalise_derives_plastid_reference_from_oatk_pltd_path(self) -> None:
        context = normalise_organelle_provenance(
            {
                "mitohifi_reference_accession": "NC_082245.1",
                "mitohifi_reference_definition": "Fallopia convolvulus chloroplast, complete genome.",
                "mitohifi_reference_file": (
                    "/lustre/species/working/dcFalConv1.hifiasm/oatk/pltd/"
                    "dcFalConv1.oatk.pltd.mitohifi/NC_082245.1.gb"
                ),
                "mitohifi_reference_organism": "Fallopia convolvulus",
                "mitohifi_reference_source": "chloroplast Fallopia convolvulus",
                "mitohifi_reference_source_file": (
                    "/lustre/species/working/dcFalConv1.hifiasm/oatk/pltd/"
                    "dcFalConv1.oatk.pltd.mitohifi/findMitoReference.log"
                ),
            }
        )

        self.assertEqual(context["plastid_reference_accession"], "NC_082245.1")
        self.assertEqual(context["plastid_reference_organism"], "Fallopia convolvulus")
        self.assertEqual(context["plastid_reference_organelle_label"], "chloroplast genome")
        self.assertNotIn("mito_reference_accession", context)

    def test_normalise_accepts_nested_mito_and_plastid_references(self) -> None:
        context = normalise_organelle_provenance(
            {
                "mito_reference": {
                    "accession": "NC_000001.1",
                    "organism": "Example mitochondrion",
                    "definition": "Example mitochondrion, complete genome.",
                },
                "pltd_reference": {
                    "accession": "NC_000002.1",
                    "organism": "Example plastid",
                    "definition": "Example chloroplast, complete genome.",
                },
            }
        )

        self.assertEqual(context["mito_reference_text"], "Example mitochondrion (NC_000001.1)")
        self.assertEqual(context["plastid_reference_text"], "Example plastid (NC_000002.1)")
        self.assertEqual(context["plastid_reference_organelle_label"], "chloroplast genome")

    def test_reads_local_provenance_from_gn_assets_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "organelle_provenance" / "ilAcoLuci2" / "ilAcoLuci2.organelle_provenance.yml"
            path.parent.mkdir(parents=True)
            path.write_text(
                """
mitohifi_reference_accession: NC_072246.1
mitohifi_reference_organism: Pseudeustrotia carneola
mitohifi_reference_definition: Pseudeustrotia carneola mitochondrion, complete genome.
"""
            )

            context = read_local_organelle_provenance("ilAcoLuci2", tmp)

        self.assertEqual(context["mitohifi_reference_accession"], "NC_072246.1")
        self.assertEqual(context["mitohifi_reference_organism"], "Pseudeustrotia carneola")

    def test_parses_tsv_provenance_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "organelle.tsv"
            path.write_text("field\tvalue\nmitohifi_reference_accession\tNC_072246.1\n")

            context = parse_organelle_provenance_file(path)

        self.assertEqual(context["mitohifi_reference_accession"], "NC_072246.1")
        self.assertEqual(context["mitohifi_reference_text"], "NC_072246.1")

    def test_service_returns_empty_mapping_without_tolid(self) -> None:
        service = OrganelleProvenanceService()

        self.assertEqual(service.build_context(None), {})


if __name__ == "__main__":
    unittest.main()
