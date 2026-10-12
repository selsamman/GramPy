"""Explicit compatibility checks for the historical v1/v2 qualification workflow.

Run from the repository root with unittest discovery in this directory.
These contracts do not qualify current encoder or decoder behavior.
"""
from pathlib import Path
import hashlib
import json
import unittest

from jsonschema import Draft202012Validator
from tests.mfsk_encoder_evidence import load_json, read_ppm, grayscale_values

ROOT = Path(__file__).resolve().parents[2]
PI_MATRIX = ROOT / "docs/encoder/data/mfsk_encoder_pi_matrix_v1.json"
PI_MANIFEST_SCHEMA = ROOT / "docs/encoder/data/mfsk_encoder_pi_qualification_manifest_v1.schema.json"
PRIMARY_RGB_PPM = ROOT / "tests/fixtures/mfsk/primary-color-8x4.ppm"
MATRIX = ROOT / "docs/encoder/data/mfsk_encoder_pi_matrix_v2.json"
MANIFEST_SCHEMA = ROOT / "docs/encoder/data/mfsk_encoder_pi_qualification_manifest_v2.schema.json"

class HistoricalV1QualificationContractTests(unittest.TestCase):
    def test_matrix_has_the_required_interoperability_coverage(self) -> None:
        matrix = load_json(PI_MATRIX)
        self.assertEqual(matrix["schema"], "grampy-mfsk-encoder-pi-matrix.v1")
        self.assertEqual(matrix["sample_rate_hz"], 48000)
        self.assertEqual(
            matrix["receiver"]["reference_id"],
            "fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178",
        )
        width, height, pixels = read_ppm(PRIMARY_RGB_PPM)
        rgb_bytes = bytes(component for pixel in pixels for component in pixel)
        gray_bytes = bytes(grayscale_values(pixels))
        source = matrix["source_inputs"]["primary_rgb_png"]
        self.assertEqual((source["width"], source["height"]), (width, height))
        self.assertEqual(
            source["rgb_pixel_sha256"], hashlib.sha256(rgb_bytes).hexdigest()
        )
        self.assertEqual(
            source["grayscale_pixel_sha256"], hashlib.sha256(gray_bytes).hexdigest()
        )
        cases = {case["id"]: case for case in matrix["cases"]}
        self.assertEqual(
            set(cases),
            {
                "mfsk32-text",
                "mfsk64-text",
                "mfsk32-grayscale-speeds",
                "mfsk64-color-speeds",
                "adjacent-modes-no-gap",
                "mixed-composition-boundaries",
            },
        )
        image_coverage = {
            (content["color"], content["samples_per_pixel"])
            for case in matrix["cases"]
            for segment in case["composition"]
            if segment["kind"] == "mfsk"
            for content in segment["contents"]
            if content["kind"] == "image"
        }
        self.assertTrue(
            {(color, speed) for color in ("grayscale", "color") for speed in (2, 4, 8)}
            <= image_coverage
        )
        modes = {
            segment["mode"]
            for case in matrix["cases"]
            for segment in case["composition"]
            if segment["kind"] == "mfsk"
        }
        self.assertEqual(modes, {"MFSK32", "MFSK64"})
        self.assertTrue(
            any(
                content["kind"] == "text" and content.get("role") == "post-picture"
                for case in matrix["cases"]
                for segment in case["composition"]
                if segment["kind"] == "mfsk"
                for content in segment["contents"]
            )
        )
        mixed_kinds = [
            part["kind"] for part in cases["mixed-composition-boundaries"]["composition"]
        ]
        self.assertEqual(mixed_kinds, ["mfsk", "silence", "audio", "silence", "mfsk"])
        adjacent = cases["adjacent-modes-no-gap"]
        self.assertEqual(
            [part["mode"] for part in adjacent["composition"]],
            ["MFSK32", "MFSK64"],
        )
        self.assertEqual(
            [(run["mode"], run["window"]) for run in adjacent["receiver_runs"]],
            [("MFSK32", "segment:0"), ("MFSK64", "segment:1")],
        )

    def test_pi_manifest_schema_is_valid_and_requires_hashes_and_outcomes(self) -> None:
        schema = load_json(PI_MANIFEST_SCHEMA)
        Draft202012Validator.check_schema(schema)
        required = set(schema["required"])
        self.assertTrue(
            {
                "schema",
                "run_id",
                "status",
                "source",
                "target",
                "receiver",
                "cases",
                "summary",
            }
            <= required
        )
        case_required = set(schema["$defs"]["case"]["required"])
        self.assertTrue(
            {
                "id",
                "status",
                "generated_wav",
                "encoder_result",
                "receiver_runs",
                "checks",
                "discrepancies",
            }
            <= case_required
        )
        digest = "0" * 64
        artifact = {"path": "artifact.bin", "sha256": digest, "bytes": 1}
        case = {
            "id": "case",
            "status": "pass",
            "generated_wav": {
                "path": "case.wav",
                "sha256": digest,
                "bytes": 46,
                "sample_rate_hz": 48000,
                "channels": 1,
                "sample_width_bytes": 2,
                "frame_count": 1,
            },
            "encoder_result": {
                "artifact": artifact,
                "output_path": "case.wav",
                "duration_seconds": 1 / 48000,
                "segments": [
                    {"input_index": 0, "start_frame": 0, "content_start_frames": [0]}
                ],
            },
            "receiver_runs": [
                {
                    "mode": "MFSK32",
                    "input_interval": {"start_frame": 0, "end_frame": 1},
                    "configuration": {},
                    "exit_code": 0,
                    "log": artifact,
                    "recovered_text": {"artifact": artifact, "decoded_utf8": "ok"},
                    "recovered_images": [],
                }
            ],
            "checks": [
                {"id": "receiver-exit-success", "status": "pass", "expected": 0, "observed": 0}
            ],
            "discrepancies": [],
        }
        manifest = {
            "schema": "grampy-mfsk-encoder-pi-qualification-manifest.v1",
            "run_id": "0" * 24,
            "status": "complete",
            "source": {
                "repository_revision": "0" * 40,
                "matrix": artifact,
                "encoder_distribution": artifact,
                "inputs": [artifact],
            },
            "target": {
                "hostname": "pi",
                "platform": "linux",
                "architecture": "aarch64",
                "python_version": "3.11",
            },
            "receiver": {
                "reference_id": "fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178",
                "version": "4.2.13",
                "binary": artifact,
                "configuration": {},
            },
            "execution": {
                "workflow": "tools/pi-qualify-mfsk-encoder.sh",
                "started_utc": "2026-10-01T00:00:00Z",
                "completed_utc": "2026-10-01T00:01:00Z",
                "log": artifact,
            },
            "cases": [{**case, "id": f"case-{index}"} for index in range(5)],
            "summary": {"total": 5, "passed": 5, "failed": 0, "blocked": 0},
        }
        Draft202012Validator(schema).validate(manifest)


