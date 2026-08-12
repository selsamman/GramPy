from __future__ import annotations

import unittest

import numpy as np

from grampy.picture_decode import decode_pictures
from grampy.tracking import FrequencyAnchor, FrequencyTrack


def _event(
    index: int,
    value: int,
    recognized: int,
    *,
    sample_rate: float,
    prologue_start: float,
) -> dict:
    result = {
        "id": f"text-{index:04d}",
        "octet": value,
        "wire_interval": {"start": index * 10, "stop": index * 10 + 10},
        "recognized_at_input_sample": recognized,
        "confidence": {"value": 1.0},
        "damage_flags": [],
    }
    if recognized:
        symbol_samples = sample_rate / 62.5
        result["provenance"] = {
            "decoded_bit_interval": {"start": 99, "stop": 100},
            "recognized_symbol": 0,
            "transition_crossover_clock": {
                "status": "estimated",
                "epoch_input_sample": prologue_start - 60 * symbol_samples,
                "nominal_symbol_samples": symbol_samples,
                "estimated_rate_error_ppm": 0.0,
                "phase_uncertainty_input_samples": 0.25,
                "parameter_covariance": [[0.04, 0.0], [0.0, 1e-8]],
                "residual_sigma_input_samples": 0.25,
                "operative": False,
            },
        }
    return result


class RemediationR4PictureEvidenceTests(unittest.TestCase):
    def test_fractional_p2_p4_p8_clock_and_ranked_boundaries(self) -> None:
        rate = 44_100
        center = 1500.0
        bandwidth = 937.5
        expected = np.asarray([16, 63, 129, 240], dtype=np.uint8)
        for speed in (2, 4, 8):
            with self.subTest(speed=speed):
                recognized = 4410
                prologue_start = recognized + round(0.965 * rate)
                prologue_count = round(352 * rate / 8000.0)
                raster_start = prologue_start + prologue_count
                scale = speed * rate / 8000.0
                raster_stop = round(raster_start + len(expected) * scale)
                frequencies = np.full(
                    raster_stop + round(1.440 * rate), center, dtype=np.float64
                )
                frequencies[prologue_start:raster_start] = center - bandwidth / 2
                for component, value in enumerate(expected):
                    start = round(raster_start + component * scale)
                    stop = round(raster_start + (component + 1) * scale)
                    frequencies[start:stop] = (
                        center + bandwidth * (int(value) - 128) / 256
                    )
                phase = 2 * np.pi * np.cumsum(frequencies) / rate
                samples = np.exp(1j * phase).astype(np.complex64)
                header = f"Pic:4x1p{speed};".encode()
                decoded = decode_pictures(
                    samples,
                    input_start=0,
                    sample_rate=rate,
                    mode="MFSK64",
                    orientation="normal",
                    center_hz=center,
                    text_events=[
                        _event(
                            index,
                            value,
                            recognized if index == len(header) - 1 else 0,
                            sample_rate=rate,
                            prologue_start=prologue_start,
                        )
                        for index, value in enumerate(header)
                    ],
                )
                picture = decoded.pictures[0]
                actual = decoded.artifacts[0]["values"]
                self.assertTrue(picture["complete"])
                self.assertEqual(
                    picture["completion_reason"], "expected_component_count"
                )
                self.assertAlmostEqual(
                    picture["component_clock"]["nominal_samples_per_component"],
                    scale,
                )
                self.assertGreaterEqual(len(picture["start_alternatives"]), 2)
                self.assertEqual(
                    sum(item["selected"] for item in picture["start_alternatives"]),
                    1,
                )
                self.assertEqual(
                    sum(item["selected"] for item in picture["end_alternatives"]),
                    1,
                )
                self.assertLessEqual(
                    max(abs(left - right) for left, right in zip(actual, expected)),
                    3,
                )
                self.assertIn("damage_summary", picture)

    def test_offset_drift_step_and_content_bias_matrix(self) -> None:
        rate = 48_000
        center = 1500.0
        bandwidth = 937.5
        rate_error_ppm = 1_000.0
        expected = np.asarray(
            [24] * 8 + [224] * 8 + [64, 192] * 8,
            dtype=np.uint8,
        )
        for speed in (2, 4, 8):
            with self.subTest(speed=speed):
                recognized = 4800
                nominal_prologue = recognized + round(0.965 * rate)
                prologue_start = nominal_prologue + 24
                prologue_count = round(352 * rate / 8000.0)
                raster_start = prologue_start + prologue_count
                nominal_scale = speed * rate / 8000.0
                tracked_scale = nominal_scale * (1.0 + rate_error_ppm * 1e-6)
                raster_stop = round(raster_start + len(expected) * tracked_scale)
                step_sample = round(
                    raster_start + len(expected) * tracked_scale / 2
                )
                track = FrequencyTrack(
                    (
                        FrequencyAnchor(0, center, 0.5, "controlled"),
                        FrequencyAnchor(step_sample - 1, center, 0.5, "controlled"),
                        FrequencyAnchor(step_sample, center + 8.0, 0.5, "controlled"),
                        FrequencyAnchor(
                            raster_stop + round(1.440 * rate),
                            center + 8.0,
                            0.5,
                            "controlled",
                        ),
                    ),
                    breakpoints=(step_sample,),
                )
                positions = np.arange(raster_stop + round(1.440 * rate))
                frequencies = np.asarray(track.center_at(positions))
                frequencies[prologue_start:raster_start] -= bandwidth / 2
                for component, value in enumerate(expected):
                    start = round(raster_start + component * tracked_scale)
                    stop = round(raster_start + (component + 1) * tracked_scale)
                    frequencies[start:stop] += (
                        bandwidth * (int(value) - 128) / 256
                    )
                phase = 2 * np.pi * np.cumsum(frequencies) / rate
                header = f"Pic:{len(expected)}x1p{speed};".encode()
                decoded = decode_pictures(
                    np.exp(1j * phase).astype(np.complex64),
                    input_start=0,
                    sample_rate=rate,
                    mode="MFSK64",
                    orientation="normal",
                    center_hz=center,
                    frequency_track=track,
                    component_rate_error_ppm=rate_error_ppm,
                    text_events=[
                        _event(
                            index,
                            value,
                            recognized if index == len(header) - 1 else 0,
                            sample_rate=rate,
                            prologue_start=prologue_start,
                        )
                        for index, value in enumerate(header)
                    ],
                )
                picture = decoded.pictures[0]
                actual = decoded.artifacts[0]["values"]
                self.assertTrue(picture["complete"])
                self.assertEqual(
                    picture["component_clock"]["rate_error_ppm"],
                    rate_error_ppm,
                )
                self.assertEqual(
                    picture["carrier_track_assumption"]["track"]["breakpoints"],
                    [step_sample],
                )
                self.assertLessEqual(
                    max(
                        abs(int(left) - int(right))
                        for left, right in zip(actual, expected)
                    ),
                    4,
                    actual,
                )


if __name__ == "__main__":
    unittest.main()
