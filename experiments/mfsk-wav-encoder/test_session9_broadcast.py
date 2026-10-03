"""Guard the practical gate against blank, wrong-geometry and reordered results."""
import json
from pathlib import Path
import unittest

import numpy as np

from session9_broadcast import picture_score, protocol_text, text_in_order


class PracticalGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = json.loads(Path("docs/encoder/data/mfsk_encoder_pi_matrix_v3.json").read_text())["picture_gate"]
        cls.truth = np.tile(np.arange(160, dtype=np.uint8), (120, 1))

    def test_blank_is_rejected(self):
        self.assertFalse(picture_score(self.truth, np.zeros_like(self.truth), self.gate)["pass"])

    def test_wrong_geometry_is_rejected(self):
        self.assertFalse(picture_score(self.truth, self.truth[:119], self.gate)["pass"])

    def test_large_colour_bias_is_rejected(self):
        observed = np.clip(self.truth.astype(int) + 20, 0, 255).astype(np.uint8)
        result = picture_score(self.truth, observed, self.gate)
        self.assertTrue(result["checks"]["raw_mae"])
        self.assertFalse(result["checks"]["channel_bias"])
        self.assertFalse(result["pass"])

    def test_modest_non_exact_output_is_allowed(self):
        observed = self.truth + 2
        self.assertTrue(picture_score(self.truth, observed, self.gate)["pass"])

    def test_reordered_text_is_rejected(self):
        self.assertFalse(text_in_order("END HEADER BEGIN", ["BEGIN", "HEADER", "END"]))
        self.assertFalse(text_in_order("BEGIN END", ["BEGIN", "HEADER", "END"]))
        self.assertTrue(text_in_order("noise BEGIN HEADER END noise", ["BEGIN", "HEADER", "END"]))

    def test_protocol_checks_retain_controls_omitted_from_display_summary(self):
        manifest = {"text_summary": {"text": "A", "octets": [65]},
                    "text_events": [{"octet": 2}, {"octet": 65}, {"octet": 4}, {"octet": None}]}
        self.assertEqual(protocol_text(manifest), "\x02A\x04")
        self.assertTrue(text_in_order(protocol_text(manifest), ["\x02A\x04"]))


if __name__ == "__main__":
    unittest.main()