class HistoricalV2QualificationContractTests(unittest.TestCase):
    def test_draft_pi_contract_requires_continuous_rxid_acquisition(self) -> None:
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(matrix["schema"], "grampy-mfsk-encoder-pi-matrix.v2")
        self.assertEqual(matrix["encoder_rsid_policy"]["per_mfsk_segment"], "required-unconditional")
        self.assertTrue(matrix["encoder_rsid_policy"]["includes_first_and_repeated_same_mode"])
        self.assertFalse(matrix["encoder_rsid_policy"]["caller_opt_out"])
        self.assertFalse(matrix["encoder_rsid_policy"]["extra_editorial_silence"])
        self.assertTrue(matrix["receiver"]["rxid_enabled"])
        self.assertFalse(matrix["receiver"]["rxid_notify_only"])
        self.assertFalse(matrix["receiver"]["rxid_auto_disable_after_detection"])
        self.assertEqual(matrix["receiver"]["initial_mode"], "BPSK31")
        self.assertEqual(len(matrix["cases"]), 7)
        expected = {"MFSK32", "MFSK64"}
        self.assertEqual(
            {mode for case in matrix["cases"] for mode in case["expected_rsid_modes"]},
            expected,
        )
        for case in matrix["cases"]:
            self.assertTrue(any("whole-wav-rxid-run" in check for check in case["required_checks"]))
            self.assertGreaterEqual(len(case["expected_rsid_modes"]), 1)


if __name__ == "__main__":
    unittest.main()
