"""Independent checks for the source-derived RSID candidate evidence."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ORACLE = (
    Path(__file__).resolve().parents[1]
    / "docs/encoder/data/mfsk_encoder_rsid_oracle_v1.json"
)


def _gf16_product(left: int, right: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & 16:
            left ^= 0x19  # x^4 + x^3 + 1
    return product & 15


def _word(code: int) -> list[int]:
    symbols = [code >> 8, (code >> 4) & 15, code & 15] + [0] * 12
    for factor in (2, 4, 8, 9, 11, 15, 7, 14, 5, 10, 13, 3):
        prior = symbols[:]
        symbols[0] = _gf16_product(prior[0], factor)
        for index in range(1, 15):
            symbols[index] = prior[index - 1] ^ _gf16_product(prior[index], factor)
    return symbols


class RsidOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = json.loads(ORACLE.read_text(encoding="utf-8"))

    def test_frozen_words_cover_primary_and_extended_identifiers(self) -> None:
        self.assertEqual(self.oracle["source"]["tag"], "v4.2.12")
        self.assertEqual(
            self.oracle["source"]["commit"],
            "b0032cabb70dc670064ed7561b9a626010a5e4ae",
        )
        self.assertEqual(self.oracle["field"]["native_pcm_peak"], 16_384)
        words = self.oracle["words"]
        for name, code in (("MFSK32", 147), ("escape", 6), ("MFSK64", 620)):
            self.assertEqual(words[name]["tones"], _word(code))
            self.assertEqual(len(words[name]["tones"]), 15)
        altered = words["MFSK64"]["tones"][:]
        altered[5] ^= 1
        self.assertNotEqual(altered, _word(620))

    def test_48k_prefix_intervals_are_contiguous_and_exact(self) -> None:
        oracle = self.oracle
        self.assertEqual(oracle["schema"], "grampy-mfsk-encoder-rsid-oracle.v1")
        period = (48_000 * 1024) // 11025
        self.assertEqual(period, oracle["frame_counts_at_48000_hz"]["frames_per_symbol"])
        for mode, expected_periods in (("MFSK32", 25), ("MFSK64", 50)):
            intervals = oracle["frame_counts_at_48000_hz"][mode]
            cursor = 0
            for part in oracle["sequence_symbol_periods"][mode]:
                start, end = intervals[part["kind"]]
                self.assertEqual(start, cursor)
                self.assertEqual(end - start, part["count"] * period)
                cursor = end
            self.assertEqual(cursor, expected_periods * period)
            self.assertEqual(cursor, intervals["total"])


if __name__ == "__main__":
    unittest.main()
