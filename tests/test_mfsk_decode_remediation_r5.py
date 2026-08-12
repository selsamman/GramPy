from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest import mock

from grampy.pipeline import DecodeConfig, run_reference_pipeline


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json").read_text(encoding="utf-8")
)


class BoundedPipelineTests(unittest.TestCase):
    def test_controlled_text_can_use_bounded_organization(self) -> None:
        fixture = next(
            item for item in EVIDENCE["fixtures"]
            if item["id"] == "mfsk32-text-printable"
        )
        fixture_root = Path(
            os.environ.get(
                "GRAM_PY_MFSK_FIXTURES",
                ROOT / ".local" / "fldigi-fixtures",
            )
        ) / fixture["artifact_directory"]
        meta = fixture_root / fixture["artifacts"]["sigmf_meta"]
        data = fixture_root / fixture["artifacts"]["sigmf_data"]
        if not meta.exists() or not data.exists():
            self.skipTest("controlled MFSK fixture unavailable")

        with mock.patch(
            "grampy.pipeline.BOUNDED_PIPELINE_THRESHOLD_SECONDS", 0.0
        ):
            manifest = run_reference_pipeline(
                meta_path=meta,
                data_path=data,
                start_sample=None,
                stop_sample=None,
                config=DecodeConfig(
                    mode="MFSK32",
                    center_hz=1500.0,
                    orientation="normal",
                    trace_level="summary",
                ),
            )

        self.assertEqual(
            manifest["diagnostics"]["working_set_organization"],
            "p11d_bounded_text_and_picture_ranges",
        )
        self.assertEqual(
            manifest["text_summary"]["text"], fixture["decoded_text"]
        )
        bounded = manifest["diagnostics"]["text_pipeline"][
            "bounded_organization"
        ]
        self.assertEqual(
            bounded["kind"], "p11d_compact_tracks_and_stateful_text_pass"
        )
        self.assertLessEqual(
            bounded["maximum_materialized_iq_samples"],
            manifest["input"]["requested_interval"]["stop"]
            - manifest["input"]["requested_interval"]["start"],
        )


if __name__ == "__main__":
    unittest.main()
