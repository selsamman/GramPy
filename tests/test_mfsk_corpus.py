from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from grampy.corpus import (
    build_inventory,
    promote,
    sha256_file,
    verify_corpus,
)


class ReceivedCorpusTests(unittest.TestCase):
    def make_capture(self, root: Path) -> Path:
        group = root / "reference-captures" / "wrmi-test"
        group.mkdir(parents=True)
        stem = group / "TEST-20260727T000000Z-10000000"
        samples = np.asarray([[100, -100], [0, 0], [32767, 1], [50, 25]], dtype="<i2")
        samples.tofile(stem.with_suffix(".sigmf-data"))
        stem.with_suffix(".sigmf-meta").write_text(
            json.dumps(
                {
                    "core:sample_rate": 2,
                    "frequency_hz": 10_000_000,
                    "start_utc": "2026-07-27T00:00:00Z",
                    "expected_output_bytes": 16,
                    "exit_status": 0,
                }
            ),
            encoding="utf-8",
        )
        return stem

    def test_inventory_measures_complete_capture_and_excludes_output(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            stem = self.make_capture(root)
            output = root / "reference-captures" / "output"
            output.mkdir()
            (output / "ignored.sigmf-data").write_bytes(b"")
            inventory = build_inventory(root / "reference-captures")
            self.assertEqual(inventory["capture_count"], 1)
            item = inventory["captures"][0]
            self.assertTrue(item["complete"])
            self.assertEqual(item["data_bytes"], 16)
            self.assertEqual(item["iq_metrics"]["sample_count"], 4)
            self.assertEqual(item["iq_metrics"]["zero_sample_fraction"], 0.25)
            self.assertEqual(item["data_sha256"], sha256_file(stem.with_suffix(".sigmf-data")))

    def test_promotion_is_self_contained_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            stem = self.make_capture(root)
            digest = sha256_file(stem.with_suffix(".sigmf-data"))
            selection = {
                "corpus_version": "test-v1",
                "sources": [
                    {
                        "id": "wrmi-test",
                        "intake_group": "wrmi-test",
                        "intake_stem": stem.name,
                        "data_sha256": digest,
                        "station": "WRMI",
                        "start_utc": "2026-07-27T00:00:00Z",
                        "frequency_hz": 10_000_000,
                        "partition": "development",
                        "quality_role": "clean",
                        "selection_reason": "test",
                    }
                ],
                "cases": [
                    {
                        "schema_version": 1,
                        "id": "case-1",
                        "source_capture_id": "wrmi-test",
                        "interval": {"start_sample": 0, "stop_sample": 4},
                    }
                ],
            }
            corpus = root / "corpus"
            manifest = promote(
                intake_root=root / "reference-captures",
                corpus_root=corpus,
                selection=selection,
            )
            self.assertEqual(manifest["storage"]["source_count"], 1)
            self.assertEqual(verify_corpus(corpus), [])

    def test_verifier_rejects_missing_scorecard(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            corpus = Path(name)
            (corpus / "corpus.json").write_text(
                json.dumps(
                    {
                        "sources": [],
                        "cases": [],
                        "scorecards": [
                            {
                                "path": "scores/missing.json",
                                "bytes": 10,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                )
            )
            self.assertEqual(
                verify_corpus(corpus),
                [f"missing scorecard: {corpus / 'scores/missing.json'}"],
            )
            self.assertFalse(
                any("reference-captures" in path.read_text(encoding="utf-8")
                    for path in corpus.rglob("*.json"))
            )

    def test_verifier_allows_explicitly_missing_picture_truth(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            corpus = Path(name)
            program = corpus / "programs" / "459"
            (program / "truth").mkdir(parents=True)
            (program / "truth" / "text-review.json").write_text("{}")
            (program / "program.json").write_text(
                json.dumps(
                    {
                        "id": "459",
                        "text_truth": {"review": "truth/text-review.json"},
                        "pictures": [
                            {
                                "order": 8,
                                "pixel_truth_status": "missing",
                                "artifact": None,
                            }
                        ],
                        "transmissions": [],
                    }
                )
            )
            (corpus / "corpus.json").write_text(
                json.dumps(
                    {
                        "sources": [],
                        "cases": [],
                        "programs": [
                            {"id": "459", "path": "programs/459/program.json"}
                        ],
                    }
                )
            )
            self.assertEqual(verify_corpus(corpus), [])


if __name__ == "__main__":
    unittest.main()
