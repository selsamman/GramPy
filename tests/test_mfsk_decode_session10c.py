from __future__ import annotations

import unittest

import numpy as np

from grampy.text_decode import _measure_persistent_tones


class PersistentToneMeasurementTests(unittest.TestCase):
    def test_predeclared_feature_detects_nonwinning_persistent_tone(self) -> None:
        metrics = np.full((24, 16), -8.0)
        winners = np.asarray([2, 4, 6, 8] * 6)
        metrics[np.arange(24), winners] = 0.0
        metrics[:, 11] = -0.5

        measured = _measure_persistent_tones(metrics)

        self.assertFalse(np.any(measured["persistent_competitor"][:15]))
        self.assertTrue(np.all(measured["persistent_competitor"][15:]))
        self.assertEqual(measured["maximum_run_length"][-1], 24)
        self.assertEqual(measured["maximum_occupancy_fraction"][-1], 1.0)

    def test_legitimate_repeated_winner_is_not_its_own_competitor(self) -> None:
        metrics = np.full((32, 16), -8.0)
        metrics[:, 7] = 0.0

        measured = _measure_persistent_tones(metrics)

        self.assertFalse(np.any(measured["persistent_competitor"]))
        self.assertEqual(measured["maximum_run_length"][-1], 0)

    def test_adjacent_competition_is_measured_without_changing_metrics(self) -> None:
        metrics = np.full((20, 16), -8.0)
        metrics[:, 5] = 0.0
        metrics[:, 6] = -0.25
        original = metrics.copy()

        measured = _measure_persistent_tones(metrics)

        np.testing.assert_array_equal(metrics, original)
        self.assertAlmostEqual(
            measured["adjacent_competitor_gap_nats"][-1], 0.25
        )
        self.assertTrue(measured["persistent_competitor"][-1])

    def test_unknown_policy_is_rejected_at_public_boundary(self) -> None:
        from grampy.text_decode import decode_mfsk_text

        with self.assertRaisesRegex(ValueError, "persistent tone policy"):
            decode_mfsk_text(
                np.ones(48_000, dtype=np.complex64),
                input_start=0,
                sample_rate=48_000.0,
                orientation_hint="normal",
                trace_level="none",
                mode="MFSK32",
                persistent_tone_policy="unknown",
            )


if __name__ == "__main__":
    unittest.main()
