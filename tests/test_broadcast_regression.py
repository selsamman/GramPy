"""The full-broadcast gate must reject degradation and incomplete evidence."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader("broadcast_regression", str(Path(__file__).resolve().parents[1] / "tools/broadcast-regression"))
spec = importlib.util.spec_from_loader(loader.name, loader)
regression = importlib.util.module_from_spec(spec)
loader.exec_module(regression)


class BroadcastGateTests(unittest.TestCase):
    def test_changed_iq_with_same_file_size_fails_real_preflight(self):
        with tempfile.TemporaryDirectory() as name:
            corpus = Path(name)
            source = corpus / "sources/test"
            source.mkdir(parents=True)
            data = source / "capture.sigmf-data"
            data.write_bytes(b"original")
            item = {"path": data.name, "bytes": data.stat().st_size, "sha256": regression.digest(data)}
            (corpus / "corpus.json").write_text(json.dumps({"sources": [{"id": "test", "artifacts": {"data": item}}]}))
            data.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "changed corpus source"):
                regression.preflight(corpus, {"cases": [{"program": "1", "transmission": "test"}]})

    def test_worse_text_missing_picture_and_one_damaged_image_each_fail(self):
        baseline = {"text_cer": .1, "text_coverage": .9, "pictures_detected": 2,
                    "picture_1_raw_mae": 10, "picture_2_raw_mae": 30}
        self.assertEqual(regression.compare(baseline, baseline), [])
        for key, value in [("text_cer", .11), ("text_coverage", .89),
                           ("pictures_detected", 1), ("picture_1_raw_mae", 11)]:
            with self.subTest(key=key):
                current = dict(baseline, **{key: value})
                self.assertTrue(regression.compare(current, baseline))
        # An improvement in another picture cannot hide the damaged one.
        self.assertTrue(regression.compare(dict(baseline, picture_1_raw_mae=11, picture_2_raw_mae=1), baseline))

    def test_missing_or_nonfinite_metric_cannot_pass(self):
        for current, baseline in [({}, {"text_cer": .1}), ({"text_cer": float("nan")}, {"text_cer": .1}),
                                  ({"text_cer": .1}, {"text_cer": float("inf")})]:
            self.assertTrue(regression.compare(current, baseline))
        invalid_score = {"decoder": "radiogram-direct-iq", "text": {"character_error_rate": 0, "reference_coverage": 1},
                         "picture_summary": {"detected": 1, "pixel_scored": 0},
                         "pictures": [{"order": 1, "event_status": "detected", "completion_status": "complete",
                                       "pixel_score": {"status": "error_truth_artifact_missing"}}]}
        with self.assertRaisesRegex(ValueError, "uncomputable picture score"):
            regression.metrics(invalid_score)

    def test_missing_corpus_fails_before_any_decode_and_writes_failed_report(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            policy = root / "policy.json"
            policy.write_text('{"schema": "grampy-broadcast-policy.v1", "cases": [{"program": "1", "transmission": "test"}]}')
            with patch.object(regression, "run") as decode:
                self.assertEqual(regression.main(["--corpus", str(root / "missing"),
                    "--policy", str(policy), "--output", str(root / "out")]), 1)
                decode.assert_not_called()
            report = json.loads((root / "out/result.json").read_text())
            self.assertFalse(report["computable"])
            self.assertFalse(report["passed"])

    def test_changed_truth_or_reference_fails_before_decode(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            policy = root / "policy.json"
            policy.write_text('{"schema": "grampy-broadcast-policy.v1", "cases": [{"program": "1", "transmission": "test"}]}')
            baseline = root / "baseline.json"
            baseline.write_text(json.dumps({"schema": "grampy-broadcast-baseline.v1", "policy": json.loads(policy.read_text()), "inputs": {"truth": "old-hash"}}))
            with patch.object(regression, "preflight", return_value={"truth": "new-hash"}), patch.object(regression, "run") as decode:
                self.assertEqual(regression.main(["--policy", str(policy), "--baseline", str(baseline),
                                                 "--output", str(root / "out")]), 1)
                decode.assert_not_called()

    def test_workflow_returns_failure_for_degradation_and_review_status_for_changed_images(self):
        for degraded in (True, False):
            with self.subTest(degraded=degraded), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                source = root / "sources/test"
                source.mkdir(parents=True)
                (source / "capture.sigmf-meta").write_text('{"global": {"core:datatype": "ci16_le"}}')
                (source / "capture.sigmf-data").write_bytes(bytes(32))
                image = root / "image.png"
                image.write_bytes(b"new raster identity")
                policy = {"schema": "grampy-broadcast-policy.v1", "cases": [{"program": "1", "transmission": "test"}],
                          "decode_arguments": [], "score_arguments": [], "reference_id": "pinned"}
                policy_path = root / "policy.json"
                policy_path.write_text(json.dumps(policy))
                score = {"decoder": "radiogram-direct-iq", "text": {"character_error_rate": .2 if degraded else .1,
                         "reference_coverage": .9}, "picture_summary": {"detected": 1, "pixel_scored": 0},
                         "pictures": [{"order": 1, "event_status": "detected", "completion_status": "complete",
                                       "decoded_artifact": str(image), "pixel_score": {"status": "not_scored_missing_truth"}}]}
                bounds = regression.metrics(score)
                bounds["text_cer"] = .1
                baseline_path = root / "baseline.json"
                baseline_path.write_text(json.dumps({"schema": "grampy-broadcast-baseline.v1", "policy": policy,
                    "inputs": {}, "scores": {"test": {"grampy": bounds, "fldigi": bounds}},
                    "score_contracts": {"test": {"grampy": regression.score_contract(score), "fldigi": regression.score_contract(score)}},
                    "images": {"test": {"1": "old raster identity"}}}))

                def command(*arguments):
                    if "program-direct" in arguments or "program-fldigi" in arguments:
                        path = Path(arguments[arguments.index("--output") + 1])
                        regression.write(path, score)

                with patch.object(regression, "preflight", return_value={}), patch.object(regression, "run", side_effect=command), \
                        patch.object(regression, "source_revision", return_value="revision"):
                    code = regression.main(["--corpus", str(root), "--policy", str(policy_path), "--baseline", str(baseline_path),
                                            "--output", str(root / "out")])
                self.assertEqual(code, 1 if degraded else 3)
                report = json.loads((root / "out/result.json").read_text())
                self.assertFalse(report["passed"])
                self.assertEqual(report["automated_passed"], not degraded)
                self.assertTrue(report["human_review_required"])
