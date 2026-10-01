from __future__ import annotations

import io
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import wave

import numpy as np
from scipy import signal

from grampy.mfsk_encode import (
    ContinuousPhaseToneWriter,
    ENVELOPE_SECONDS,
    GENERATED_PCM_PEAK,
    encode_text_segment_wav,
    iter_framed_text_tones,
    plan_text_segment,
    tone_frequency_hz,
)
from grampy.text_decode import decode_mfsk_text
from tests.mfsk_encoder_evidence import (
    MODE_PARAMETERS as ORACLE_MODE_PARAMETERS,
    convolutional_encode,
    interleave_groups,
    physical_tone_indices,
)


ROOT = Path(__file__).resolve().parents[1]
START = b"\r\x02\r"
END = b"\r\x04\r"


def oracle_tones(mode: str, payload: bytes) -> tuple[int, ...]:
    import json

    varicode = json.loads(
        (ROOT / "docs" / "decoder" / "data" / "mfsk_varicode.json").read_text(
            encoding="utf-8"
        )
    )["encodings"]
    parameters = ORACLE_MODE_PARAMETERS[mode]
    bits = (
        "0" * parameters["leading_zero_input_bits"]
        + "".join(varicode[octet] for octet in START + payload + END)
        + "1"
        + "0" * parameters["preamble_input_bits"]
    )
    coded = tuple(int(bit) for bit in convolutional_encode(bits))
    groups = [coded[index : index + 4] for index in range(0, len(coded) - 3, 4)]
    interleaved = interleave_groups(groups)
    labels = [sum(bit << (3 - lane) for lane, bit in enumerate(group)) for group in interleaved]
    return tuple(physical_tone_indices(labels))


def pcm16(payload: bytes) -> np.ndarray:
    return np.frombuffer(payload, dtype="<i2")


class Session3FramingTests(unittest.TestCase):
    def test_complete_framing_matches_independent_oracle_in_both_modes(self) -> None:
        for mode in ("MFSK32", "MFSK64"):
            with self.subTest(mode=mode):
                actual = tuple(
                    iter_framed_text_tones(text_parts=(b"GramPy",), mode=mode)
                )
                self.assertEqual(actual, oracle_tones(mode, b"GramPy"))

    def test_text_item_chunking_is_wire_invariant(self) -> None:
        for mode in ("MFSK32", "MFSK64"):
            whole = tuple(iter_framed_text_tones(text_parts=(b"abcdef",), mode=mode))
            split = tuple(
                iter_framed_text_tones(
                    text_parts=(b"a", b"", b"bc", b"def"), mode=mode
                )
            )
            self.assertEqual(split, whole)

    def test_plan_has_exact_frames_and_logical_item_boundaries(self) -> None:
        plan = plan_text_segment(
            text_parts=(b"a", b"", b"bc"),
            mode="MFSK64",
            sample_rate_hz=48_000,
        )
        tones = tuple(
            iter_framed_text_tones(
                text_parts=(b"a", b"", b"bc"), mode="MFSK64"
            )
        )
        self.assertEqual(plan.frames_per_symbol, 768)
        self.assertEqual(plan.tone_count, len(tones))
        self.assertEqual(plan.frame_count, len(tones) * 768)
        self.assertEqual(plan.content_start_frames[1], plan.content_start_frames[0] + 3 * 768)
        self.assertEqual(plan.content_start_frames[2], plan.content_start_frames[1])


