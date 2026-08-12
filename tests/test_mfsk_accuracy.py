from __future__ import annotations

import unittest

import numpy as np

from grampy.accuracy import (
    align_component_streams,
    extract_framed_payload,
    image_to_wire_components,
    normalize_presentation_text,
    score_mode_sequence,
    score_raw_rasters,
    score_picture_truth_availability,
    score_text,
)


class FramedTextTests(unittest.TestCase):
    def test_concatenates_only_complete_payload_epochs(self) -> None:
        result = extract_framed_payload(
            "garbage\x02first\r\n\x04noise\x02second\x04trailing"
        )
        self.assertEqual(result.text, "first\r\nsecond")
        self.assertEqual(result.frame_count, 2)
        self.assertEqual(result.discarded_prefix_characters, 7)
        self.assertEqual(result.discarded_interframe_characters, 5)
        self.assertEqual(result.discarded_suffix_characters, 8)

    def test_unmatched_controls_are_diagnostics_not_payload(self) -> None:
        result = extract_framed_payload("\x04bad\x02lost\x02kept\x04")
        self.assertEqual(result.text, "kept")
        self.assertEqual(result.unmatched_eot, 1)
        self.assertEqual(result.unmatched_stx, 1)

    def test_presentation_normalization_ignores_line_wrapping(self) -> None:
        self.assertEqual(
            normalize_presentation_text("one\r\n  two\nthree"),
            "one two three",
        )

    def test_text_score_separates_error_kinds(self) -> None:
        result = score_text("abcdef", "abXdeZf")
        self.assertEqual(result["substitutions"], 1)
        self.assertEqual(result["insertions"], 1)
        self.assertEqual(result["deletions"], 0)

    def test_mode_sequence_reports_missed_and_false_events(self) -> None:
        result = score_mode_sequence(
            ["MFSK32", "MFSK64", "MFSK32"],
            [
                {"mode": "MFSK32"},
                {"mode": "MFSK16"},
                {"mode": "MFSK64"},
            ],
        )
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(result["missed_count"], 1)
        self.assertEqual(result["false_count"], 1)
        self.assertEqual(result["coordinate_truth_status"], "not_available")


class PictureAccuracyTests(unittest.TestCase):
    def test_rgb_wire_order_is_row_plane_order(self) -> None:
        image = np.asarray(
            [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]],
            dtype=np.uint8,
        )
        np.testing.assert_array_equal(
            image_to_wire_components(image),
            [1, 4, 2, 5, 3, 6, 7, 10, 8, 11, 9, 12],
        )

    def test_declared_missing_truth_is_not_an_artifact_failure(self) -> None:
        self.assertEqual(
            score_picture_truth_availability(
                truth_status="missing", truth_path_exists=False
            )["status"],
            "not_scored_missing_truth",
        )
        self.assertEqual(
            score_picture_truth_availability(
                truth_status="available", truth_path_exists=False
            )["status"],
            "error_truth_artifact_missing",
        )

    def test_raw_raster_metrics_report_signed_channel_bias(self) -> None:
        truth = np.zeros((2, 2, 3), dtype=np.uint8)
        decoded = np.zeros((2, 2, 3), dtype=np.uint8)
        decoded[:, :, 0] = 10
        result = score_raw_rasters(truth, decoded)
        self.assertEqual(result["channels"]["red"]["signed_bias_255"], 10)
        self.assertEqual(result["channels"]["green"]["mean_absolute_error_255"], 0)
        self.assertAlmostEqual(
            result["whole_raster"]["mean_absolute_error_255"], 10 / 3
        )

    def test_alignment_finds_persistent_one_component_shift(self) -> None:
        truth = np.tile(np.arange(31, dtype=np.uint8) * 7, 6)
        decoded = np.concatenate((truth[:70], truth[69:-1]))
        result = align_component_streams(
            truth, decoded, max_offset=4, change_penalty=0.04
        )
        segments = result["offset_path_rle"]
        self.assertEqual(segments[0]["offset"], 0)
        self.assertEqual(segments[-1]["offset"], -1)
        self.assertLess(result["aligned_mean_absolute_error_255"], 1.0)

    def test_noise_does_not_force_offset_changes(self) -> None:
        truth = np.tile(np.arange(50, dtype=np.uint8) * 5, 4)
        decoded = np.clip(truth.astype(np.int16) + 2, 0, 255).astype(np.uint8)
        result = align_component_streams(truth, decoded, max_offset=3)
        self.assertEqual(result["offset_change_count"], 0)
        self.assertEqual(result["zero_offset_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
