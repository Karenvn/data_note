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
        self.assertEqual(
            context["hic_specimen_reference"],
            "the Hi-C specimen (specimen ID NHMUK014438725, ToLID ilSabHarp1)",
        )
        self.assertEqual(
            context["rna_specimen_reference"],
            "the same specimen used for Hi-C sequencing (specimen ID NHMUK014438725, ToLID ilSabHarp1)",
        )


if __name__ == "__main__":
    unittest.main()
