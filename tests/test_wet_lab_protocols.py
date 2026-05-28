from __future__ import annotations

import unittest

from data_note.models import BaseNoteInfo, NoteData
from data_note.services.render_context_builder import RenderContextBuilder
from data_note.wet_lab_protocols import (
    COLLECTION_VERSION,
    WET_LAB_PROTOCOLS,
    all_wet_lab_protocols,
    build_wet_lab_protocol_context,
)


class WetLabProtocolMappingTests(unittest.TestCase):
    def test_catalog_contains_published_collection_v3_protocols(self) -> None:
        context = build_wet_lab_protocol_context({})

        self.assertEqual(COLLECTION_VERSION, 3)
        self.assertEqual(len(WET_LAB_PROTOCOLS), 38)
        self.assertEqual(len(context["wet_lab_protocol_catalog"]), 38)
        self.assertEqual(len(all_wet_lab_protocols("extraction")), 23)
        self.assertIn("8epv5xxy6g1b/v3", context["wet_lab_protocol_collection"]["url"])

    def test_maps_common_non_plant_metadata_to_reviewable_protocols(self) -> None:
        context = build_wet_lab_protocol_context(
            {
                "extraction_protocol": "MagAttract Standard 48xrn",
                "disruption_method": "Powermash",
                "spri_type": "1x ProNex (manual)",
                "pacbio_protocols": ["PacBio - HiFi (ULI)"],
            }
        )

        self.assertEqual(context["homogenisation_protocol"]["key"], "homogenisation_powermash")
        self.assertEqual(context["extraction_protocol_match"]["key"], "extraction_automated_magattract_v2")
        self.assertTrue(context["extraction_protocol_match"]["review_required"])
        self.assertEqual(context["cleanup_protocol"]["key"], "cleanup_manual_spri")
        self.assertEqual(context["fragmentation_protocol"]["key"], "fragmentation_covaris_gtube_uli_pacbio")
        self.assertTrue(context["wet_lab_protocol_review_required"])
        self.assertIn("Wet lab protocol editor note", context["wet_lab_protocol_editor_comment"])
        self.assertIn("Published protocol catalog", context["wet_lab_protocol_editor_comment"])
        self.assertIn("MagAttract Standard 48xrn", context["wet_lab_protocol_editor_comment"])

    def test_maps_plant_magattract_version_and_cryo_disruption(self) -> None:
        context = build_wet_lab_protocol_context(
            {
                "extraction_protocol": "Plant MagAttract 48xrn v4",
                "extraction_mode": "Automatic",
                "disruption_method": "Covaris cryoPREP",
                "spri_type": "0.45x AMPure PB (auto KF)",
                "pacbio_protocols": ["PacBio - HiFi"],
            }
        )

        self.assertEqual(context["homogenisation_protocol"]["key"], "homogenisation_covaris_cryoprep")
        self.assertEqual(context["extraction_protocol_match"]["key"], "extraction_automated_plant_magattract_v4")
        self.assertEqual(context["cleanup_protocol"]["key"], "cleanup_automated_spri")
        self.assertEqual(context["fragmentation_protocol"]["key"], "fragmentation_megaruptor_li_pacbio")

    def test_maps_apex_spri_type_to_automated_cleanup(self) -> None:
        context = build_wet_lab_protocol_context({"spri_type": "Apex"})

        self.assertEqual(context["cleanup_protocol"]["key"], "cleanup_automated_spri")

    def test_keeps_unknown_protocols_for_manual_review_without_guessing(self) -> None:
        context = build_wet_lab_protocol_context({"extraction_protocol": "Unpublished bench protocol"})

        self.assertIsNone(context["extraction_protocol_match"])
        self.assertEqual(context["extraction_protocol_candidates"], [])
        self.assertTrue(context["wet_lab_protocol_review_required"])
        self.assertIn("No wet lab extraction protocol mapping", context["wet_lab_protocol_review_note"])

    def test_render_context_builder_adds_protocol_catalog_and_matches(self) -> None:
        builder = RenderContextBuilder()
        note_data = NoteData(
            base=BaseNoteInfo.from_mapping(
                {
                    "bioproject": "PRJEB1",
                    "tolid": "ixExample1",
                    "assemblies_type": "prim_alt",
                    "extraction_protocol": "Manual MagAttract v3",
                    "disruption_method": "FastPrep-96 bead beating",
                }
            )
        )

        context = builder.derive_note_fields(note_data)
        self.assertNotIn("wet_lab_protocol_catalog", context)

        built = builder.build(note_data, profile=_NoTableProfile())

        self.assertEqual(len(built["wet_lab_protocol_catalog"]), 38)
        self.assertEqual(built["extraction_protocol_match"]["key"], "extraction_manual_magattract_v3")
        self.assertEqual(built["homogenisation_protocol"]["key"], "homogenisation_cryogenic_bead_beating")


class _NoTableProfile:
    def build_tables(self, context):
        return context


if __name__ == "__main__":
    unittest.main()
