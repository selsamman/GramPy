from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from grampy.acquisition import acquire_modes
from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.sigmf import SigmfRecording
from tests.rsid_support import SAMPLE_RATE, synthetic_rsid_sigmf


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(
    os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests" / "samples")
)
CORPUS = SAMPLES / "received-corpus"


class RemediationR1Test(unittest.TestCase):
    def test_shared_detector_emits_ranked_mode_region_and_track(self) -> None:
        with synthetic_rsid_sigmf() as fixture:
            recording = SigmfRecording.open(fixture.meta, fixture.data)
            result = acquire_modes(recording, threshold_db=8.0)

        self.assertEqual(len(result.mode_hypotheses), 1)
        hypothesis = result.mode_hypotheses[0]
        self.assertEqual(hypothesis["rank"], 1)
        self.assertEqual(hypothesis["mode"], "MFSK32")
        self.assertEqual(hypothesis["orientation"], "normal")
        self.assertEqual(hypothesis["evidence"]["rsid_code"], 147)
        self.assertEqual(hypothesis["evidence"]["code_distance"], 0)
        self.assertAlmostEqual(hypothesis["evidence"]["center_hz"], 1582.0, delta=3.0)

        self.assertEqual(len(result.regions), 1)
        region = result.regions[0]
        self.assertEqual(region.role, "rsid_acquisition")
        self.assertLess(region.interval_stop - region.interval_start, SAMPLE_RATE * 4)
        self.assertIn("RSID", region.threshold_basis)

        self.assertEqual(len(result.mode_segments), 1)
        self.assertEqual(result.mode_segments[0]["mode"], "MFSK32")
        self.assertEqual(len(result.frequency_tracks), 1)
        self.assertAlmostEqual(
            result.frequency_tracks[0].anchors[0].center_hz, 1582.0, delta=3.0
        )

    def test_auto_manifest_serializes_r1_evidence_without_full_iq_decode(self) -> None:
        with synthetic_rsid_sigmf() as fixture:
            manifest = run_reference_pipeline(
                meta_path=fixture.meta,
                data_path=fixture.data,
                start_sample=None,
                stop_sample=None,
                config=DecodeConfig(mode="auto"),
            )

        self.assertEqual(manifest["mode_hypotheses"][0]["mode"], "MFSK32")
        self.assertEqual(manifest["mode_segments"][0]["source"], "rsid")
        self.assertEqual(manifest["signal_regions"][0]["role"], "rsid_acquisition")
        self.assertEqual(
            manifest["frequency_tracks"][0]["anchors"][0]["source"], "rsid:147"
        )
        self.assertEqual(manifest["text_events"], [])
        self.assertIn(
            "segmented-payload-decode-deferred",
            {warning["code"] for warning in manifest["warnings"]},
        )

    def test_weak_full_broadcasts_recover_established_mode_events(self) -> None:
        cases = (
            (
                "winb-20260718T023007Z-9265000",
                "d356d6d177aa63d26bd82113fa0e2e54f7a90bdd37ff39e56bc4cc1a94907adc",
                1547.699,
            ),
            (
                "wrmi-20260720T080010Z-5850000",
                "8a3af499ee3448e7c629cb5c17455e1f1244adafb3f81acafda2fbf95b589f09",
                1499.249,
            ),
        )
        required = [
            CORPUS / "sources" / capture_id / "capture.sigmf-data"
            for capture_id, _, _ in cases
        ]
        required.extend(
            CORPUS / "sources" / capture_id / "capture.sigmf-meta"
            for capture_id, _, _ in cases
        )
        required.extend(
            CORPUS / "truth" / capture_id / "expected-rsid-events.json"
            for capture_id, _, _ in cases
        )
        if not all(path.is_file() for path in required):
            self.skipTest(
                "weak received corpus unavailable; set GRAMPY_TEST_SAMPLES"
            )

        for capture_id, expected_hash, established_center in cases:
            with self.subTest(capture_id=capture_id):
                source = CORPUS / "sources" / capture_id
                truth_path = (
                    CORPUS / "truth" / capture_id / "expected-rsid-events.json"
                )
                truth = json.loads(truth_path.read_text(encoding="utf-8"))
                expected = [
                    event
                    for event in truth["events"]
                    if isinstance(event["strict_detector"], dict)
                ]
                manifest = run_reference_pipeline(
                    meta_path=source / "capture.sigmf-meta",
                    data_path=source / "capture.sigmf-data",
                    start_sample=None,
                    stop_sample=None,
                    config=DecodeConfig(mode="auto"),
                )
                hypotheses = manifest["mode_hypotheses"]

                self.assertEqual(manifest["input"]["data_sha256"], expected_hash)
                self.assertEqual(len(hypotheses), len(expected))
                self.assertEqual(
                    [item["mode"] for item in hypotheses],
                    [item["mode"] for item in expected],
                )
                self.assertEqual(
                    [item["evidence"]["code_distance"] for item in hypotheses],
                    [
                        item["strict_detector"]["code_distance"]
                        for item in expected
                    ],
                )
                for hypothesis, event in zip(hypotheses, expected):
                    actual_sec = (
                        hypothesis["event_interval"]["start"] / SAMPLE_RATE
                    )
                    self.assertAlmostEqual(
                        actual_sec,
                        event["strict_detector"]["capture_sec"],
                        delta=0.5,
                    )
                    center = hypothesis["evidence"]["center_hz"]
                    self.assertLess(abs(center - established_center), 6.0)
                    self.assertNotAlmostEqual(center, 1582.0, delta=1.0)
                self.assertEqual(
                    [item["mode"] for item in manifest["mode_segments"]],
                    ["MFSK32", "MFSK64", "MFSK32"],
                )


if __name__ == "__main__":
    unittest.main()
