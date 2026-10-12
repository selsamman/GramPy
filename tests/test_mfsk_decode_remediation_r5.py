from __future__ import annotations

import unittest
from unittest import mock

from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.accuracy import extract_framed_payload
from tests.controlled_fixtures import require_fixture
from tests.suites import data_test


class BoundedPipelineTests(unittest.TestCase):
    def _check_bounded_text(self, mode, organization, kind):
        fixture, meta, data = require_fixture(f"{mode.lower()}-text-printable")
        with mock.patch("grampy.pipeline.BOUNDED_PIPELINE_THRESHOLD_SECONDS", 0.0):
            manifest = run_reference_pipeline(
                meta_path=meta, data_path=data, start_sample=None, stop_sample=None,
                config=DecodeConfig(mode=mode, center_hz=1500.0,
                                    orientation="normal", trace_level="summary"),
            )
        self.assertEqual(manifest["diagnostics"]["working_set_organization"], organization)
        wire_text = "".join(chr(event["octet"]) for event in manifest["text_events"]
                            if event["octet"] is not None
                            and event.get("control_role") not in {"NUL", "CR"})
        framed = extract_framed_payload(wire_text)
        self.assertGreaterEqual(framed.frame_count, 1)
        self.assertEqual(framed.text.strip("\r\n"), fixture["decoded_text"])
        if mode == "MFSK32":
            self.assertEqual(manifest["text_summary"]["text"], fixture["decoded_text"])
        bounded = manifest["diagnostics"]["text_pipeline"]["bounded_organization"]
        self.assertEqual(bounded["kind"], kind)
        self.assertLessEqual(
            bounded["maximum_materialized_iq_samples"],
            manifest["input"]["requested_interval"]["stop"]
            - manifest["input"]["requested_interval"]["start"],
        )

    @data_test("controlled")
    def test_mfsk32_default_uses_bounded_fallback_and_preserves_text(self):
        self._check_bounded_text("MFSK32",
                                "bounded_overlapping_text_windows_and_complete_picture_windows",
                                "overlapping_complete-region_text_windows")

    @data_test("controlled")
    def test_mfsk64_default_uses_compact_bounded_path_and_preserves_text(self):
        self._check_bounded_text("MFSK64", "p11d_bounded_text_and_picture_ranges",
                                "p11d_compact_tracks_and_stateful_text_pass")


if __name__ == "__main__":
    unittest.main()
