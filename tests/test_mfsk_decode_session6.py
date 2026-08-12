from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

import numpy as np

from grampy.picture_decode import decode_pictures, parse_picture_headers
from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.tracking import FrequencyAnchor, FrequencyTrack


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json").read_text(encoding="utf-8")
)
FIXTURE_ROOT = Path(
    os.environ.get("GRAM_PY_MFSK_FIXTURES", ROOT / ".local" / "fldigi-fixtures")
)


def event(index: int, value: int, recognized: int = 0) -> dict:
    result = {
        "id": f"text-{index:04d}",
        "octet": value,
        "wire_interval": {"start": index * 10, "stop": index * 10 + 10},
        "recognized_at_input_sample": recognized,
        "confidence": {"value": 1.0},
    }
    if recognized:
        symbol_samples = 48_000.0 / 62.5
        prologue_start = recognized + round(0.965 * 48_000)
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


class PictureHeaderTests(unittest.TestCase):
    def test_accepts_all_wire_forms_and_rejects_invalid_values(self) -> None:
        payload = (
            b"Pic:1x4095; Pic:8x4C; Pic:2x3p2; Pic:4x5Cp4;"
            b" Pic:0x4; Pic:8x4p3;"
        )
        headers, rejected = parse_picture_headers(
            [event(index, value) for index, value in enumerate(payload)]
        )
        self.assertEqual(
            [
                (item["width"], item["height"], item["color"], item["samples_per_component"])
                for item in headers
            ],
            [
                (1, 4095, False, 8),
                (8, 4, True, 8),
                (2, 3, False, 2),
                (4, 5, True, 4),
            ],
        )
        self.assertEqual(rejected, 2)

    def test_p2_p4_p8_component_clock_and_mapping(self) -> None:
        rate = 48_000
        center = 1500.0
        bandwidth = 937.5
        values = np.asarray([17, 64, 128, 239], dtype=np.uint8)
        for speed in (2, 4, 8):
            with self.subTest(speed=speed):
                component_samples = speed * 6
                prologue = 352 * 6
                recognized = 4800
                prologue_start = recognized + round(0.965 * rate)
                frequencies = np.concatenate(
                    [
                        np.full(prologue_start, center),
                        np.full(prologue, center - bandwidth / 2),
                        np.repeat(
                            center + bandwidth * (values.astype(float) - 128) / 256,
                            component_samples,
                        ),
                        np.full(round(1.440 * rate), center),
                    ]
                )
                phase = 2 * np.pi * np.cumsum(frequencies) / rate
                samples = np.exp(1j * phase).astype(np.complex64)
                header = f"Pic:4x1p{speed};".encode()
                events = [
                    event(index, value, recognized if index == len(header) - 1 else 0)
                    for index, value in enumerate(header)
                ]
                decoded = decode_pictures(
                    samples,
                    input_start=0,
                    sample_rate=rate,
                    mode="MFSK64",
                    orientation="normal",
                    center_hz=center,
                    text_events=events,
                )
                self.assertEqual(len(decoded.pictures), 1)
                picture = decoded.pictures[0]
                self.assertTrue(picture["complete"])
                actual = decoded.artifacts[0]["values"]
                self.assertLessEqual(
                    max(abs(left - right) for left, right in zip(actual, values)),
                    2,
                )

    def test_picture_mapping_uses_local_frequency_track(self) -> None:
        rate = 48_000
        center = 1500.0
        bandwidth = 937.5
        values = np.asarray([32, 96, 160, 224], dtype=np.uint8)
        component_samples = 8 * 6
        recognized = 4800
        prologue_start = recognized + round(0.965 * rate)
        prologue_samples = 352 * 6
        raster_start = prologue_start + prologue_samples
        raster_stop = raster_start + len(values) * component_samples
        track = FrequencyTrack(
            (
                FrequencyAnchor(0, center, 0.5, "rsid"),
                FrequencyAnchor(raster_stop, center + 10.0, 0.5, "rsid"),
            )
        )
        sample_positions = np.arange(raster_stop + round(1.440 * rate))
        local_centers = track.center_at(sample_positions)
        frequencies = local_centers.copy()
        frequencies[prologue_start:raster_start] -= bandwidth / 2
        for index, value in enumerate(values):
            start = raster_start + index * component_samples
            stop = start + component_samples
            frequencies[start:stop] += bandwidth * (int(value) - 128) / 256
        phase = 2 * np.pi * np.cumsum(frequencies) / rate
        samples = np.exp(1j * phase).astype(np.complex64)
        header = b"Pic:4x1;"
        events = [
            event(index, value, recognized if index == len(header) - 1 else 0)
            for index, value in enumerate(header)
        ]
        decoded = decode_pictures(
            samples,
            input_start=0,
            sample_rate=rate,
            mode="MFSK64",
            orientation="normal",
            center_hz=center,
            frequency_track=track,
            text_events=events,
        )
        actual = decoded.artifacts[0]["values"]
        self.assertLessEqual(
            max(abs(left - right) for left, right in zip(actual, values)),
            2,
        )


