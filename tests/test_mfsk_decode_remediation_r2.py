from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from grampy.text_decode import (
    _decode_orientation,
    _observe_tracked_tones,
    detect_mfsk_comb_hypotheses,
)
from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.tracking import ClockTrack, FrequencyAnchor, FrequencyTrack


class RemediationR2Test(unittest.TestCase):
    @staticmethod
    def _mfsk_tones(
        tones: np.ndarray,
        *,
        sample_rate: float = 8_000.0,
        center_hz: float = 1_512.0,
        spacing_hz: float = 31.25,
    ) -> np.ndarray:
        samples_per_symbol = int(round(sample_rate / spacing_hz))
        result = []
        phase = 0.0
        for tone in tones:
            frequency = center_hz + (int(tone) - 7.5) * spacing_hz
            time_axis = np.arange(samples_per_symbol) / sample_rate
            result.append(
                np.exp(1j * (phase + 2 * np.pi * frequency * time_axis))
            )
            phase = (
                phase
                + 2 * np.pi * frequency * samples_per_symbol / sample_rate
            ) % (2 * np.pi)
        return np.concatenate(result).astype(np.complex64)

    def test_missing_rsid_comb_retains_both_modes_and_orientations(self) -> None:
        tones = np.random.default_rng(4).integers(0, 16, 320)
        hypotheses = detect_mfsk_comb_hypotheses(
            self._mfsk_tones(tones),
            input_start=7_000,
            sample_rate=8_000.0,
        )

        self.assertEqual(
            {(item["mode"], item["orientation"]) for item in hypotheses},
            {
                ("MFSK32", "normal"),
                ("MFSK32", "reverse"),
                ("MFSK64", "normal"),
                ("MFSK64", "reverse"),
            },
        )
        for item in hypotheses:
            self.assertEqual(item["status"], "competing")
            self.assertEqual(item["source"], "bounded-mfsk-comb")
            self.assertGreater(item["persistence_symbols"], 32)
            self.assertGreaterEqual(item["interval"]["start"], 7_000)
            self.assertGreater(item["interval"]["stop"], item["interval"]["start"])
            self.assertLess(abs(item["center_hz"] - 1_512.0), 5.0)
            self.assertGreater(item["center_uncertainty_hz"], 0.0)

    def test_auto_manifest_serializes_missing_rsid_competitors(self) -> None:
        tones = np.random.default_rng(7).integers(0, 16, 320)
        samples = self._mfsk_tones(tones)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "comb.sigmf-data"
            meta = root / "comb.sigmf-meta"
            samples.astype("<c8").tofile(data)
            meta.write_text(
                json.dumps(
                    {
                        "global": {
                            "core:datatype": "cf32_le",
                            "core:sample_rate": 8_000,
                        },
                        "captures": [{"core:sample_start": 0}],
                        "annotations": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = run_reference_pipeline(
                meta_path=meta,
                data_path=data,
                start_sample=None,
                stop_sample=None,
                config=DecodeConfig(mode="auto"),
            )

        hypotheses = manifest["mode_hypotheses"]
        self.assertEqual(
            {(item["mode"], item["orientation"]) for item in hypotheses},
            {
                ("MFSK32", "normal"),
                ("MFSK32", "reverse"),
                ("MFSK64", "normal"),
                ("MFSK64", "reverse"),
            },
        )
        self.assertTrue(
            all(item["prior"]["kind"] == "missing-rsid" for item in hypotheses)
        )
        self.assertEqual(manifest["mode_segments"], [])

    def test_single_adjacent_carrier_and_picture_sweep_are_not_text_combs(
        self,
    ) -> None:
        sample_rate = 8_000.0
        count = 82_000
        time_axis = np.arange(count) / sample_rate
        adjacent = np.exp(2j * np.pi * 2_100.0 * time_axis).astype(
            np.complex64
        )
        picture_frequency = 1_500.0 + 180.0 * np.sin(
            2 * np.pi * 0.15 * time_axis
        )
        picture_phase = 2 * np.pi * np.cumsum(picture_frequency) / sample_rate
        picture = np.exp(1j * picture_phase).astype(np.complex64)

        self.assertEqual(
            detect_mfsk_comb_hypotheses(
                adjacent, input_start=0, sample_rate=sample_rate
            ),
            [],
        )
        self.assertEqual(
            detect_mfsk_comb_hypotheses(
                picture, input_start=0, sample_rate=sample_rate
            ),
            [],
        )

    def test_tracks_drive_non_integer_intervals_and_local_oscillators(self) -> None:
        sample_rate = 8_000.0
        nominal_symbol_samples = sample_rate / 31.25
        clock = ClockTrack(
            epoch_input_sample=13.0,
            samples_per_symbol=nominal_symbol_samples,
            rate_error_ppm=1_250.0,
        )
        frequency = FrequencyTrack(
            (
                FrequencyAnchor(0, 1_450.0, 0.2, "controlled"),
                FrequencyAnchor(8_000, 1_470.0, 0.2, "controlled"),
            )
        )
        samples = np.zeros(8_000, dtype=np.complex64)
        expected_tones = []
        generated_stop = 0
        for symbol in range(30):
            start, stop = clock.interval(symbol)
            if stop > len(samples):
                break
            expected_tones.append(symbol % 16)
            midpoint = (start + stop) // 2
            tone_hz = (
                frequency.center_at(midpoint)
                + (expected_tones[-1] - 7.5) * 31.25
            )
            local_time = np.arange(stop - start) / sample_rate
            samples[start:stop] = np.exp(2j * np.pi * tone_hz * local_time)
            generated_stop = stop

        observed = _observe_tracked_tones(
            samples,
            input_start=0,
            input_stop=generated_stop,
            sample_rate=sample_rate,
            frequency_track=frequency,
            clock_track=clock,
            tone_spacing_hz=31.25,
        )

        actual = np.argmax(observed["log_metrics"], axis=1)
        self.assertEqual(actual.tolist(), expected_tones)
        self.assertTrue(
            any(
                stop - start != round(nominal_symbol_samples)
                for start, stop in observed["intervals"]
            )
        )
        np.testing.assert_allclose(
            np.logaddexp.reduce(observed["log_metrics"], axis=1),
            0.0,
            atol=1e-12,
        )
        self.assertFalse(np.any(observed["erased"]))

    def test_carrier_step_fade_and_tone_interference_are_explicit(self) -> None:
        sample_rate = 8_000.0
        clock = ClockTrack(
            epoch_input_sample=0.0,
            samples_per_symbol=256.0,
        )
        frequency = FrequencyTrack(
            (
                FrequencyAnchor(0, 1_450.0, 0.2, "controlled"),
                FrequencyAnchor(3_839, 1_450.0, 0.2, "controlled"),
                FrequencyAnchor(3_840, 1_480.0, 0.2, "controlled"),
                FrequencyAnchor(8_000, 1_480.0, 0.2, "controlled"),
            ),
            breakpoints=(3_840,),
        )
        tones = np.arange(30) % 16
        samples = np.zeros(30 * 256, dtype=np.complex64)
        for symbol, tone in enumerate(tones):
            start, stop = clock.interval(symbol)
            center = frequency.center_at((start + stop) // 2)
            tone_hz = center + (tone - 7.5) * 31.25
            time_axis = np.arange(stop - start) / sample_rate
            samples[start:stop] = np.exp(2j * np.pi * tone_hz * time_axis)
        samples[10 * 256:12 * 256] = 0.0
        start, stop = clock.interval(20)
        competing_hz = (
            frequency.center_at((start + stop) // 2)
            + ((tones[20] + 1) % 16 - 7.5) * 31.25
        )
        samples[start:stop] += np.exp(
            2j * np.pi * competing_hz * np.arange(stop - start) / sample_rate
        )

        observed = _observe_tracked_tones(
            samples,
            input_start=0,
            input_stop=len(samples),
            sample_rate=sample_rate,
            frequency_track=frequency,
            clock_track=clock,
            tone_spacing_hz=31.25,
        )

        winners = np.argmax(observed["log_metrics"], axis=1)
        reliable = ~observed["erased"]
        np.testing.assert_array_equal(winners[reliable], tones[reliable])
        self.assertTrue(observed["erased"][10])
        self.assertTrue(observed["erased"][11])
        self.assertTrue(observed["erased"][20])

    def test_flat_tone_evidence_becomes_neutral_llr_erasure(self) -> None:
        metrics = np.full((40, 16), -np.log(16.0))
        result = _decode_orientation(
            metrics,
            "normal",
            0,
            0,
            256,
            erased=np.ones(40, dtype=bool),
        )

        groups = np.asarray(result["deinterleaved_groups"])
        np.testing.assert_array_equal(groups, np.zeros_like(groups))
        self.assertTrue(all(row["erasure"] for row in result["tone_rows"]))
        self.assertTrue(
            all(
                abs(np.logaddexp.reduce(row["log_metrics"])) < 1e-12
                for row in result["tone_rows"]
            )
        )


class RemediationR2ReceivedTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]
    SOURCE = Path(
        os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests" / "samples")
    ) / "received-corpus" / "sources" / "wrmi-20260715T133007Z-15770000"

    def test_held_out_text_segments_decode_without_center_hint(self) -> None:
        meta = self.SOURCE / "capture.sigmf-meta"
        data = self.SOURCE / "capture.sigmf-data"
        if not meta.is_file() or not data.is_file():
            self.skipTest(
                "held-out received corpus unavailable; set GRAMPY_TEST_SAMPLES"
            )
        cases = (
            (
                "MFSK32",
                90 * 48_000,
                150 * 48_000,
                "Welcome to program 457 of Shortwave Radiogram.",
            ),
            (
                "MFSK64",
                350 * 48_000,
                410 * 48_000,
                "This is Shortwave Radiogram in MFSK64",
            ),
        )
        for mode, start, stop, expected in cases:
            with self.subTest(mode=mode):
                manifest = run_reference_pipeline(
                    meta_path=meta,
                    data_path=data,
                    start_sample=start,
                    stop_sample=stop,
                    config=DecodeConfig(mode=mode, trace_level="summary"),
                )
                self.assertIn(expected, manifest["text_summary"]["text"])
                segment = manifest["mode_segments"][0]
                self.assertEqual(segment["orientation"], "normal")
                self.assertGreater(segment["center_hz"], 1_545.0)
                self.assertLess(segment["center_hz"], 1_565.0)
                tones = manifest["diagnostics"]["text_pipeline"][
                    "tone_evidence"
                ]
                self.assertTrue(tones["frequency_track"]["operative"])
                self.assertTrue(tones["clock_track"]["operative"])
                self.assertEqual(
                    tones["metric"],
                    "normalized_log_matched_correlator_energy",
                )
                self.assertGreater(
                    manifest["diagnostics"]["counts"]["erasures"], 0
                )


if __name__ == "__main__":
    unittest.main()
