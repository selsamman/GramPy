from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from grampy.pipeline import DecodeConfig, run_reference_pipeline


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(
    os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests" / "samples")
)
EVIDENCE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json").read_text(encoding="utf-8")
)
RECEIVED = (
    SAMPLES
    / "received-corpus"
    / "sources"
    / "wrmi-20260708T133006Z-15770000"
    / "capture"
)
START_SAMPLE = 570 * 48_000
STOP_SAMPLE = 630 * 48_000
DATA_SHA256 = "1c1e443e64e47835bb38bd1996b935ada432e9db7b46a9fc3a01d7a8f5bb1cc6"


class MFSK64TextVerticalSliceTests(unittest.TestCase):
    def test_controlled_iq_decodes_exact_octets_through_shared_pipeline(self) -> None:
        fixture = next(
            item
            for item in EVIDENCE["fixtures"]
            if item["id"] == "mfsk64-text-printable"
        )
        fixture_root = Path(
            os.environ.get(
                "GRAM_PY_MFSK_FIXTURES",
                ROOT / ".local" / "fldigi-fixtures",
            )
        ) / fixture["artifact_directory"]
        meta = fixture_root / fixture["artifacts"]["sigmf_meta"]
        data = fixture_root / fixture["artifacts"]["sigmf_data"]
        if not meta.is_file() or not data.is_file():
            self.skipTest(
                "controlled MFSK fixtures unavailable; set GRAM_PY_MFSK_FIXTURES"
            )

        manifest = run_reference_pipeline(
            meta_path=meta,
            data_path=data,
            start_sample=None,
            stop_sample=None,
            config=DecodeConfig(mode="MFSK64", trace_level="events"),
        )

        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["input"]["data_sha256"], fixture["sigmf_data_sha256"])
        self.assertEqual(manifest["text_summary"]["text"], fixture["decoded_text"])
        self.assertEqual(
            bytes(manifest["text_summary"]["octets"]),
            fixture["decoded_text"].encode("ascii"),
        )
        segment = manifest["mode_segments"][0]
        self.assertEqual(segment["mode"], "MFSK64")
        self.assertEqual(segment["orientation"], "normal")
        self.assertLess(abs(segment["center_hz"] - 1500.0), 12.0)
        tones = manifest["diagnostics"]["text_pipeline"]["tone_evidence"]
        self.assertEqual(tones["tone_spacing_hz"], 62.5)
        self.assertEqual(tones["symbol_samples"], 768)
        self.assertEqual(manifest["diagnostics"]["persistent_intermediate_files"], 0)

    def test_untouched_received_interval_decodes_mfsk64_without_hints(self) -> None:
        meta = RECEIVED.with_suffix(".sigmf-meta")
        data = RECEIVED.with_suffix(".sigmf-data")
        if not meta.is_file() or not data.is_file():
            self.skipTest(
                "received WRMI fixture unavailable; set GRAMPY_TEST_SAMPLES"
            )

        manifest = run_reference_pipeline(
            meta_path=meta,
            data_path=data,
            start_sample=START_SAMPLE,
            stop_sample=STOP_SAMPLE,
            config=DecodeConfig(mode="MFSK64", trace_level="summary"),
        )

        decoded = manifest["text_summary"]["text"]
        self.assertIn('"The Star-Spangled Banner"', decoded)
        self.assertIn("national anthem of the United \nStates", decoded)
        self.assertIn("Popular Usage:", decoded)
        self.assertEqual(manifest["input"]["data_sha256"], DATA_SHA256)
        self.assertEqual(
            manifest["input"]["requested_interval"],
            {"start": START_SAMPLE, "stop": STOP_SAMPLE},
        )
        segment = manifest["mode_segments"][0]
        self.assertEqual(segment["mode"], "MFSK64")
        self.assertEqual(segment["orientation"], "normal")
        self.assertGreater(segment["center_hz"], 1550.0)
        self.assertLess(segment["center_hz"], 1625.0)
        tones = manifest["diagnostics"]["text_pipeline"]["tone_evidence"]
        self.assertGreaterEqual(len(tones["acquisition_candidates"]), 2)
        self.assertEqual(tones["symbol_samples"], 768)
        self.assertLess(abs(tones["frequency_track"]["drift_hz_per_second"]), 0.5)
        self.assertLess(
            abs(tones["clock_track"]["estimated_rate_error_ppm"]), 500.0
        )
        self.assertEqual(manifest["diagnostics"]["persistent_intermediate_files"], 0)


if __name__ == "__main__":
    unittest.main()
