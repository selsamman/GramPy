"""RSID composition contracts and coupled whole-file auto-acquisition smoke.

Frozen-source PCM is independent evidence. GramPy receiving a full Hilbert
transform of its own WAV is coupled evidence, never fldigi qualification.
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np
from scipy import signal

from grampy import api
from grampy.mfsk_compose import _preflight, _snapshot_parts
from grampy.mfsk_encode import ContinuousPhaseToneWriter
from grampy.mfsk_segment_encode import _write_segment, plan_mfsk_segment
from tests.test_mfsk_encode_session6 import _wav_pcm, _write_audio
from tests.test_mfsk_encode_session6r1 import reference_pcm


class Session6R2Tests(unittest.TestCase):
    def test_prefix_and_existing_mfsk_pcm_join_exactly_without_extra_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "out.wav"
            for mode in ("MFSK32", "MFSK64"):
                for rate in (8000, 48000, 192000):
                    with self.subTest(mode=mode, rate=rate):
                        carrier = 1731.25
                        part = api.MfskSegment((api.TextPart(b"JOIN"),), mode, carrier)
                        result = api.encode_mfsk_wav(parts=(part,), output_path=output,
                                                     config=api.EncodeConfig(rate))
                        sink = io.BytesIO()
                        writer = ContinuousPhaseToneWriter(sink, mode=mode,
                            carrier_hz=carrier, sample_rate_hz=rate)
                        _write_segment(writer, contents=(b"JOIN",), mode=mode,
                            carrier_hz=carrier, sample_rate_hz=rate)
                        writer.finish()
                        expected = reference_pcm(mode, carrier, rate) + sink.getvalue()
                        self.assertEqual(_wav_pcm(output), expected)
                        self.assertEqual(result.duration_seconds, len(expected) // 2 / rate)
                        self.assertEqual(result.segments[0].start_seconds, 0)

    def test_empty_items_and_every_rate_include_each_prefix_in_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.wav"
            for rate in range(8000, 192001, 8000):
                for mode, periods in (("MFSK32", 25), ("MFSK64", 50)):
                    with self.subTest(mode=mode, rate=rate):
                        part = api.MfskSegment((api.TextPart(b""), api.TextPart(b"")), mode)
                        parts = _snapshot_parts((part, part))
                        items, starts, total = _preflight(parts, output, rate)
                        baseline = plan_mfsk_segment(contents=(b"", b""), mode=mode,
                            carrier_hz=1500, sample_rate_hz=rate)
                        prefix = periods * (rate * 1024 // 11025)
                        frames = prefix + baseline.frame_count
                        self.assertEqual([item.frame_count for item in items], [frames, frames])
                        self.assertEqual(total, 2 * frames)
                        self.assertEqual(starts[1].start_seconds, frames / rate)
                        for index, start in enumerate(starts):
                            expected = (index * frames + prefix + baseline.content_start_frames[0]) / rate
                            self.assertEqual([c.start_seconds for c in start.contents], [expected, expected])

    def test_riff_ceiling_counts_prefix_for_empty_and_repeated_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.wav"
            part = api.MfskSegment((api.TextPart(b""),), "MFSK64")
            baseline = plan_mfsk_segment(contents=(b"",), mode="MFSK64",
                carrier_hz=1500, sample_rate_hz=48000).frame_count
            for count in (1, 2):
                output.write_bytes(b"KEEP")
                ceiling = count * (baseline + 222900) - 1
                with patch("grampy.mfsk_compose.MAX_WAV_FRAMES", ceiling):
                    with self.assertRaisesRegex(ValueError, "RIFF/WAVE limit"):
                        api.encode_mfsk_wav(parts=(part,) * count, output_path=output)
                self.assertEqual(output.read_bytes(), b"KEEP")

    def test_prefix_failure_and_accounting_mismatch_remove_replaced_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.wav"
            part = api.MfskSegment((api.TextPart(b"x"),))
            for error in (OSError("RSID sink failure"), KeyboardInterrupt()):
                output.write_bytes(b"OLD")
                def fail_after_guard(sink, **kwargs):
                    sink.write(bytes(4458 * 2))
                    raise error
                with patch("grampy.mfsk_compose._write_rsid_prefix", fail_after_guard):
                    with self.assertRaises(type(error)):
                        api.encode_mfsk_wav(parts=(part,), output_path=output)
                self.assertFalse(output.exists())
            output.write_bytes(b"OLD")
            with patch("grampy.mfsk_compose._write_rsid_prefix", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "RSID frame counts disagree"):
                    api.encode_mfsk_wav(parts=(part,), output_path=output)
            self.assertFalse(output.exists())
            output.write_bytes(b"OLD")
            with patch("grampy.mfsk_compose._write_segment", side_effect=OSError("payload failed")):
                with self.assertRaisesRegex(OSError, "payload failed"):
                    api.encode_mfsk_wav(parts=(part,), output_path=output)
            self.assertFalse(output.exists())

    def test_repeated_empty_segments_each_emit_complete_prefix_and_framing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "empty.wav"
            for mode in ("MFSK32", "MFSK64"):
                part = api.MfskSegment((api.TextPart(b""), api.TextPart(b"")), mode)
                result = api.encode_mfsk_wav(parts=(part, part), output_path=output)
                pcm = _wav_pcm(output)
                midpoint = round(result.segments[1].start_seconds * 48000) * 2
                prefix = reference_pcm(mode, 1500, 48000)
                self.assertEqual(pcm[:midpoint], pcm[midpoint:])
                self.assertEqual(pcm[:len(prefix)], prefix)
                self.assertEqual(pcm[midpoint:midpoint + len(prefix)], prefix)
                self.assertEqual(result.duration_seconds, len(pcm) // 2 / 48000)

    def test_whole_wav_auto_acquisition_and_payload_recovery(self):
        # Each input is acquired once from its entire WAV, without mode/carrier
        # hints or caller timestamp windows. Same-mode cases also retune.
        for modes in (("MFSK32", "MFSK64"), ("MFSK64", "MFSK32"),
                      ("MFSK32", "MFSK32"), ("MFSK64", "MFSK64")):
            for spaced in (False, True):
                with self.subTest(modes=modes, spaced=spaced), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    audio = root / "audio.wav"
                    audio_pcm = _write_audio(audio, (123, -456, 789, 0) * 1200)
                    payloads = (b"FIRST NATIVE RSID MESSAGE", b"SECOND NATIVE RSID MESSAGE")
                    parts = []
                    if spaced:
                        parts.append(api.AudioPart(audio))
                    parts.append(api.MfskSegment((api.TextPart(payloads[0]),), modes[0], 1400))
                    if spaced:
                        parts.extend((api.SilencePart(0.25), api.AudioPart(audio)))
                    parts.append(api.MfskSegment((api.TextPart(payloads[1]),), modes[1], 1600))
                    output = root / "whole.wav"
                    result = api.encode_mfsk_wav(parts=parts, output_path=output)
                    raw = _wav_pcm(output)
                    for index, (part, start) in enumerate(zip(parts, result.segments)):
                        begin = round(start.start_seconds * 48000) * 2
                        if isinstance(part, api.AudioPart):
                            self.assertEqual(raw[begin:begin + len(audio_pcm)], audio_pcm)
                        elif isinstance(part, api.SilencePart):
                            stop = round(result.segments[index + 1].start_seconds * 48000) * 2
                            self.assertEqual(raw[begin:stop], bytes(12000 * 2))
                    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 16384
                    iq = signal.hilbert(samples).astype("<c8")
                    data = root / "whole.sigmf-data"
                    iq.tofile(data)
                    meta = root / "whole.sigmf-meta"
                    meta.write_text(json.dumps({"global": {"core:datatype": "cf32_le",
                        "core:sample_rate": 48000, "core:version": "1.0.0"},
                        "captures": [{"core:sample_start": 0}]}))
                    manifest = api.decode_iq(meta_path=meta, data_path=data,
                        config=api.DecodeConfig(mode="auto"))
                    hypotheses = manifest["mode_hypotheses"]
                    self.assertEqual([h["mode"] for h in hypotheses], list(modes))
                    self.assertEqual([h["evidence"]["rsid_code"] for h in hypotheses],
                                     [147 if mode == "MFSK32" else 620 for mode in modes])
                    for h, carrier in zip(hypotheses, (1400, 1600)):
                        # The bounded receiver accepts code distance <= 2;
                        # exact transmitted words are tested against the oracle.
                        self.assertLessEqual(h["evidence"]["code_distance"], 2)
                        self.assertAlmostEqual(h["evidence"]["center_hz"], carrier, delta=3)
                    text = manifest["text_summary"]["text"]
                    for payload in payloads:
                        self.assertIn(payload.decode(), text)
                    self.assertLess(text.index(payloads[0].decode()), text.index(payloads[1].decode()))
                    mfsk_starts = [s for s, p in zip(result.segments, parts) if isinstance(p, api.MfskSegment)]
                    for h, start, mode in zip(hypotheses, mfsk_starts, modes):
                        # The receiver's bucket/refinement start is approximate
                        # and can precede the tone word by several periods. Its
                        # window must overlap the transmitted identifier word.
                        # Exact output boundaries belong to the PCM oracle.
                        frame = round(start.start_seconds * 48000)
                        word_start = frame + (5 if mode == "MFSK32" else 30) * 4458
                        self.assertGreater(h["event_interval"]["stop"], word_start)
                        self.assertLess(h["event_interval"]["start"], word_start + 15 * 4458)
                    with wave.open(str(output), "rb") as source:
                        self.assertEqual(result.duration_seconds, source.getnframes() / 48000)


if __name__ == "__main__":
    unittest.main()
