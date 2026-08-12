from __future__ import annotations

import difflib
import os
from pathlib import Path
import unittest

from grampy.pipeline import DecodeConfig, run_reference_pipeline


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(
    os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests" / "samples")
)
SOURCE = (
    SAMPLES
    / "received-corpus"
    / "sources"
    / "wrmi-20260708T133006Z-15770000"
)
TRUTH = (
    SAMPLES
    / "received-corpus"
    / "truth"
    / "wrmi-20260708T133006Z-15770000"
)
START_SAMPLE = 84 * 48_000
STOP_SAMPLE = 151 * 48_000
DATA_SHA256 = "1c1e443e64e47835bb38bd1996b935ada432e9db7b46a9fc3a01d7a8f5bb1cc6"


class ReceivedMFSK32AcquisitionTests(unittest.TestCase):
    def test_untouched_wrmi_interval_decodes_with_rf_tracking(self) -> None:
        meta = SOURCE / "capture.sigmf-meta"
        data = SOURCE / "capture.sigmf-data"
        expected_path = TRUTH / "mfsk32-84-151-expected.txt"
        if not all(path.is_file() for path in (meta, data, expected_path)):
            self.skipTest(
                "received WRMI fixture unavailable; set GRAMPY_TEST_SAMPLES"
            )

        manifest = run_reference_pipeline(
            meta_path=meta,
            data_path=data,
            start_sample=START_SAMPLE,
            stop_sample=STOP_SAMPLE,
            config=DecodeConfig(trace_level="summary"),
        )

        expected = expected_path.read_text(encoding="utf-8")
        decoded = manifest["text_summary"]["text"]
        character_accuracy = difflib.SequenceMatcher(
            None, expected, decoded, autojunk=False
        ).ratio()
        self.assertGreaterEqual(character_accuracy, 0.85)
        self.assertEqual(manifest["input"]["data_sha256"], DATA_SHA256)
        self.assertEqual(
            manifest["input"]["requested_interval"],
            {"start": START_SAMPLE, "stop": STOP_SAMPLE},
        )

        segment = manifest["mode_segments"][0]
        self.assertEqual(segment["orientation"], "normal")
        self.assertGreater(segment["center_hz"], 1550.0)
        self.assertLess(segment["center_hz"], 1625.0)
        self.assertGreater(segment["interval"]["start"], START_SAMPLE)

        tones = manifest["diagnostics"]["text_pipeline"]["tone_evidence"]
        candidates = tones["acquisition_candidates"]
        self.assertGreaterEqual(len(candidates), 2)
        self.assertTrue(
            any(candidate["center_hz"] > 2000 for candidate in candidates)
        )
        track = tones["frequency_track"]
        self.assertGreaterEqual(len(track["points"]), 5)
        self.assertEqual(track["points"][0]["lock_state"], "searching")
        self.assertIn("locked", [point["lock_state"] for point in track["points"]])
        self.assertLess(abs(track["drift_hz_per_second"]), 0.5)
        self.assertLess(
            abs(tones["clock_track"]["estimated_rate_error_ppm"]), 500.0
        )
        self.assertGreater(tones["quality"]["weak_symbol_count"], 0)
        self.assertEqual(
            manifest["diagnostics"]["persistent_intermediate_files"], 0
        )


if __name__ == "__main__":
    unittest.main()
