from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from grampy.accuracy_cli import main


class AccuracyCliTests(unittest.TestCase):
    def test_program_fldigi_accepts_an_immutable_recent_reference(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            corpus = root / "corpus"
            program = corpus / "programs" / "1"
            (program / "truth").mkdir(parents=True)
            (program / "transmissions").mkdir()
            (program / "truth" / "text.txt").write_text("hello")
            (program / "truth" / "text-review.json").write_text(
                json.dumps({"status": "approved", "truth_path": "truth/text.txt"})
            )
            (program / "program.json").write_text(
                json.dumps(
                    {
                        "text_truth": {
                            "review": "truth/text-review.json",
                            "status": "approved",
                            "artifact": {"path": "truth/text.txt"},
                        },
                        "pictures": [],
                        "mode_sequence_truth": {"status": "reviewed_program_truth"},
                    }
                )
            )
            (program / "transmissions" / "test.json").write_text(
                json.dumps(
                    {
                        "benchmark_role": "test",
                        "fldigi_reference": {"decoder": "fldigi", "version": "4.2.06"},
                    }
                )
            )
            reference = corpus / "references" / "test" / "fldigi-recent"
            reference.mkdir(parents=True)
            (reference / "images").mkdir()
            (reference / "decoded.txt").write_text("\x02hello\x04")
            output = root / "score.json"
            self.assertEqual(
                main(
                    [
                        "program-fldigi",
                        "--corpus", str(corpus),
                        "--program", "1",
                        "--transmission", "test",
                        "--reference-id", "fldigi-recent",
                        "--decoder-version", "4.2.12",
                        "--output", str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertEqual(result["decoder_version"], "4.2.12")
            self.assertEqual(result["decoder_reference_id"], "fldigi-recent")
            self.assertEqual(result["text"]["character_error_rate"], 0)

    def test_text_command_writes_framing_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "truth.txt").write_text("one two\n")
            (root / "decoded.txt").write_text("noise\x02one\r\ntwo\x04tail")
            output = root / "score.json"
            self.assertEqual(
                main(
                    [
                        "text",
                        "--truth",
                        str(root / "truth.txt"),
                        "--decoded",
                        str(root / "decoded.txt"),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertTrue(result["exact"])
            self.assertEqual(result["framing_diagnostics"]["frame_count"], 1)

    def test_picture_command_scores_identical_png(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / "image.png"
            Image.new("RGB", (3, 2), (10, 20, 30)).save(path)
            output = root / "score.json"
            self.assertEqual(
                main(
                    [
                        "picture",
                        "--truth",
                        str(path),
                        "--decoded",
                        str(path),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertEqual(result["aligned_mean_absolute_error_255"], 0)
            self.assertTrue(result["geometry_matches"])

    def test_program_direct_merges_modes_and_labels_two_pass_result(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            corpus = root / "corpus"
            program = corpus / "programs" / "1"
            (program / "truth" / "images").mkdir(parents=True)
            (program / "truth" / "text.txt").write_text("one two")
            (program / "truth" / "text-review.json").write_text(
                json.dumps({"status": "approved", "truth_path": "truth/text.txt"})
            )
            (program / "transmissions").mkdir()
            (program / "transmissions" / "test.json").write_text(
                json.dumps({"benchmark_role": "test"})
            )
            truth_image = program / "truth" / "images" / "001-test.png"
            Image.new("RGB", (3, 2), (10, 20, 30)).save(truth_image)
            (program / "program.json").write_text(
                json.dumps(
                    {
                        "mode_sequence_truth": {
                            "basis": "test",
                            "events": [
                                {"mode": "MFSK32"},
                                {"mode": "MFSK64"},
                                {"mode": "MFSK32"},
                            ],
                            "status": "reviewed_program_truth",
                        },
                        "text_truth": {
                            "review": "truth/text-review.json",
                            "status": "approved",
                            "artifact": {"path": "truth/text.txt"},
                        },
                        "pictures": [
                            {
                                "order": 1,
                                "stable_id": "test",
                                "expected_header": "Pic:3x2C;",
                                "width": 3,
                                "height": 2,
                                "color": True,
                                "pixel_truth_status": "available",
                                "exact_transmitter_input": "test",
                                "artifact": {"path": "truth/images/001-test.png"},
                            }
                        ],
                    }
                )
            )

            def write_manifest(
                mode: str,
                events: list[tuple[int, int]],
                picture_color: tuple[int, int, int] | None = None,
            ):
                path = root / f"{mode}.json"
                artifacts = []
                pictures = []
                if picture_color is not None:
                    artifact_dir = root / f"{mode}.artifacts"
                    artifact_dir.mkdir()
                    decoded = artifact_dir / "raster-0001.png"
                    Image.new("RGB", (3, 2), picture_color).save(decoded)
                    artifacts.append(
                        {"id": "raster-0001", "path": f"{mode}.artifacts/raster-0001.png"}
                    )
                    pictures.append(
                        {
                            "raster_artifact": "raster-0001",
                            "first_raster_input_sample": 30,
                            "header_text": "Pic:3x2C;",
                            "width": 3,
                            "height": 2,
                            "color": True,
                            "complete": True,
                            "samples_per_component": 8,
                            "damage_summary": {
                                "component_count": 18,
                                "clipped_count": 0,
                                "unstable_frequency_count": 0,
                                "threshold_calibrated": False,
                            },
                            "prologue_interval": {"start": 20, "stop": 30},
                            "end_alternatives": [
                                {
                                    "selected": True,
                                    "input_sample": 100,
                                }
                            ],
                            "first_trustworthy_resumed_text_input_sample": 110,
                            "reacquisition_evidence": {"status": "acquired"},
                            "return_to_text_reacquisition_interval": {
                                "start": 100,
                                "stop": 105,
                            },
                        }
                    )
                path.write_text(
                    json.dumps(
                        {
                            "decoder": {
                                "version": "test",
                                "configuration": {"mode": mode},
                            },
                            "input": {"sample_rate_hz": 10.0},
                            "timing": {
                                "wall_seconds": 2.0,
                                "cpu_seconds": 1.5,
                                "peak_rss_bytes": 100,
                            },
                            "diagnostics": {
                                "bytes_read": 1000,
                                "bytes_written": 100,
                                "peak_temporary_storage_bytes": 0,
                                "incremental_time_to_result_seconds": {},
                                "stage_wall_seconds": {},
                            },
                            "text_events": [
                                {
                                    "id": f"{mode}-{index}",
                                    "recognized_at_input_sample": sample,
                                    "octet": octet,
                                }
                                for index, (sample, octet) in enumerate(events)
                            ],
                            "mode_hypotheses": [
                                {
                                    "status": "accepted",
                                    "mode": event_mode,
                                    "event_interval": {
                                        "start": index * 10,
                                        "stop": index * 10 + 2,
                                    },
                                    "interval_uncertainty_samples": 1,
                                    "evidence": {
                                        "center_hz": 1500.0,
                                        "center_uncertainty_hz": 1.0,
                                        "rsid_code": 147 if event_mode == "MFSK32" else 620,
                                        "code_distance": 0,
                                    },
                                    "confidence": {
                                        "kind": "test",
                                        "value": 10.0,
                                        "calibrated": False,
                                    },
                                }
                                for index, event_mode in enumerate(
                                    ("MFSK32", "MFSK64", "MFSK32")
                                )
                            ],
                            "pictures": pictures,
                            "artifacts": artifacts,
                        }
                    )
                )
                return path

            mfsk32 = write_manifest(
                "MFSK32",
                [(1, 2), (2, ord("o")), (3, ord("n")), (4, ord("e")), (8, 4)],
                picture_color=(10, 20, 30),
            )
            mfsk64 = write_manifest(
                "MFSK64",
                [(5, ord(" ")), (6, ord("t")), (7, ord("w")), (7, ord("o"))],
                picture_color=(100, 110, 120),
            )
            output = root / "score.json"
            self.assertEqual(
                main(
                    [
                        "program-direct",
                        "--corpus",
                        str(corpus),
                        "--program",
                        "1",
                        "--transmission",
                        "test",
                        "--mfsk32-manifest",
                        str(mfsk32),
                        "--mfsk64-manifest",
                        str(mfsk64),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertEqual(
                result["execution_composition"]["status"], "two_pass_diagnostic"
            )
            self.assertTrue(result["text"]["exact"])
            self.assertTrue(result["acquisition"]["exact"])
            self.assertEqual(result["damage"]["clipped_count"], 0)
            self.assertEqual(result["transitions"]["return_to_text_acquired"], 1)
            self.assertEqual(
                result["operations"]["combined"]["wall_seconds_serial"], 4.0
            )
            self.assertEqual(
                result["pictures"][0]["pixel_score"][
                    "aligned_mean_absolute_error_255"
                ],
                0,
            )

    def test_baseline_summary_retains_hash_and_headline_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            score = root / "score.json"
            score.write_text(
                json.dumps(
                    {
                        "schema": "score.v1",
                        "status": "calibration",
                        "program_id": "1",
                        "transmission_id": "tx",
                        "decoder": "decoder",
                        "decoder_version": "1",
                        "text": {
                            "reference_characters": 10,
                            "decoded_characters": 9,
                            "substitutions": 1,
                            "deletions": 1,
                            "insertions": 0,
                            "character_error_rate": 0.2,
                            "reference_coverage": 0.8,
                        },
                        "picture_summary": {
                            "expected": 1,
                            "detected": 1,
                            "missed": 0,
                            "pixel_scored": 1,
                            "pixel_not_scored": 0,
                            "mean_aligned_mae_255_over_scored_pictures": 2.0,
                            "mean_raw_whole_raster": {
                                "mean_absolute_error_255": 3.0
                            },
                        },
                        "pictures": [
                            {
                                "pixel_score": {
                                    "status": "scored",
                                    "maximum_absolute_offset_components": 4,
                                    "offset_path_rle": [
                                        {
                                            "offset": -2,
                                            "start_component": 0,
                                            "stop_component": 10,
                                        },
                                        {
                                            "offset": 4,
                                            "start_component": 10,
                                            "stop_component": 12,
                                        },
                                    ],
                                }
                            }
                        ],
                        "alignment_parameters": {
                            "max_offset_components": 24,
                            "change_penalty": 25.0,
                            "offset_penalty": 0.0005,
                        },
                    }
                )
            )
            output = root / "summary.json"
            self.assertEqual(
                main(
                    [
                        "baseline-summary",
                        "--score",
                        str(score),
                        "--source-revision",
                        "abc123",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertEqual(result["source_revision"], "abc123")
            self.assertEqual(result["scorecard_count"], 1)
            self.assertEqual(len(result["records"][0]["scorecard_sha256"]), 64)
            self.assertEqual(len(result["program_summaries"]), 1)
            self.assertEqual(len(result["decoder_summaries"]), 1)
            decoder = result["decoder_summaries"][0]
            self.assertEqual(decoder["raw_image_mae_255"], 3.0)
            self.assertEqual(
                decoder["maximum_absolute_alignment_offset_components"], 4
            )
            self.assertEqual(
                decoder[
                    "maximum_absolute_dominant_alignment_offset_components"
                ],
                2,
            )

    def test_planning_gate_is_hierarchical_and_enforces_regression_limits(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            records = []
            for transmission, direct_cer in (("a", 0.08), ("b", 0.12)):
                for decoder, version, cer, detected, mae in (
                    ("direct", "dev", direct_cer, 9, 20.0),
                    ("fldigi", "recent", 0.10, 8, 25.0),
                ):
                    records.append(
                        {
                            "program_id": "1",
                            "transmission_id": transmission,
                            "decoder": decoder,
                            "decoder_version": version,
                            "receiver_family": "airspy",
                            "text": {"cer": cer},
                            "pictures": {
                                "detected": detected,
                                "expected": 10,
                                "aligned_mae_255": mae,
                            },
                        }
                    )
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema": "grampy-baseline-publication.v1",
                        "records": records,
                    }
                )
            )
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema": "grampy-fldigi-gate-policy.v1",
                        "policy_id": "test-v1",
                        "corpus_revision": "test",
                        "identities": {
                            "direct_decoder": {"name": "direct", "version": "dev"},
                            "fldigi": {"name": "fldigi", "version": "recent"},
                        },
                        "weights": {
                            "text_accuracy": 0.4,
                            "picture_event_recall": 0.3,
                            "pixel_fidelity": 0.3,
                        },
                        "pass_threshold": 0.0,
                        "catastrophic_regression_limits": {
                            "text_accuracy": 0.03,
                            "picture_event_recall": 0.05,
                            "pixel_fidelity": 0.05,
                        },
                    }
                )
            )
            output = root / "gate.json"
            self.assertEqual(
                main(
                    [
                        "planning-gate",
                        "--baseline",
                        str(baseline),
                        "--policy",
                        str(policy),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertTrue(result["computable"])
            self.assertTrue(result["passed"])
            self.assertEqual(len(result["programs"]), 1)
            self.assertEqual(result["receiver_subsets"][0]["receiver_family"], "airspy")

    def test_planning_gate_is_not_computable_with_an_unpaired_case(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema": "grampy-baseline-publication.v1",
                        "records": [
                            {
                                "program_id": "1",
                                "transmission_id": "a",
                                "decoder": "direct",
                                "decoder_version": "dev",
                                "text": {"cer": 0.1},
                                "pictures": {"detected": 1, "expected": 1, "aligned_mae_255": 10},
                            }
                        ],
                    }
                )
            )
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema": "grampy-fldigi-gate-policy.v1",
                        "policy_id": "test-v1",
                        "corpus_revision": "test",
                        "identities": {
                            "direct_decoder": {"name": "direct", "version": "dev"},
                            "fldigi": {"name": "fldigi", "version": "recent"},
                        },
                        "weights": {"text_accuracy": 0.4, "picture_event_recall": 0.3, "pixel_fidelity": 0.3},
                        "pass_threshold": 0.0,
                        "catastrophic_regression_limits": {"text_accuracy": 0.03, "picture_event_recall": 0.05, "pixel_fidelity": 0.05},
                    }
                )
            )
            output = root / "gate.json"
            self.assertEqual(main(["planning-gate", "--baseline", str(baseline), "--policy", str(policy), "--output", str(output)]), 0)
            result = json.loads(output.read_text())
            self.assertFalse(result["computable"])
            self.assertFalse(result["passed"])
            self.assertEqual(len(result["missing_pairs"]), 1)


if __name__ == "__main__":
    unittest.main()
