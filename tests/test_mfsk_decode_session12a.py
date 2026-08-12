"""Regression coverage for the approved Session 12A picture defaults."""

from __future__ import annotations

import unittest

from grampy.cli import build_parser
from grampy.pipeline import DecodeConfig


class Session12ADefaultTests(unittest.TestCase):
    def test_decode_config_uses_approved_picture_measurement(self) -> None:
        config = DecodeConfig()
        self.assertEqual(config.picture_component_estimator, "bounded_correlation")
        self.assertEqual(config.picture_component_window, "full_hann")
        self.assertEqual(config.picture_filter_profile, "response_matched")

    def test_cli_uses_approved_picture_measurement(self) -> None:
        args = build_parser().parse_args([
            "--in-meta", "capture.sigmf-meta",
            "--in-data", "capture.sigmf-data",
            "--out-manifest", "output.json",
        ])
        self.assertEqual(args.picture_component_estimator, "bounded_correlation")
        self.assertEqual(args.picture_component_window, "full_hann")
        self.assertEqual(args.picture_filter_profile, "response_matched")


if __name__ == "__main__":
    unittest.main()