class ControlledPictureVerticalSliceTests(unittest.TestCase):
    def _decode(self, fixture_id: str) -> tuple[dict, dict]:
        fixture = next(
            item for item in EVIDENCE["fixtures"] if item["id"] == fixture_id
        )
        root = FIXTURE_ROOT / fixture["artifact_directory"]
        meta = root / fixture["artifacts"]["sigmf_meta"]
        data = root / fixture["artifacts"]["sigmf_data"]
        if not meta.is_file() or not data.is_file():
            self.skipTest("controlled MFSK picture fixtures unavailable")
        manifest = run_reference_pipeline(
            meta_path=meta,
            data_path=data,
            start_sample=None,
            stop_sample=None,
            config=DecodeConfig(mode="MFSK64", trace_level="events"),
        )
        return fixture, manifest

    def test_grayscale_header_transition_and_complete_raster(self) -> None:
        fixture, manifest = self._decode("mfsk64-gray-8x4-p8")
        self.assertEqual(manifest["input"]["data_sha256"], fixture["sigmf_data_sha256"])
        picture = manifest["pictures"][0]
        self.assertEqual(picture["header_text"], "Pic:8x4;")
        self.assertEqual((picture["width"], picture["height"]), (8, 4))
        self.assertFalse(picture["color"])
        self.assertEqual(picture["observed_component_count"], 32)
        self.assertTrue(picture["complete"])
        expected = fixture["raster_start_wav_sample"] - 48_000
        self.assertLessEqual(abs(picture["first_raster_input_sample"] - expected), 48)
        self.assertEqual(manifest["artifacts"][0]["shape"], [4, 8])

    def test_color_header_row_plane_assembly_and_reacquisition(self) -> None:
        fixture, manifest = self._decode("mfsk64-primary-color-8x4-p8")
        picture = manifest["pictures"][0]
        self.assertEqual(picture["header_text"], "Pic:8x4C;")
        self.assertTrue(picture["color"])
        self.assertEqual(picture["observed_component_count"], 96)
        self.assertTrue(picture["complete"])
        expected = fixture["raster_start_wav_sample"] - 48_000
        self.assertLessEqual(abs(picture["first_raster_input_sample"] - expected), 48)
        protocol = picture["protocol_boundary_prediction"]
        self.assertFalse(protocol["operative"])
        expected_prologue = fixture["prologue_start_wav_sample"] - 48_000
        self.assertEqual(
            expected_prologue
            - protocol["predicted_prologue_start_input_sample"],
            252,
        )
        self.assertEqual(manifest["artifacts"][0]["shape"], [4, 8, 3])
        interval = picture["return_to_text_reacquisition_interval"]
        self.assertEqual(interval["stop"] - interval["start"], 69_120)
        self.assertEqual(manifest["diagnostics"]["persistent_intermediate_files"], 0)


if __name__ == "__main__":
    unittest.main()