class Session3SynthesisTests(unittest.TestCase):
    def test_frequency_formula_and_every_supported_output_rate(self) -> None:
        for mode in ("MFSK32", "MFSK64"):
            expected_spacing = ORACLE_MODE_PARAMETERS[mode]["tone_spacing_hz"]
            self.assertEqual(
                tone_frequency_hz(mode, 1500.0, 15)
                - tone_frequency_hz(mode, 1500.0, 0),
                15 * expected_spacing,
            )
            internal_frames = 256 if mode == "MFSK32" else 128
            for sample_rate in range(8_000, 192_001, 8_000):
                with self.subTest(mode=mode, sample_rate=sample_rate):
                    sink = io.BytesIO()
                    writer = ContinuousPhaseToneWriter(
                        sink,
                        mode=mode,
                        carrier_hz=1500.0,
                        sample_rate_hz=sample_rate,
                    )
                    writer.push_tones((0, 15))
                    writer.finish()
                    expected_frames = 2 * internal_frames * (sample_rate // 8_000)
                    self.assertEqual(writer.frame_count, expected_frames)
                    self.assertEqual(len(sink.getvalue()), expected_frames * 2)

    def test_phase_is_continuous_and_matches_integrated_frequency(self) -> None:
        sink = io.BytesIO()
        tones = (0, 3, 15, 7)
        writer = ContinuousPhaseToneWriter(
            sink,
            mode="MFSK64",
            carrier_hz=1500.0,
            sample_rate_hz=48_000,
        )
        writer.push_tones(tones)
        writer.finish()
        frames_per_symbol = 768
        expected_phase = sum(
            2.0 * math.pi * tone_frequency_hz("MFSK64", 1500.0, tone)
            * frames_per_symbol
            / 48_000
            for tone in tones
        ) % (2.0 * math.pi)
        circular_error = math.remainder(
            writer.phase_radians - expected_phase,
            2.0 * math.pi,
        )
        self.assertAlmostEqual(circular_error, 0.0, places=10)

        samples = pcm16(sink.getvalue())
        boundary = frames_per_symbol
        prior_phase = sum(
            2.0 * math.pi * tone_frequency_hz("MFSK64", 1500.0, tones[0])
            / 48_000
            for _ in range(boundary)
        ) % (2.0 * math.pi)
        expected_boundary_sample = int(round(GENERATED_PCM_PEAK * math.sin(prior_phase)))
        self.assertEqual(int(samples[boundary]), expected_boundary_sample)

    def test_pcm_level_and_frame_neutral_raised_cosine_envelope(self) -> None:
        sink = io.BytesIO()
        writer = ContinuousPhaseToneWriter(
            sink,
            mode="MFSK32",
            carrier_hz=1500.0,
            sample_rate_hz=48_000,
        )
        writer.push_tones((4, 9, 12))
        writer.finish()
        samples = pcm16(sink.getvalue())
        frames_per_symbol = 1536
        ramp_frames = int(ENVELOPE_SECONDS * 48_000)
        self.assertEqual(len(samples), 3 * frames_per_symbol)
        self.assertEqual(int(samples[0]), 0)
        self.assertEqual(int(samples[-1]), 0)
        self.assertLessEqual(int(np.max(np.abs(samples.astype(np.int32)))), GENERATED_PCM_PEAK)
        self.assertGreater(
            int(np.max(np.abs(samples[ramp_frames:frames_per_symbol]))),
            int(GENERATED_PCM_PEAK * 0.99),
        )
        self.assertGreater(
            int(np.max(np.abs(samples[frames_per_symbol:2 * frames_per_symbol]))),
            int(GENERATED_PCM_PEAK * 0.99),
        )

    def test_pcm_quantization_has_exact_initial_samples(self) -> None:
        sink = io.BytesIO()
        writer = ContinuousPhaseToneWriter(
            sink,
            mode="MFSK64",
            carrier_hz=1500.0,
            sample_rate_hz=48_000,
        )
        writer.push_tones((8, 8))
        writer.finish()
        actual = pcm16(sink.getvalue())
        frequency = tone_frequency_hz("MFSK64", 1500.0, 8)
        ramp_frames = int(ENVELOPE_SECONDS * 48_000)
        expected = []
        for index in range(12):
            gain = 0.5 - 0.5 * math.cos(math.pi * index / (ramp_frames - 1))
            expected.append(
                int(round(GENERATED_PCM_PEAK * gain * math.sin(2 * math.pi * frequency * index / 48_000)))
            )
        self.assertEqual(actual[:12].tolist(), expected)

    def test_pcm_writes_remain_one_symbol_bounded_for_long_tone_streams(self) -> None:
        class CountingSink:
            def __init__(self) -> None:
                self.lengths: list[int] = []

            def write(self, payload: bytes) -> int:
                self.lengths.append(len(payload))
                return len(payload)

        sink = CountingSink()
        writer = ContinuousPhaseToneWriter(
            sink,
            mode="MFSK32",
            carrier_hz=1500.0,
            sample_rate_hz=192_000,
        )
        writer.push_tones(index % 16 for index in range(200))
        writer.finish()
        self.assertEqual(len(sink.lengths), 200)
        self.assertEqual(set(sink.lengths), {256 * (192_000 // 8_000) * 2})


class Session3WaveTests(unittest.TestCase):
    def test_streaming_output_is_canonical_wav_with_exact_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.wav"
            result = encode_text_segment_wav(
                text_parts=(b"hello", b" world"),
                output_path=output,
                mode="MFSK32",
                carrier_hz=1500.0,
                sample_rate_hz=48_000,
            )
            raw = output.read_bytes()
            self.assertEqual(raw[:4], b"RIFF")
            self.assertEqual(raw[8:12], b"WAVE")
            self.assertEqual(raw[12:16], b"fmt ")
            self.assertEqual(raw[36:40], b"data")
            self.assertEqual(struct.unpack("<I", raw[4:8])[0], len(raw) - 8)
            self.assertEqual(struct.unpack("<I", raw[40:44])[0], len(raw) - 44)
            with wave.open(str(output), "rb") as source:
                self.assertEqual(source.getnchannels(), 1)
                self.assertEqual(source.getsampwidth(), 2)
                self.assertEqual(source.getframerate(), 48_000)
                self.assertEqual(source.getnframes(), result.frame_count)
            self.assertEqual(result.output_path, output)
            self.assertEqual(result.frame_count * 2 + 44, len(raw))
            self.assertEqual(result.duration_seconds, result.frame_count / 48_000)

    def test_invalid_preflight_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.wav"
            output.write_bytes(b"preserve me")
            with self.assertRaises(ValueError):
                encode_text_segment_wav(
                    text_parts=(b"x",),
                    output_path=output,
                    mode="MFSK32",
                    carrier_hz=50.0,
                    sample_rate_hz=48_000,
                )
            self.assertEqual(output.read_bytes(), b"preserve me")

    def test_reported_write_failure_removes_replaced_output(self) -> None:
        class FailingHandle:
            def __init__(self, wrapped: io.BufferedRandom) -> None:
                self.wrapped = wrapped
                self.write_count = 0

            def write(self, payload: bytes) -> int:
                self.write_count += 1
                if self.write_count == 2:
                    raise OSError("injected PCM write failure")
                return self.wrapped.write(payload)

            def seek(self, offset: int) -> int:
                return self.wrapped.seek(offset)

            def flush(self) -> None:
                self.wrapped.flush()

            def close(self) -> None:
                self.wrapped.close()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.wav"
            output.write_bytes(b"old output")
            wrapped = open(output, "w+b")
            failing = FailingHandle(wrapped)
            with mock.patch.object(Path, "open", return_value=failing):
                with self.assertRaisesRegex(OSError, "injected PCM write failure"):
                    encode_text_segment_wav(
                        text_parts=(b"failure",),
                        output_path=output,
                        mode="MFSK64",
                    )
            self.assertTrue(wrapped.closed)
            self.assertFalse(output.exists())

    def test_validation_boundaries(self) -> None:
        with self.assertRaises(ValueError):
            plan_text_segment(text_parts=(), mode="MFSK32", sample_rate_hz=48_000)
        with self.assertRaises(TypeError):
            plan_text_segment(text_parts=(bytearray(b"x"),), mode="MFSK32", sample_rate_hz=48_000)  # type: ignore[arg-type]
        for invalid in (True, 7_999, 48_001, 192_001):
            with self.assertRaises(ValueError):
                plan_text_segment(text_parts=(b"x",), mode="MFSK32", sample_rate_hz=invalid)  # type: ignore[arg-type]

    def test_coupled_round_trip_recovers_payload_in_both_modes(self) -> None:
        payload = b"GramPy session 3 round trip"
        with tempfile.TemporaryDirectory() as directory:
            for mode in ("MFSK32", "MFSK64"):
                with self.subTest(mode=mode):
                    output = Path(directory) / f"{mode}.wav"
                    encode_text_segment_wav(
                        text_parts=(payload,),
                        output_path=output,
                        mode=mode,
                        carrier_hz=1500.0,
                        sample_rate_hz=48_000,
                    )
                    with wave.open(str(output), "rb") as source:
                        real = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float64)
                    analytic = signal.hilbert(real / GENERATED_PCM_PEAK).astype(np.complex64)
                    decoded = decode_mfsk_text(
                        analytic,
                        input_start=0,
                        sample_rate=48_000.0,
                        orientation_hint="normal",
                        trace_level="none",
                        mode=mode,
                        center_hint_hz=1500.0,
                    )
                    self.assertTrue(decoded.text_summary["framing"]["stx_found"])
                    self.assertTrue(decoded.text_summary["framing"]["eot_found"])
                    self.assertEqual(bytes(decoded.text_summary["octets"]), payload)


if __name__ == "__main__":
    unittest.main()
