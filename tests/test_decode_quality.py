"""The decode proxy follows wire and component time without changing IQ power."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from grampy.decode_quality import add_decode_confidence


RATE = 16_000


def _input() -> dict:
    return {
        "metadata_sha256": "a" * 64, "data_sha256": "b" * 64,
        "sample_rate_hz": RATE,
        "requested_interval": {"start": 0, "stop": 3 * RATE},
    }


def _event(identifier: str, start: int, *, value: float, valid: bool = True) -> dict:
    return {
        "id": identifier,
        "octet": ord("A") if valid else None,
        "control_role": None,
        "wire_interval": {"start": start, "stop": start + 2000},
        "confidence": {"kind": "minimum_absolute_input_llr", "value": value},
        "damage_flags": [] if valid else ["invalid_varicode"],
    }


def _documents() -> tuple[dict, dict, dict]:
    quality = {
        "schema": "grampy-quality-manifest.v1", "run_id": "0" * 24,
        "status": "partial", "decoder": {"version": "test", "configuration": {}},
        "input": _input(),
        "grid": {"origin_sample": 0, "interval_seconds": 1, "point_count": 3},
        "columns": ["signal_dbfs", "noise_dbfs", "decode_confidence"],
        "points": [[-40.0, -70.0, None] for _ in range(3)],
        "methods": {
            "signal_noise": {
                "id": "test", "calibrated_rf_power": False,
                "fft_size": 4096, "window": "hann", "snapshots_per_second": 4,
                "aggregation": "median_linear_power", "center_search_hz": 125,
                "guard_hz": 100, "noise_shoulder_hz": 500,
                "signal_band_hz": {"MFSK32": 531.25, "MFSK64": 1062.5},
                "noise_estimator": "test", "logical_iq_bytes_read": 0,
            },
            "decode_confidence": {
                "id": "pending-stage-4", "calibrated_error_probability": False,
            },
        },
        "exceptions": [],
        "warnings": [{"code": "decode-confidence-pending", "message": "pending"}],
    }
    source = {
        "run_id": "0" * 24, "status": "complete", "input": _input(),
        "text_events": [
            _event("high-1", 1000, value=3.0),
            _event("high-2", 5000, value=3.0),
            _event("low-1", RATE + 1000, value=0.05),
            _event("low-2", RATE + 5000, value=0.05, valid=False),
        ],
        "pictures": [{"id": "picture-1", "complete": True,
                      "width": 10, "height": 10, "color": False,
                      "component_evidence_artifact": "components-1"}],
        "artifacts": [{"id": "components-1", "kind": "npz_component_evidence",
                       "path": "components.npz"}],
    }
    text = {
        "run_id": "0" * 24, "input": _input(),
        "mode_segments": [{"items": [
            {"kind": "text", "interval": {"start": 0, "stop": 2 * RATE}},
            {"id": "picture-1", "kind": "picture",
             "interval": {"start": 2 * RATE, "stop": 3 * RATE}},
        ]}],
    }
    return quality, source, text


class DecodeQualityTests(unittest.TestCase):
    def test_text_margin_invalid_code_and_picture_damage(self) -> None:
        quality, source, text = _documents()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clipped = np.array([True] * 20 + [False] * 80)
            np.savez(root / "components.npz", input_start=[2 * RATE],
                     input_samples_per_component=[160], clipped=clipped,
                     value=np.full(100, 128, dtype=np.uint8))
            result = add_decode_confidence(
                quality, source, text, artifact_root=root
            )

        scores = [point[2] for point in result["points"]]
        self.assertEqual(scores[0], 1.0)
        self.assertAlmostEqual(scores[1], 0.401, places=3)
        self.assertAlmostEqual(scores[2], 0.92, places=3)
        self.assertEqual([point[:2] for point in result["points"]],
                         [point[:2] for point in quality["points"]])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["methods"]["decode_confidence"]["id"],
                         "reference-fidelity-proxy.v1")
        self.assertEqual(quality["points"][0][2], None)

    def test_missing_picture_evidence_remains_null(self) -> None:
        quality, source, text = _documents()
        with tempfile.TemporaryDirectory() as temporary:
            result = add_decode_confidence(
                quality, source, text, artifact_root=Path(temporary)
            )
        self.assertIsNone(result["points"][2][2])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["warnings"][0]["code"],
                         "decode-confidence-picture-evidence-missing")

    def test_inline_component_evidence_needs_no_artifact(self) -> None:
        quality, source, text = _documents()
        source["artifacts"] = []
        source["pictures"][0]["component_evidence_artifact"] = None
        source["pictures"][0]["component_evidence"] = [
            {
                "input_interval": {"start": 2 * RATE + index * 160,
                                   "stop": 2 * RATE + (index + 1) * 160},
                "damage_flags": ["clipped"] if index < 20 else [],
                "value": 128,
            }
            for index in range(100)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            result = add_decode_confidence(
                quality, source, text, artifact_root=Path(temporary)
            )
        self.assertAlmostEqual(result["points"][2][2], 0.92, places=3)
        self.assertEqual(result["status"], "complete")

    def test_incomplete_picture_does_not_penalize_received_components(self) -> None:
        quality, source, text = _documents()
        source["pictures"][0]["complete"] = False
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            np.savez(root / "components.npz", input_start=[2 * RATE],
                     input_samples_per_component=[160],
                     clipped=np.array([True] * 20 + [False] * 80),
                     value=np.full(100, 128, dtype=np.uint8))
            result = add_decode_confidence(
                quality, source, text, artifact_root=root
            )
        self.assertAlmostEqual(result["points"][2][2], 0.92, places=3)

    def test_spatial_outliers_reduce_picture_score_without_clipping(self) -> None:
        quality, source, text = _documents()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            values = np.full((10, 10), 128, dtype=np.uint8)
            values[::3, ::3] = 255
            np.savez(root / "components.npz", input_start=[2 * RATE],
                     input_samples_per_component=[160],
                     clipped=np.zeros(100, dtype=bool), value=values.reshape(-1))
            result = add_decode_confidence(
                quality, source, text, artifact_root=root
            )
        self.assertLess(result["points"][2][2], 0.98)
        self.assertGreater(result["points"][2][2], 0.9)


if __name__ == "__main__":
    unittest.main()
