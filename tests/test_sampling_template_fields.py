from __future__ import annotations

import unittest

from data_note.sampling_template_fields import populate_sampling_template_fields


class SamplingTemplateFieldsTests(unittest.TestCase):
    def test_formats_collectors_and_affiliations_for_template_use(self) -> None:
        context = {
            "pacbio_collector": "Mark Sterling | David Lees",
            "pacbio_collector_institute": "Natural History Museum | Natural History Museum",
            "pacbio_identifier": "Mark Sterling",
            "pacbio_identifier_affiliation": "Natural History Museum",
        }

        populate_sampling_template_fields(context)

        self.assertEqual(context["pacbio_collector_text"], "Mark Sterling and David Lees")
        self.assertEqual(context["pacbio_collector_institute_text"], "Natural History Museum")
        self.assertEqual(
            context["pacbio_collector_display"],
            "Mark Sterling and David Lees (Natural History Museum)",
        )
        self.assertEqual(
            context["pacbio_identifier_display"],
            "Mark Sterling (Natural History Museum)",
        )
        self.assertEqual(context["pacbio_coll_institute"], "Natural History Museum")

    def test_derives_relationship_aware_specimen_references(self) -> None:
        context = {
            "pacbio_sample_accession": "SAMEA112975585",
            "pacbio_sample_derived_from": "SAMEA112964414",
            "pacbio_specimen_id": "NHMUK014438727",
            "pacbio_tolid": "ilSabHarp2",
            "hic_sample_accession": "SAMEA112975583",
            "hic_sample_derived_from": "SAMEA112964413",
            "hic_specimen_id": "NHMUK014438725",
            "hic_tolid": "ilSabHarp1",
            "rna_sample_accession": "SAMEA112975583",
            "rna_sample_derived_from": "SAMEA112964413",
            "rna_specimen_id": "NHMUK014438725",
            "rna_tolid": "ilSabHarp1",
        }

        populate_sampling_template_fields(context)

        self.assertTrue(context["hic_differs_from_pacbio"])
        self.assertFalse(context["hic_same_as_pacbio"])
        self.assertFalse(context["rna_same_as_pacbio"])
        self.assertTrue(context["rna_same_as_hic"])
        self.assertEqual(
            context["pacbio_specimen_label"],
            "specimen ID NHMUK014438727, ToLID ilSabHarp2",
        )
        self.assertEqual(context["pacbio_specimen_short_label"], "ilSabHarp2 specimen")
        self.assertEqual(context["pacbio_specimen_short_reference"], "the ilSabHarp2 specimen")
        self.assertEqual(
            context["pacbio_specimen_short_sentence_reference"],
            "The ilSabHarp2 specimen",
        )
        self.assertEqual(
            context["hic_specimen_reference"],
            "the Hi-C specimen (specimen ID NHMUK014438725, ToLID ilSabHarp1)",
        )
        self.assertEqual(context["hic_specimen_short_reference"], "the ilSabHarp1 specimen")
        self.assertEqual(
            context["rna_specimen_reference"],
            "the same specimen used for Hi-C sequencing (specimen ID NHMUK014438725, ToLID ilSabHarp1)",
        )
        self.assertEqual(context["rna_specimen_short_reference"], "the ilSabHarp1 specimen")
        self.assertEqual(
            context["rna_specimen_short_sentence_reference"],
            "The ilSabHarp1 specimen",
        )

    def test_short_reference_prefers_related_tolid_over_biosample_only_label(self) -> None:
        context = {
            "pacbio_sample_accession": "SAMEA112975585",
            "pacbio_specimen_id": "NHMUK014438727",
            "pacbio_tolid": "ilSabHarp2",
            "rna_sample_accession": "SAMEA112975585",
        }

        populate_sampling_template_fields(context)

        self.assertTrue(context["rna_same_as_pacbio"])
        self.assertEqual(context["rna_specimen_short_label"], "ilSabHarp2 specimen")
        self.assertEqual(context["rna_specimen_short_reference"], "the ilSabHarp2 specimen")

    def test_formats_coordinates_and_detects_shared_collection_event(self) -> None:
        context = {
            "pacbio_coll_location": "Trefor, Gwyneth, UK",
            "pacbio_coll_date": "2022-08-08",
            "pacbio_coll_lat": "52.9871",
            "pacbio_coll_long": "-4.4362",
            "hic_coll_location": "Trefor, Gwyneth, United Kingdom",
            "hic_coll_date": "2022-08-08",
            "hic_coll_lat": "52.9871",
            "hic_coll_long": "--4.4362",
            "rna_coll_location": "Elsewhere",
            "rna_coll_date": "2022-08-09",
            "rna_coll_lat": "51.0",
            "rna_coll_long": "-1.0",
        }

        populate_sampling_template_fields(context)

        self.assertEqual(context["pacbio_coll_long_display"], "\u22124.4362")
        self.assertEqual(context["hic_coll_long_display"], "\u22124.4362")
        self.assertTrue(context["hic_collection_same_as_pacbio"])
        self.assertFalse(context["rna_collection_same_as_hic"])

    def test_formats_organism_part_as_tissue_phrase(self) -> None:
        context = {
            "pacbio_organism_part": "leaf",
            "hic_organism_part": "head and thorax",
            "rna_organism_part": "muscle tissue",
            "isoseq_organism_part": "NOT_COLLECTED",
        }

        populate_sampling_template_fields(context)

        self.assertEqual(context["pacbio_tissue_phrase"], "leaf tissue")
        self.assertEqual(context["hic_tissue_phrase"], "head and thorax tissue")
        self.assertEqual(context["rna_tissue_phrase"], "muscle tissue")
        self.assertEqual(context["isoseq_tissue_phrase"], "tissue")


if __name__ == "__main__":
    unittest.main()
