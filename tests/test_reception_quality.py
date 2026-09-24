"""Reception measurements use IQ power, independently of decoded text."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from grampy.reception_quality import build_reception_quality_manifest
from grampy.sigmf import SigmfRecording


RATE = 16_000


def _capture(root: Path, samples: np.ndarray) -> SigmfRecording:
    meta = root / "capture.sigmf-meta"
    data = root / "capture.sigmf-data"
    meta.write_text(json.dumps({
        "global": {"core:datatype": "cf32_le", "core:sample_rate": RATE},
        "captures": [{"core:sample_start": 0}],
    }), encoding="utf-8")
    pairs = np.column_stack((samples.real, samples.imag)).astype("<f4")
    pairs.tofile(data)
    return SigmfRecording.open(meta, data)


def _source(seconds: int) -> dict:
    return {
        "run_id": "0" * 24,
        "decoder": {"version": "test", "configuration": {"mode": "auto"}},
        "input": {
            "metadata_sha256": "a" * 64, "data_sha256": "b" * 64,
            "sample_rate_hz": RATE,
            "requested_interval": {"start": 0, "stop": seconds * RATE},
        },
        "mode_segments": [{
            "id": "mode-64", "mode": "MFSK64", "center_hz": 1500.0,
            "interval": {"start": 0, "stop": seconds * RATE},
        }],
    }


class ReceptionQualityTests(unittest.TestCase):
    def test_signal_fade_drift_noise_rise_and_quiet_interval(self) -> None:
        rng = np.random.default_rng(12345)
        seconds = 5
        count = seconds * RATE
        sample_index = np.arange(count)
        tone = rng.integers(0, 16, size=(count + 255) // 256)
        frequency = 1500 + (tone[sample_index // 256] - 7.5) * 62.5
        frequency[RATE:2 * RATE] += 80.0
        phase = 2 * np.pi * np.cumsum(frequency) / RATE
        amplitude = np.repeat([0.12, 0.12, 0.04, 0.12, 0.0], RATE)
        noise_level = np.repeat([0.01, 0.01, 0.01, 0.04, 0.01], RATE)
        noise = noise_level * (
            rng.normal(size=count) + 1j * rng.normal(size=count)
        ) / np.sqrt(2)
        samples = amplitude * np.exp(1j * phase) + noise
        with tempfile.TemporaryDirectory() as temporary:
            recording = _capture(Path(temporary), samples)
            result = build_reception_quality_manifest(recording, _source(seconds))

        self.assertEqual(result["grid"]["point_count"], seconds)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(all(point[2] is None for point in result["points"]))
        signal = [point[0] for point in result["points"]]
        noise_db = [point[1] for point in result["points"]]
        self.assertIsNotNone(signal[0])
        self.assertLess(abs(signal[1] - signal[0]), 3.0)
        self.assertLess(signal[2], signal[0] - 5.0)
        self.assertGreater(noise_db[3], noise_db[0] + 8.0)
        self.assertIsNone(signal[4])
        self.assertEqual(result["exceptions"], [])

    def test_nonfinite_iq_has_explicit_unavailable_values(self) -> None:
        samples = np.full(RATE, complex(float("nan"), 0), dtype=np.complex64)
        with tempfile.TemporaryDirectory() as temporary:
            recording = _capture(Path(temporary), samples)
            result = build_reception_quality_manifest(recording, _source(1))
        self.assertEqual(result["points"], [[None, None, None]])
        self.assertEqual(result["exceptions"], [{"index": 0, "reason": "invalid_spectrum"}])


if __name__ == "__main__":
    unittest.main()
