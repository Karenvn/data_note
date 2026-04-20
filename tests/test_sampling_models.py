from __future__ import annotations

import unittest

from data_note.models import SampleMetadataRecord, SamplingInfo


class SamplingModelTests(unittest.TestCase):
    def test_sample_metadata_record_parses_prefixed_mapping(self) -> None:
        record = SampleMetadataRecord.from_mapping(
            "pacbio",
            {
                "pacbio_collector": "Alice Able",
                "pacbio_specimen_id": "SPEC-1",
                "pacbio_tolid": "ixFooBar1",
            },
        )

        self.assertEqual(record.collector, "Alice Able")
        self.assertEqual(record.specimen_id, "SPEC-1")
        self.assertEqual(record.tolid, "ixFooBar1")

    def test_sampling_info_flattens_records_back_to_legacy_context(self) -> None:
        sampling = SamplingInfo.from_legacy_dicts(
            pacbio={
                "pacbio_collector": "Alice Able",
                "pacbio_specimen_id": "SPEC-1",
            },
            hic={
                "hic_collector": "Bob Baker",
                "hic_specimen_id": "SPEC-2",
            },
        )

        context = sampling.to_context_dict()

        self.assertIsNotNone(sampling.record("pacbio"))
        self.assertIsNotNone(sampling.record("hic"))
        self.assertEqual(context["pacbio_collector"], "Alice Able")
        self.assertEqual(context["pacbio_specimen_id"], "SPEC-1")
        self.assertEqual(context["hic_collector"], "Bob Baker")
        self.assertEqual(context["hic_specimen_id"], "SPEC-2")


if __name__ == "__main__":
    unittest.main()
