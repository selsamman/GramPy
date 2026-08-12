from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "mfsk-image-review"


class MfskImageReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        namespace = runpy.run_path(str(TOOL))
        cls.final_scorecard = staticmethod(namespace["final_scorecard"])
        cls.scorecard_html = staticmethod(namespace["scorecard_html"])
        cls.candidate_specs = staticmethod(namespace["candidate_specs"])

    def test_candidate_specs_accept_an_arbitrary_named_set(self) -> None:
        candidates = self.candidate_specs([
            "Hann=results/hann", "FFT=results/fft", "Consensus=results/consensus",
        ])
        self.assertEqual(candidates, [
            ("Hann", Path("results/hann")),
            ("FFT", Path("results/fft")),
            ("Consensus", Path("results/consensus")),
        ])
        with self.assertRaisesRegex(ValueError, "LABEL=ROOT"):
            self.candidate_specs(["invalid"])

    def test_final_scorecard_preserves_identity_metrics_and_gate_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = root / "summary.json"
            gate = root / "gate.json"
            summary.write_text(
                json.dumps(
                    {
                        "decoder_summaries": [
                            {
                                "decoder": "direct",
                                "aggregation": "unweighted_program_mean",
                                "program_count": 3,
                                "text_character_error_rate": 0.12,
                                "picture_event_recall": 0.9,
                                "aligned_image_mae_255": 32.0,
                                "raw_image_mae_255": 38.0,
                                "maximum_absolute_alignment_offset_components": 9,
                                "maximum_absolute_dominant_alignment_offset_components": 4,
                            },
                            {
                                "decoder": "fldigi",
                                "aggregation": "unweighted_program_mean",
                                "program_count": 3,
                                "text_character_error_rate": 0.06,
                                "picture_event_recall": 0.875,
                                "aligned_image_mae_255": 24.5,
                                "raw_image_mae_255": 29.0,
                                "maximum_absolute_alignment_offset_components": 5,
                                "maximum_absolute_dominant_alignment_offset_components": 2,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            gate.write_text(
                json.dumps(
                    {
                        "identities": {
                            "direct_decoder": {"name": "direct"},
                            "fldigi": {"name": "fldigi"},
                        },
                        "policy_id": "policy-v2",
                        "passed": False,
                        "aggregate_weighted_advantage": -0.03,
                        "catastrophic_regressions": [
                            {"metric": "text_accuracy"}
                        ],
                        "cases": [{"program_id": "456"}],
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                summary=summary,
                gate=gate,
                title="Accepted comparison",
                direct_label="Accepted direct",
                fldigi_label="Qualified fldigi",
                decision_status="accepted picture baseline",
            )

            scorecard = self.final_scorecard(args)

        assert scorecard is not None
        self.assertEqual(scorecard["schema"], "grampy-final-scorecard.v1")
        self.assertAlmostEqual(
            scorecard["metrics"]["aligned_image_mae_255"][
                "direct_minus_fldigi"
            ],
            7.5,
        )
        self.assertEqual(
            scorecard["planning_gate"][
                "picture_fidelity_catastrophic_regression_count"
            ],
            0,
        )
        self.assertAlmostEqual(
            scorecard["metrics"]["raw_image_mae_255"][
                "direct_minus_fldigi"
            ],
            9.0,
        )
        document = self.scorecard_html(scorecard)
        self.assertIn("Accepted direct", document)
        self.assertIn("-0.03000", document)
        self.assertIn("Raw image MAE /255", document)
        self.assertIn("Maximum dominant alignment compensation", document)

    def test_summary_and_gate_must_be_supplied_together(self) -> None:
        args = argparse.Namespace(summary=Path("summary.json"), gate=None)
        with self.assertRaisesRegex(ValueError, "must be supplied together"):
            self.final_scorecard(args)


if __name__ == "__main__":
    unittest.main()
