from __future__ import annotations

import os
from pathlib import Path
import unittest

import numpy as np

from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.stateful_text import (
    PictureHeaderScanner,
    plan_text_epochs,
)
from grampy.wire import (
    SoftDeinterleaver,
    convolutional_encode,
    soft_viterbi_decode,
)

from tests.suites import data_test
from tests.received_expectations import heldout_text


class RemediationR3StateTests(unittest.TestCase):
    def test_deinterleaver_checkpoint_restore_and_fill_validity(self) -> None:
        groups = [tuple(float(4 * row + lane) for lane in range(4)) for row in range(70)]
        uninterrupted = SoftDeinterleaver()
        expected = [uninterrupted.push(group) for group in groups]

        split = SoftDeinterleaver()
        actual = [split.push(group) for group in groups[:37]]
        restored = SoftDeinterleaver.restore(split.checkpoint())
        actual.extend(restored.push(group) for group in groups[37:])

        self.assertEqual(actual, expected)
        fresh = SoftDeinterleaver()
        fresh.push(groups[0])
        self.assertEqual(fresh.output_validity(), (False, False, False, True))
        for group in groups[1:31]:
            fresh.push(group)
        self.assertEqual(fresh.output_validity(), (True, True, True, True))

    def test_unknown_viterbi_start_recovers_midstream_without_invented_reset(
        self,
    ) -> None:
        bits = tuple(np.random.default_rng(8).integers(0, 2, 180).tolist())
        coded = convolutional_encode(bits, initial_state=0b1011011)
        llrs = [14.0 if bit else -14.0 for bit in coded]

        result = soft_viterbi_decode(llrs, initial_state=None)

        # Six predecessor bits are intrinsically ambiguous at an arbitrary cut;
        # the remaining committed interval is exact.
        self.assertEqual(result.bits[6:], bits[6:])

    def test_confidence_aware_header_rejects_damage_and_accepts_split_token(
        self,
    ) -> None:
        def events(text: bytes, *, confidence: float, damaged: bool = False):
            return [
                {
                    "id": f"e-{index}",
                    "octet": value,
                    "confidence": {"value": confidence},
                    "damage_flags": ["weak"] if damaged else [],
                }
                for index, value in enumerate(text)
            ]

        scanner = PictureHeaderScanner(minimum_confidence=0.25)
        accepted, rejected = scanner.push(events(b"Pic:12x", confidence=0.9))
        self.assertEqual((accepted, rejected), ([], 0))
        accepted, rejected = scanner.push(events(b"7Cp4;", confidence=0.9))
        self.assertEqual(rejected, 0)
        self.assertEqual(
            (accepted[0]["width"], accepted[0]["height"], accepted[0]["samples_per_component"]),
            (12, 7, 4),
        )

        weak = PictureHeaderScanner(minimum_confidence=0.25)
        accepted, rejected = weak.push(
            events(b"Pic:12x7Cp4;", confidence=0.1, damaged=True)
        )
        self.assertEqual(accepted, [])
        self.assertEqual(rejected, 1)

        weak_but_intact = PictureHeaderScanner(minimum_confidence=0.25)
        accepted, rejected = weak_but_intact.push(
            events(b"Pic:12x7Cp4;", confidence=0.1)
        )
        self.assertEqual(rejected, 0)
        self.assertEqual(accepted[0]["confidence"]["support"], "weak_exact_grammar")
        self.assertEqual(
            accepted[0]["confidence"]["acceptance_basis"],
            "exact_grammar_and_no_damaged_octets",
        )

    def test_sustained_dropout_creates_explicit_new_epoch(self) -> None:
        intervals = [(10_000 + 256 * i, 10_000 + 256 * (i + 1)) for i in range(100)]
        erased = [False] * 35 + [True] * 14 + [False] * 51

        epochs = plan_text_epochs(
            erased, intervals, mode="MFSK32", source="text_evidence"
        )

        self.assertEqual(len(epochs), 2)
        self.assertEqual(epochs[0]["end_reset_cause"], "sustained_signal_loss")
        self.assertEqual(epochs[1]["start_reset_cause"], "sustained_signal_loss")
        self.assertEqual(
            epochs[1]["state_assumptions"]["fec_initial_state"], "unknown"
        )
        self.assertLessEqual(
            epochs[1]["fill_warmup_interval"]["stop"],
            epochs[1]["committed_interval"]["start"],
        )
        self.assertEqual(epochs[1]["hypotheses"]["bounded_total"], 8)


class RemediationR3ReceivedTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]
    SOURCE = Path(
        os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests" / "samples")
    ) / "received-corpus" / "sources" / "wrmi-20260715T133007Z-15770000"

    @data_test("received")
    def test_received_cut_without_nearby_rsid_records_independent_epoch(self) -> None:
        meta = self.SOURCE / "capture.sigmf-meta"
        data = self.SOURCE / "capture.sigmf-data"
        if not meta.is_file() or not data.is_file():
            self.fail(
                "held-out received corpus unavailable; set GRAMPY_TEST_SAMPLES"
            )
        manifest = run_reference_pipeline(
            meta_path=meta,
            data_path=data,
            start_sample=100 * 48_000,
            stop_sample=145 * 48_000,
            config=DecodeConfig(mode="MFSK32", trace_level="summary"),
        )

        self.assertIn(heldout_text()["r3_mfsk32"], manifest["text_summary"]["text"])
        self.assertFalse(
            any(
                item.get("source") == "rsid"
                and item["interval"]["start"] >= 100 * 48_000
                for item in manifest["mode_hypotheses"]
            )
        )
        epoch = manifest["text_epochs"][0]
        self.assertEqual(
            epoch["start_evidence"], "bounded_text_evidence_without_required_rsid"
        )
        self.assertIn(
            epoch["state_assumptions"]["fec_initial_state"],
            {"known_zero_or_unknown_ranked", "unknown"},
        )
        self.assertEqual(
            manifest["diagnostics"]["text_pipeline"]["fec_evidence"][
                "startup_hypotheses"
            ][0]["assumption"],
            "known_zero",
        )


if __name__ == "__main__":
    unittest.main()
