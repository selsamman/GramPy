from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

import numpy as np

from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.wire import (
    convolutional_encode,
    parse_varicode,
    soft_viterbi_decode,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json").read_text(encoding="utf-8")
)
VARICODE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_varicode.json").read_text(encoding="utf-8")
)["encodings"]


class Session3WireTests(unittest.TestCase):
    def test_soft_viterbi_recovers_fixed_encoded_bits(self) -> None:
        bits = tuple(map(int, "001011001011101000111010001"))
        coded = convolutional_encode(bits)
        llrs = np.asarray([18.0 if bit else -18.0 for bit in coded])
        result = soft_viterbi_decode(llrs)
        self.assertEqual(result.bits, bits)
        self.assertGreaterEqual(result.path_metric_gap, 0.0)

    def test_varicode_parser_uses_lookahead_and_retains_invalid_words(self) -> None:
        stream = VARICODE[101] + VARICODE[32] + VARICODE[116] + "1"
        events = parse_varicode(tuple(map(int, stream)))
        self.assertEqual([event.octet for event in events], [101, 32, 116])
        invalid = parse_varicode(tuple(map(int, "0001")))
        self.assertEqual(len(invalid), 1)
        self.assertIsNone(invalid[0].octet)
        self.assertEqual(invalid[0].codeword, "000")


class ControlledMFSK32VerticalSliceTests(unittest.TestCase):
    def test_pinned_iq_decodes_to_exact_final_octets_with_coordinates(self) -> None:
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
            self.skipTest(
                "controlled MFSK fixtures unavailable; set GRAM_PY_MFSK_FIXTURES"
            )

        manifest = run_reference_pipeline(
            meta_path=meta,
            data_path=data,
            start_sample=None,
            stop_sample=None,
            config=DecodeConfig(trace_level="events"),
        )

        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["input"]["data_sha256"], fixture["sigmf_data_sha256"])
        self.assertEqual(manifest["text_summary"]["text"], fixture["decoded_text"])
        self.assertEqual(
            bytes(manifest["text_summary"]["octets"]),
            fixture["decoded_text"].encode("ascii"),
        )
        self.assertEqual(manifest["mode_segments"][0]["mode"], "MFSK32")
        self.assertEqual(manifest["mode_segments"][0]["orientation"], "normal")
        self.assertAlmostEqual(manifest["mode_segments"][0]["center_hz"], 1500.0)
        roles = [event["control_role"] for event in manifest["text_events"]]
        self.assertIn("STX", roles)
        self.assertIn("EOT", roles)
        for event in manifest["text_events"]:
            interval = event["wire_interval"]
            self.assertLessEqual(interval["start"], interval["stop"])
            self.assertLessEqual(
                interval["stop"], event["recognized_at_input_sample"]
            )
            self.assertEqual(event["mode_segment"], "mode-0001")

        diagnostics = manifest["diagnostics"]["text_pipeline"]
        self.assertGreater(diagnostics["tone_evidence"]["symbol_count"], 0)
        self.assertGreater(diagnostics["bit_evidence"]["coded_llr_count"], 0)
        self.assertGreater(diagnostics["fec_evidence"]["decoded_bit_count"], 0)
        self.assertGreater(diagnostics["varicode_evidence"]["event_count"], 0)
        self.assertEqual(manifest["diagnostics"]["persistent_intermediate_files"], 0)


if __name__ == "__main__":
    unittest.main()
