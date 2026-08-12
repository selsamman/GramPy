from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from grampy.picture_decode import decode_pictures
from grampy.pipeline import DecodeConfig, run_reference_pipeline


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(
    os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests" / "samples")
)
CAPTURE = (
    SAMPLES
    / "received-corpus"
    / "sources"
    / "wrmi-20260708T133006Z-15770000"
    / "capture"
)


def _event(index: int, value: int, recognized: int) -> dict:
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


class BoundedPictureArtifactTests(unittest.TestCase):
    def test_large_raster_and_component_planes_are_atomic_sidecars(self) -> None:
        rate = 48_000
        center = 1500.0
        width, height = 65, 65
        header = f"Pic:{width}x{height};".encode()
        recognized = 4800
        prologue_start = recognized + round(0.965 * rate)
        prologue_samples = 352 * 6
        component_samples = 8 * 6
        frequencies = np.concatenate(
            [
                np.full(prologue_start, center),
                np.full(prologue_samples, center - 937.5 / 2),
                np.full(width * height * component_samples, center),
                np.full(1, center),
            ]
        )
        phase = 2 * np.pi * np.cumsum(frequencies) / rate
        samples = np.exp(1j * phase).astype(np.complex64)
        events = [
            _event(index, value, recognized if index == len(header) - 1 else 0)
            for index, value in enumerate(header)
        ]
        with tempfile.TemporaryDirectory(prefix="radiogram-mfsk-artifacts-") as name:
            artifact_dir = Path(name)
            decoded = decode_pictures(
                samples,
                input_start=0,
                sample_rate=rate,
                mode="MFSK64",
                orientation="normal",
                center_hz=center,
                text_events=events,
                artifact_dir=artifact_dir,
                artifact_path_prefix="decode.artifacts",
            )
            picture = decoded.pictures[0]
            self.assertEqual(picture["component_evidence"], [])
            self.assertEqual(len(decoded.artifacts), 2)
            self.assertEqual(
                [item["kind"] for item in decoded.artifacts],
                ["png_uint8_raster", "npz_component_evidence"],
            )
            for artifact in decoded.artifacts:
                path = artifact_dir / Path(artifact["path"]).name
                self.assertTrue(path.is_file())
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    artifact["sha256"],
                )
            self.assertEqual(decoded.diagnostics["persistent_artifact_files"], 2)


class ReceivedPictureTransitionTests(unittest.TestCase):
    DATA_SHA256 = (
        "1c1e443e64e47835bb38bd1996b935ada432e9db7b46a9fc3a01d7a8f5bb1cc6"
    )

    def test_received_color_picture_completes_and_returns_to_text(self) -> None:
        meta = CAPTURE.with_suffix(".sigmf-meta")
        data = CAPTURE.with_suffix(".sigmf-data")
        if not meta.is_file() or not data.is_file():
            self.skipTest(
                "received WRMI corpus unavailable; set GRAMPY_TEST_SAMPLES"
            )
        with tempfile.TemporaryDirectory(prefix="radiogram-mfsk-received-") as name:
            artifact_dir = Path(name) / "received.artifacts"
            manifest = run_reference_pipeline(
                meta_path=meta,
                data_path=data,
                start_sample=36_000_000,
                stop_sample=43_200_000,
                config=DecodeConfig(
                    mode="MFSK64",
                    center_hz=1586.25,
                    orientation="normal",
                    trace_level="summary",
                ),
                artifact_dir=artifact_dir,
                artifact_path_prefix="received.artifacts",
            )
            self.assertEqual(manifest["input"]["data_sha256"], self.DATA_SHA256)
            first = manifest["pictures"][0]
            self.assertEqual(first["header_text"], "Pic:220x147C;")
            self.assertEqual(first["expected_component_count"], 97_020)
            self.assertTrue(first["complete"])
            self.assertIsNotNone(
                first["first_trustworthy_resumed_text_input_sample"]
            )
            self.assertTrue(first["reacquisition_evidence"]["attempted"])
            self.assertEqual(
                first["reacquisition_evidence"]["source"],
                "independent_post_picture_iq_decode",
            )
            self.assertIsNotNone(first["following_text_epoch"])
            resumed_epoch = next(
                item
                for item in manifest["text_epochs"]
                if item["id"] == first["following_text_epoch"]
            )
            self.assertEqual(resumed_epoch["start_reset_cause"], "picture_completion")
            self.assertEqual(
                resumed_epoch["state_assumptions"]["fec_initial_state"], "unknown"
            )
            self.assertEqual(
                resumed_epoch["state_assumptions"]["prior_text_modem_state"],
                "discarded_at_picture_start",
            )
            self.assertGreaterEqual(len(manifest["pictures"]), 2)
            self.assertEqual(
                manifest["pictures"][1]["header_text"], "Pic:222x143C;"
            )
            self.assertEqual(
                [item["kind"] for item in manifest["artifacts"][:2]],
                ["png_uint8_raster", "npz_component_evidence"],
            )
            self.assertLess(manifest["diagnostics"]["bytes_written"], 5_000_000)


if __name__ == "__main__":
    unittest.main()
