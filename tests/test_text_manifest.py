"""Consumer text product without changing the underlying MFSK decode."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from grampy.text_manifest import build_text_manifest


def _event(identifier: str, octet: int | None, sample: int) -> dict:
    role = {2: "STX", 4: "EOT"}.get(octet)
    return {
        "id": identifier,
        "octet": octet,
        "control_role": role,
        "wire_interval": {"start": sample - 5, "stop": sample},
        "recognized_at_input_sample": sample,
        "mode_segment": "mode-64",
    }


def _source(events: list[dict], pictures: list[dict] | None = None) -> dict:
    return {
        "run_id": "0" * 24,
        "status": "complete",
        "decoder": {"version": "test", "configuration": {"mode": "MFSK64"}},
        "input": {
            "metadata_sha256": "a" * 64,
            "data_sha256": "b" * 64,
            "sample_rate_hz": 100,
            "requested_interval": {"start": 0, "stop": 1000},
        },
        "mode_segments": [{
            "id": "mode-64", "mode": "MFSK64",
            "interval": {"start": 0, "stop": 1000},
        }],
        "text_events": events,
        "pictures": pictures or [],
        "artifacts": ([{
            "id": "raster-0001", "kind": "png_uint8_raster",
            "path": "pictures/raster-0001.png", "sha256": "c" * 64,
        }] if pictures else []),
        "warnings": [],
    }


class TextManifestTests(unittest.TestCase):
    def test_complete_frame_spans_picture_and_links_to_introductory_text(self) -> None:
        events = [
            _event("noise", ord("x"), 20),
            _event("stx", 2, 100),
            _event("h", ord("H"), 150),
            _event("i", ord("i"), 200),
            _event("false-picture-text", ord("Z"), 350),
            _event("o", ord("o"), 500),
            _event("k", ord("k"), 550),
            _event("eot", 4, 600),
        ]
        picture = {
            "id": "picture-0001", "mode": "MFSK64",
            "prologue_interval": {"start": 300, "stop": 320},
            "end_alternatives": [{"input_sample": 450, "selected": True}],
            "raster_artifact": "raster-0001", "header_event_ids": ["h", "i"],
            "header_text": "Pic:1x1;", "width": 1, "height": 1,
            "color": False, "complete": True,
        }
        result = build_text_manifest(_source(events, [picture]))
        items = result["mode_segments"][0]["items"]

        self.assertEqual([item["kind"] for item in items], ["text", "picture", "text"])
        self.assertEqual([items[0]["text"], items[2]["text"]], ["Hi", "ok"])
        self.assertEqual(items[0]["frame_id"], items[2]["frame_id"])
        self.assertEqual(items[0]["framing"], "complete_stx_eot")
        self.assertEqual(items[1]["associated_text_item_id"], items[0]["id"])
        self.assertEqual(items[1]["artifact"]["path"], "pictures/raster-0001.png")
        self.assertEqual(result["omitted_unframed"][0]["reason"], "before_stx")
        self.assertEqual(result["omitted_unframed"][1]["reason"], "inside_picture")
        self.assertNotIn("text_events", result)

    def test_unframed_text_is_retained_when_no_stx_is_detected(self) -> None:
        source = _source([_event("a", ord("A"), 100)])
        source["status"] = "partial"
        result = build_text_manifest(source)

        self.assertEqual(result["mode_segments"][0]["items"][0]["text"], "A")
        self.assertEqual(result["mode_segments"][0]["items"][0]["framing"], "uncertain")
        self.assertEqual(result["omitted_unframed"], [])
        self.assertEqual(result["status"], "partial")

    def test_utf8_quotes_and_accent_with_invalid_octet_preserved(self) -> None:
        payload = b'\xe2\x80\x9cSilver Age\xe2\x80\x9d caf\xc3\xa9 \xe9'
        events = [_event("stx", 2, 50)]
        events.extend(
            _event(f"byte-{index}", octet, 100 + index * 5)
            for index, octet in enumerate(payload)
        )
        events.append(_event("eot", 4, 100 + len(payload) * 5))

        result = build_text_manifest(_source(events))
        item = result["mode_segments"][0]["items"][0]
        self.assertEqual(item["text"], '“Silver Age” café é')
        self.assertEqual(item["framing"], "complete_stx_eot")

    def test_full_broadcast_reference_has_ordered_modes_and_nine_images(self) -> None:
        root = Path(__file__).parent / "samples/received-corpus/references"
        reference = (
            root / "wrmi-20260923T133007Z-15770000"
            / "grampy-0.2.0-reference/decode.manifest.json"
        )
        if not reference.is_file():
            self.skipTest("optional full-broadcast reference unavailable")
        result = build_text_manifest(json.loads(reference.read_text()))
        self.assertEqual(
            [item["mode"] for item in result["mode_segments"]],
            ["MFSK32", "MFSK64", "MFSK32"],
        )
        pictures = [
            item for segment in result["mode_segments"]
            for item in segment["items"] if item["kind"] == "picture"
        ]
        self.assertEqual(len(pictures), 9)
        self.assertTrue(all(item["associated_text_item_id"] for item in pictures))
        self.assertTrue(all((reference.parent / item["artifact"]["path"]).is_file() for item in pictures))
        self.assertLess(len(json.dumps(result).encode()), 250_000)
        all_text = "".join(
            item["text"] for segment in result["mode_segments"]
            for item in segment["items"] if item["kind"] == "text"
        )
        self.assertIn("“Silver Age”", all_text)
        self.assertNotIn("â\x80\x9cSilver Age", all_text)


if __name__ == "__main__":
    unittest.main()
