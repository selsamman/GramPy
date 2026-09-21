from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import numpy as np

from grampy.picture_decode import PictureDecode
from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.text_decode import MFSKTextDecode


def _segment(identifier: str, mode: str, start: int, stop: int) -> dict:
    return {
        "id": identifier,
        "mode": mode,
        "orientation": "normal",
        "interval": {"start": start, "stop": stop},
        "endpoint_uncertainty_samples": 10,
        "source": "rsid",
        "confidence": {"kind": "test", "value": 1.0, "calibrated": False},
        "supporting_events": [],
        "acquisition_state": "candidate",
        "symbol_phase_uncertainty_input_samples": 1,
        "superseded_alternatives": [],
        "center_hz": 1500.0,
        "frequency_track": 0,
    }


def _event(identifier: str, value: int, sample: int, segment: str) -> dict:
    role = "STX" if value == 2 else "EOT" if value == 4 else None
    return {
        "id": identifier,
        "octet": value,
        "display": None if role else chr(value),
        "control_role": role,
        "codeword": "1",
        "wire_interval": {"start": sample - 1, "stop": sample},
        "recognized_at_input_sample": sample,
        "confidence": {"kind": "test", "value": 1.0},
        "damage_flags": [],
        "mode_segment": segment,
        "provenance": {"text_epoch": None},
    }


def _decoded(mode: str, segment: str, events: list[dict]) -> MFSKTextDecode:
    octets = [
        event["octet"] for event in events if event["control_role"] is None
    ]
    return MFSKTextDecode(
        mode_segment={
            "id": f"summary-{mode}",
            "mode": mode,
            "orientation": "normal",
            "interval": {"start": 0, "stop": 20_000},
            "source": "test",
            "confidence": {"kind": "test", "value": 1.0},
            "acquisition_state": "locked",
            "symbol_phase_uncertainty_input_samples": 1,
            "center_hz": 1500.0,
        },
        text_events=events,
        text_summary={
            "octets": octets,
            "text": bytes(octets).decode("latin-1"),
            "framing": {
                "stx_found": any(event["control_role"] == "STX" for event in events),
                "eot_found": any(event["control_role"] == "EOT" for event in events),
            },
        },
        diagnostics={
            "tone_evidence": {
                "acquisition_candidates": [],
                "frequency_track": {
                    "lock_loss_count": 0,
                    "reacquisition_count": 0,
                },
            },
            "bit_evidence": {"erasure_count": 0},
            "varicode_evidence": {
                "event_count": len(events),
                "invalid_count": 0,
            },
            "bounded_organization": {
                "maximum_materialized_iq_samples": 1000,
                "first_stable_text_wall_seconds": 0.1,
            },
        },
        text_epochs=[],
    )


class AutomaticSegmentedDecodeTests(unittest.TestCase):
    def test_auto_dispatches_both_modes_and_publishes_picture(self) -> None:
        segments = (
            _segment("mode-32-a", "MFSK32", 0, 5_000),
            _segment("mode-64", "MFSK64", 5_000, 15_000),
            _segment("mode-32-b", "MFSK32", 15_000, 20_000),
        )
        acquisition = SimpleNamespace(
            regions=(), mode_hypotheses=(), mode_segments=segments,
            frequency_tracks=(),
        )
        mfsk32 = _decoded(
            "MFSK32",
            "mode-32-a",
            [
                _event("text-1", 2, 1_000, "mode-32-a"),
                _event("text-2", ord("A"), 2_000, "mode-32-a"),
                _event("text-3", 4, 19_000, "mode-32-b"),
            ],
        )
        mfsk64 = _decoded(
            "MFSK64",
            "mode-64",
            [_event("text-1", ord("B"), 8_000, "mode-64")],
        )
        picture = PictureDecode(
            pictures=[{
                "id": "picture-0001",
                "prologue_interval": {"start": 9_000, "stop": 9_100},
                "end_alternatives": [{"input_sample": 9_500, "selected": True}],
            }],
            transitions=[],
            artifacts=[],
            diagnostics={
                "header_candidates": 1,
                "header_rejections": 0,
                "picture_count": 1,
                "clipped_components": 0,
                "damaged_components": 0,
                "persistent_artifact_files": 0,
                "artifact_bytes": 0,
                "maximum_materialized_iq_samples": 1000,
                "requested_read_samples": 1000,
                "requested_read_bytes": 8000,
                "first_picture_descriptor_wall_seconds": 0.2,
                "first_complete_picture_wall_seconds": 0.3,
            },
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meta = root / "capture.sigmf-meta"
            data = root / "capture.sigmf-data"
            np.zeros(20_000, dtype="<c8").tofile(data)
            meta.write_text(json.dumps({
                "global": {"core:datatype": "cf32_le", "core:sample_rate": 8_000},
                "captures": [{"core:sample_start": 0}],
                "annotations": [],
            }), encoding="utf-8")
            with (
                mock.patch("grampy.pipeline.acquire_modes", return_value=acquisition),
                mock.patch(
                    "grampy.pipeline._decode_bounded_text",
                    side_effect=[mfsk32, mfsk64],
                ) as decode_text,
                mock.patch(
                    "grampy.pipeline._decode_bounded_pictures",
                    return_value=picture,
                ) as decode_pictures,
            ):
                manifest = run_reference_pipeline(
                    meta_path=meta,
                    data_path=data,
                    start_sample=None,
                    stop_sample=None,
                    config=DecodeConfig(),
                )

        self.assertEqual([call.args[2].mode for call in decode_text.call_args_list], [
            "MFSK32", "MFSK64"
        ])
        self.assertEqual(decode_pictures.call_args.kwargs["mode"], "MFSK64")
        self.assertEqual([item["mode"] for item in manifest["mode_segments"]], [
            "MFSK32", "MFSK64", "MFSK32"
        ])
        self.assertEqual(manifest["text_summary"]["text"], "AB")
        self.assertEqual(len(manifest["pictures"]), 1)
        self.assertNotIn(
            "segmented-payload-decode-deferred",
            {warning["code"] for warning in manifest["warnings"]},
        )


if __name__ == "__main__":
    unittest.main()
