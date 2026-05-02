from __future__ import annotations

import unittest

from data_note.calculate_metrics import calc_ebp_metric, evaluate_ebp_reference_standard


class EbpMetricTests(unittest.TestCase):
    def test_standard_input_passes_6_c_q40(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 2.4,
            "scaffold_N50": 12.5,
            "perc_assembled": 95.2,
            "prim_QV": 42.7,
        }

        self.assertEqual(calc_ebp_metric(context), "6.C.Q42")

        result = evaluate_ebp_reference_standard(context)

        self.assertEqual(result["ebp_reference_standard"], "6.C.Q40")
        self.assertEqual(result["ebp_reference_standard_reason"], "standard_input")
        self.assertTrue(result["ebp_reference_standard_met"])
        self.assertEqual(result["ebp_reference_standard_failures"], [])

    def test_chromosome_assignment_below_90_fails(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 10.06,
            "scaffold_N50": 24.81,
            "perc_assembled": 85.18,
            "prim_QV": 59.2,
        }

        self.assertEqual(calc_ebp_metric(context), "7.7.Q59")

        result = evaluate_ebp_reference_standard(context)

        self.assertFalse(result["ebp_reference_standard_met"])
        self.assertIn(
            "percent_assigned_to_chromosomes_below_standard",
            result["ebp_reference_standard_failures"],
        )

    def test_uli_protocol_uses_5_c_q40_standard(self) -> None:
        context = {
            "assemblies_type": "hap_asm",
            "hap1_contig_N50": 0.71,
            "hap1_scaffold_N50": 38.88,
            "hap1_perc_assembled": 99.48,
            "hap1_QV": 61.0,
            "pacbio_protocols": ["PacBio - HiFi (ULI)"],
        }

        self.assertEqual(calc_ebp_metric(context), "5.C.Q61")

        result = evaluate_ebp_reference_standard(context)

        self.assertEqual(result["ebp_reference_standard"], "5.C.Q40")
        self.assertEqual(result["ebp_reference_standard_reason"], "uli")
        self.assertTrue(result["ebp_reference_standard_met"])
        self.assertEqual(result["ebp_contig_n50_benchmark_label"], "≥ 0.1 Mb")

    def test_uli_protocol_keeps_6_c_q40_when_highest_standard_passes(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 2.4,
            "scaffold_N50": 12.5,
            "perc_assembled": 95.2,
            "prim_QV": 42.7,
            "pacbio_protocols": ["PacBio - HiFi", "PacBio - HiFi (ULI)"],
        }

        self.assertEqual(calc_ebp_metric(context), "6.C.Q42")

        result = evaluate_ebp_reference_standard(context)

        self.assertEqual(result["ebp_reference_standard"], "6.C.Q40")
        self.assertEqual(result["ebp_reference_standard_reason"], "standard_input")
        self.assertTrue(result["ebp_reference_standard_met"])
        self.assertEqual(result["ebp_contig_n50_benchmark_label"], "≥ 1 Mb")

    def test_low_contig_metric_fails_standard_input_without_uli(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 0.65,
            "scaffold_N50": 18.3,
            "perc_assembled": 99.69,
            "prim_QV": 55.3,
        }

        self.assertEqual(calc_ebp_metric(context), "5.C.Q55")

        result = evaluate_ebp_reference_standard(context)

        self.assertEqual(result["ebp_reference_standard"], "6.C.Q40")
        self.assertFalse(result["ebp_reference_standard_met"])
        self.assertIn("contig_n50_below_standard", result["ebp_reference_standard_failures"])

    def test_qv_below_40_fails(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 4.2,
            "scaffold_N50": 20.0,
            "perc_assembled": 98.0,
            "prim_QV": 39.9,
        }

        self.assertEqual(calc_ebp_metric(context), "6.C.Q39")

        result = evaluate_ebp_reference_standard(context)

        self.assertFalse(result["ebp_reference_standard_met"])
        self.assertIn("qv_below_standard", result["ebp_reference_standard_failures"])

    def test_uli_protocol_with_high_contig_n50_still_fails_against_6_c_q40_when_qv_fails(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 4.2,
            "scaffold_N50": 20.0,
            "perc_assembled": 98.0,
            "prim_QV": 39.9,
            "pacbio_protocols": ["PacBio - HiFi (ULI)"],
        }

        self.assertEqual(calc_ebp_metric(context), "6.C.Q39")

        result = evaluate_ebp_reference_standard(context)

        self.assertEqual(result["ebp_reference_standard"], "6.C.Q40")
        self.assertFalse(result["ebp_reference_standard_met"])
        self.assertIn("qv_below_standard", result["ebp_reference_standard_failures"])

    def test_missing_qv_is_unknown_not_pass(self) -> None:
        context = {
            "assemblies_type": "prim_alt",
            "contig_N50": 4.2,
            "scaffold_N50": 20.0,
            "perc_assembled": 98.0,
            "prim_QV": "",
        }

        self.assertEqual(calc_ebp_metric(context), "6.C.Q?")

        result = evaluate_ebp_reference_standard(context)

        self.assertIsNone(result["ebp_reference_standard_met"])
        self.assertEqual(result["ebp_reference_standard_status"], "unknown")
        self.assertIn("qv", result["ebp_reference_standard_missing_metrics"])


if __name__ == "__main__":
    unittest.main()
