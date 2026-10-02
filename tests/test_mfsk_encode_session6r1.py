"""Independent RSID waveform checks; no GramPy receiver is an oracle."""

import io
import json
import math
from pathlib import Path
import unittest
from unittest import mock
import tracemalloc

import numpy as np

from grampy.rsid_encode import _plan_rsid_prefix, _write_rsid_prefix


ORACLE = json.loads((Path(__file__).resolve().parents[1]
    / "docs/encoder/data/mfsk_encoder_rsid_oracle_v1.json").read_text())


def reference_pcm(mode, carrier, rate):
    """Integrate frozen source frequencies analytically, independently of writer."""
    period = rate * 1024 // 11025
    blocks = []
    for interval in ORACLE["sequence_symbol_periods"][mode]:
        kind = interval["kind"]
        if "silence" in kind:
            blocks.append(np.zeros(period * interval["count"], dtype="<i2"))
            continue
        name = {"primary_147": "MFSK32", "primary_escape_6": "escape",
                "secondary_620": "MFSK64"}[kind]
        phase = 0.0
        for tone in ORACLE["words"][name]["tones"]:
            step = 2 * math.pi * (carrier + (tone - 7) * 11025 / 1024) / rate
            phases = phase + step * np.arange(1, period + 1)
            blocks.append(np.rint(16384 * np.sin(phases)).astype("<i2"))
            phase = (phase + step * period) % (2 * math.pi)
    return np.concatenate(blocks).tobytes()


def render(mode="MFSK64", carrier=1500.0, rate=48000):
    sink = io.BytesIO()
    frames = _write_rsid_prefix(sink, mode=mode, carrier_hz=carrier, sample_rate_hz=rate)
    return frames, sink.getvalue()


class Session6R1Tests(unittest.TestCase):
    def test_streaming_peak_memory_is_bounded_at_maximum_rate(self):
        class DiscardSink:
            def write(self, pcm):
                return len(pcm)

        tracemalloc.start()
        try:
            for _ in range(3):
                _write_rsid_prefix(DiscardSink(), mode="MFSK64", carrier_hz=1500,
                                   sample_rate_hz=192000)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        # A maximum-rate symbol is 17,832 frames (35,664 PCM bytes).
        # Even three successive prefixes must not retain whole-prefix PCM.
        self.assertLess(peak, 256 * 1024)

    def test_complete_pcm_matches_independent_oracle_at_multiple_carriers(self):
        for mode in ("MFSK32", "MFSK64"):
            for carrier in (700.0, 1500.0, 2317.25):
                with self.subTest(mode=mode, carrier=carrier):
                    frames, actual = render(mode, carrier)
                    self.assertEqual(frames, ORACLE["frame_counts_at_48000_hz"][mode]["total"])
                    self.assertEqual(actual, reference_pcm(mode, carrier, 48000))

    def test_every_supported_rate_has_exact_frames_and_symbol_bounded_writes(self):
        class CountingSink:
            def __init__(self):
                self.lengths = []

            def write(self, pcm):
                self.lengths.append(len(pcm))
                return len(pcm)

        for rate in range(8000, 192001, 8000):
            for mode, periods in (("MFSK32", 25), ("MFSK64", 50)):
                with self.subTest(rate=rate, mode=mode):
                    sink = CountingSink()
                    plan = _plan_rsid_prefix(mode=mode, carrier_hz=1500, sample_rate_hz=rate)
                    frames = _write_rsid_prefix(sink, mode=mode, carrier_hz=1500, sample_rate_hz=rate)
                    self.assertEqual(plan.frames_per_symbol, rate * 1024 // 11025)
                    self.assertEqual(frames, periods * (rate * 1024 // 11025))
                    self.assertEqual(plan.frame_count, frames)
                    self.assertEqual(sink.lengths, [2 * plan.frames_per_symbol] * periods)
        for rate in (8000, 192000):
            for mode in ("MFSK32", "MFSK64"):
                self.assertEqual(render(mode, rate=rate)[1], reference_pcm(mode, 1500, rate))

    def test_guards_phase_reset_and_no_envelope(self):
        for mode in ("MFSK32", "MFSK64"):
            samples = np.frombuffer(render(mode)[1], dtype="<i2")
            intervals = ORACLE["frame_counts_at_48000_hz"][mode]
            for kind, bounds in intervals.items():
                if kind == "total":
                    continue
                start, stop = bounds
                if "silence" in kind:
                    self.assertFalse(np.any(samples[start:stop]))
                else:
                    name = {"primary_147": "MFSK32", "primary_escape_6": "escape",
                            "secondary_620": "MFSK64"}[kind]
                    frequency = 1500 + (ORACLE["words"][name]["tones"][0] - 7) * 11025 / 1024
                    self.assertEqual(samples[start], round(16384 * math.sin(math.tau * frequency / 48000)))
                    self.assertEqual(np.max(np.abs(samples[start:stop].astype(np.int32))), 16384)

    def test_oracle_rejects_tone_carrier_timing_phase_and_level_mutations(self):
        import grampy.rsid_encode as encoder

        expected = reference_pcm("MFSK64", 1500, 48000)
        mutated = dict(encoder._WORDS)
        tones = list(mutated["MFSK64"])
        tones[5] ^= 1
        mutated["MFSK64"] = tuple(tones)
        with mock.patch.object(encoder, "_WORDS", mutated):
            self.assertNotEqual(render()[1], expected)
        self.assertNotEqual(render(carrier=1500 + 11025 / 2048)[1], expected)
        with mock.patch.object(encoder, "_SPACING_HZ", 11.0):
            self.assertNotEqual(render()[1], expected)
        with mock.patch.object(encoder, "_PCM_PEAK", 16000):
            self.assertNotEqual(render()[1], expected)
        actual = render()[1]
        self.assertNotEqual(actual[:-2], expected)
        # Replace the first sample of the secondary word by a pre-increment
        # phase-zero sample, and independently remove one bridge guard frame.
        boundary = ORACLE["frame_counts_at_48000_hz"]["MFSK64"]["secondary_620"][0] * 2
        self.assertNotEqual(actual[:boundary] + b"\0\0" + actual[boundary + 2:], expected)
        self.assertNotEqual(actual[:boundary - 2] + actual[boundary:], expected)

    def test_invalid_preflight_and_sink_failures(self):
        for field, values in (
            ("mode", ("MFSK16", None)),
            ("sample_rate_hz", (True, 7999, 48001, 200000)),
            ("carrier_hz", (True, float("nan"), float("inf"), 0, 3999)),
        ):
            for value in values:
                args = dict(mode="MFSK64", sample_rate_hz=8000, carrier_hz=1500)
                args[field] = value
                sink = io.BytesIO()
                with self.assertRaises(ValueError):
                    _write_rsid_prefix(sink, **args)
                self.assertEqual(sink.getvalue(), b"")
        sink = mock.Mock()
        sink.write.return_value = 1
        with self.assertRaisesRegex(OSError, "short RSID write"):
            _write_rsid_prefix(sink, mode="MFSK32", carrier_hz=1500, sample_rate_hz=48000)
        sink.write.side_effect = OSError("injected sink failure")
        with self.assertRaisesRegex(OSError, "injected sink failure"):
            _write_rsid_prefix(sink, mode="MFSK64", carrier_hz=1500, sample_rate_hz=48000)


if __name__ == "__main__":
    unittest.main()
