from __future__ import annotations

import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np
from PIL import Image
from scipy import signal

from grampy.mfsk_encode import (
    ContinuousPhaseToneWriter,
    GENERATED_PCM_PEAK,
    tone_frequency_hz,
)
from grampy.mfsk_segment_encode import (
    encode_mfsk_segment_wav,
    plan_mfsk_segment,
)
from grampy.picture_decode import decode_pictures
from grampy.picture_encode import normalize_png, picture_announcement
from grampy.text_decode import decode_mfsk_text
from mfsk_encoder_evidence import MODE_PARAMETERS, count_symbols


ROOT = Path(__file__).resolve().parents[1]
VARICODE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_varicode.json").read_text(
        encoding="utf-8"
    )
)["encodings"]
START = b"\r\x02\r"
END = b"\r\x04\r"


def varicode_bits(data: bytes) -> int:
    return sum(len(VARICODE[octet]) for octet in data)


def write_png(
    directory: str,
    *,
    mode: str = "RGB",
    size: tuple[int, int] = (2, 1),
) -> Path:
    path = Path(directory) / f"{mode.lower()}.png"
    image = Image.new(mode, size)
    if mode == "RGB":
        image.putdata([(0, 128, 255), (255, 0, 128)])
    else:
        image.putdata([0, 255])
    image.save(path, "PNG")
    return path


def oracle_frame_count_and_transitions(
    contents: tuple[bytes | object, ...],
    *,
    mode: str,
    sample_rate_hz: int,
) -> tuple[int, list[tuple[int, int, int, int, int, int]]]:
    parameters = MODE_PARAMETERS[mode]
    frames_per_symbol = round(sample_rate_hz / parameters["symbols_per_second"])
    prologue_frames = 352 * sample_rate_hz // 8000
    input_bits = parameters["leading_zero_input_bits"] + varicode_bits(START)
    frame_cursor = (input_bits // 2) * frames_per_symbol
    input_bits %= 2
    transitions = []
    for content in contents:
        if isinstance(content, bytes):
            total = input_bits + varicode_bits(content)
            frame_cursor += (total // 2) * frames_per_symbol
            input_bits = total % 2
            continue
        announcement = picture_announcement(content)  # type: ignore[arg-type]
        total = input_bits + varicode_bits(announcement)
        frame_cursor += (total // 2) * frames_per_symbol
        input_bits = total % 2
        header_flush_start = frame_cursor
        header_count = count_symbols(
            1 + parameters["preamble_input_bits"],
            pending_coded_bits=input_bits * 2,
        ).complete_symbols
        frame_cursor += header_count * frames_per_symbol
        prologue_start = frame_cursor
        frame_cursor += prologue_frames
        raster_start = frame_cursor
        component_count = (
            content.width * content.height * (3 if content.color == "color" else 1)  # type: ignore[attr-defined]
        )
        frame_cursor += (
            component_count
            * content.samples_per_pixel  # type: ignore[attr-defined]
            * sample_rate_hz
            // 8000
        )
        raster_stop = frame_cursor
        post_count = count_symbols(
            1 + parameters["preamble_input_bits"]
        ).complete_symbols
        frame_cursor += post_count * frames_per_symbol
        transitions.append(
            (
                header_flush_start,
                header_count,
                prologue_start,
                raster_start,
                raster_stop,
                post_count,
            )
        )
        input_bits = 0
    total = input_bits + varicode_bits(END) + 1 + parameters["preamble_input_bits"]
    frame_cursor += (total // 2) * frames_per_symbol
    return frame_cursor, transitions


class Session5AnnouncementAndPlanTests(unittest.TestCase):
    def test_announcements_match_the_accepted_fldigi_convention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gray = normalize_png(
                write_png(directory, mode="L"),
                color="grayscale",
                samples_per_pixel=8,
            )
            color = normalize_png(
                write_png(directory, mode="RGB"),
                color="color",
                samples_per_pixel=4,
            )
            self.assertEqual(picture_announcement(gray), b"\nSending Pic:2x1;")
            self.assertEqual(picture_announcement(color), b"\nSending Pic:2x1Cp4;")
            self.assertFalse(picture_announcement(color).endswith(b"\n"))

    def test_all_orderings_have_exact_independent_transition_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gray = normalize_png(
                write_png(directory, mode="L"),
                color="grayscale",
                samples_per_pixel=2,
            )
            color = normalize_png(
                write_png(directory, mode="RGB"),
                color="color",
                samples_per_pixel=4,
            )
            layouts = {
                "image-first": (gray,),
                "text-image-text": (b"BEFORE", color, b"AFTER"),
                "multiple-image": (b"A", gray, color, b"B"),
            }
            for mode in ("MFSK32", "MFSK64"):
                for name, contents in layouts.items():
                    with self.subTest(mode=mode, layout=name):
                        plan = plan_mfsk_segment(
                            contents=contents,
                            mode=mode,
                            carrier_hz=1500.0,
                            sample_rate_hz=48_000,
                        )
                        expected_frames, expected_transitions = (
                            oracle_frame_count_and_transitions(
                                contents,
                                mode=mode,
                                sample_rate_hz=48_000,
                            )
                        )
                        self.assertEqual(plan.frame_count, expected_frames)
                        self.assertEqual(len(plan.content_start_frames), len(contents))
                        self.assertEqual(
                            [
                                (
                                    item.header_flush_start_frame,
                                    item.header_flush_symbol_count,
                                    item.prologue_start_frame,
                                    item.raster_start_frame,
                                    item.raster_stop_frame,
                                    item.post_picture_flush_symbol_count,
                                )
                                for item in plan.picture_transitions
                            ],
                            expected_transitions,
                        )
                        for item in plan.picture_transitions:
                            self.assertEqual(
                                item.raster_start_frame - item.prologue_start_frame,
                                352 * 6,
                            )
                            self.assertEqual(
                                item.post_picture_flush_start_frame,
                                item.raster_stop_frame,
                            )
                            expected_post = 54 if mode == "MFSK32" else 90
                            self.assertEqual(
                                item.post_picture_flush_symbol_count,
                                expected_post,
                            )


class Session5SynthesisTests(unittest.TestCase):
    def test_phase_is_continuous_across_tone_prologue_raster_and_tone(self) -> None:
        sink = io.BytesIO()
        writer = ContinuousPhaseToneWriter(
            sink,
            mode="MFSK64",
            carrier_hz=1500.0,
            sample_rate_hz=48_000,
        )
        intervals = (
            (tone_frequency_hz("MFSK64", 1500.0, 3), 768),
            (1031.25, 2112),
            (1500.0, 48),
            (tone_frequency_hz("MFSK64", 1500.0, 12), 768),
        )
        writer.push_tones((3,))
        writer.push_frequency(1031.25, 2112)
        writer.push_frequency(1500.0, 48)
        writer.push_tones((12,))
        writer.finish()
        samples = np.frombuffer(sink.getvalue(), dtype="<i2")
        cursor = 0
        phase = 0.0
        for frequency, frames in intervals[:-1]:
            phase = (phase + 2 * math.pi * frequency * frames / 48_000) % (
                2 * math.pi
            )
            cursor += frames
            expected = int(round(GENERATED_PCM_PEAK * math.sin(phase)))
            self.assertEqual(int(samples[cursor]), expected)

    def test_complete_wav_matches_plan_for_both_modes_and_multiple_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gray = normalize_png(
                write_png(directory, mode="L"),
                color="grayscale",
                samples_per_pixel=2,
            )
            color = normalize_png(
                write_png(directory, mode="RGB"),
                color="color",
                samples_per_pixel=4,
            )
            contents = (b"A", gray, b"B", color, b"C")
            for mode in ("MFSK32", "MFSK64"):
                with self.subTest(mode=mode):
                    output = Path(directory) / f"{mode}.wav"
                    result = encode_mfsk_segment_wav(
                        contents=contents,
                        output_path=output,
                        mode=mode,
                    )
                    plan = plan_mfsk_segment(
                        contents=contents,
                        mode=mode,
                        carrier_hz=1500.0,
                        sample_rate_hz=48_000,
                    )
                    self.assertEqual(result.frame_count, plan.frame_count)
                    self.assertEqual(
                        result.content_start_frames,
                        plan.content_start_frames,
                    )
                    with wave.open(str(output), "rb") as source:
                        self.assertEqual(source.getnframes(), plan.frame_count)
                        self.assertEqual(source.getframerate(), 48_000)
                        self.assertEqual(source.getnchannels(), 1)
                        self.assertEqual(source.getsampwidth(), 2)

    def test_coupled_grampy_recovers_header_picture_and_resumed_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            picture = normalize_png(
                write_png(directory, mode="L"),
                color="grayscale",
                samples_per_pixel=8,
            )
            output = Path(directory) / "round-trip.wav"
            result = encode_mfsk_segment_wav(
                contents=(b"BEFORE", picture, b"AFTER"),
                output_path=output,
                mode="MFSK64",
            )
            transition = result.picture_transitions[0]
            with wave.open(str(output), "rb") as source:
                real = np.frombuffer(
                    source.readframes(source.getnframes()), dtype="<i2"
                ).astype(np.float64)
            analytic = signal.hilbert(real / GENERATED_PCM_PEAK).astype(np.complex64)

            prefix = decode_mfsk_text(
                analytic[: transition.prologue_start_frame],
                input_start=0,
                sample_rate=48_000.0,
                orientation_hint="normal",
                trace_level="events",
                mode="MFSK64",
                center_hint_hz=1500.0,
            )
            prefix_octets = bytes(prefix.text_summary["octets"])
            self.assertIn(b"BEFORE\nSending Pic:2x1;", prefix_octets)

            decoded_picture = decode_pictures(
                analytic,
                input_start=0,
                sample_rate=48_000,
                mode="MFSK64",
                orientation="normal",
                center_hz=1500.0,
                text_events=prefix.text_events,
            )
            self.assertEqual(len(decoded_picture.pictures), 1)
            self.assertTrue(decoded_picture.pictures[0]["complete"])
            recovered_values = decoded_picture.artifacts[0]["values"]
            self.assertLessEqual(
                max(abs(actual - expected) for actual, expected in zip(
                    recovered_values, (0, 255)
                )),
                8,
            )

            resumed = decode_mfsk_text(
                analytic[transition.post_picture_flush_start_frame :],
                input_start=transition.post_picture_flush_start_frame,
                sample_rate=48_000.0,
                orientation_hint="normal",
                trace_level="none",
                mode="MFSK64",
                center_hint_hz=1500.0,
            )
            self.assertIn(b"AFTER", bytes(resumed.text_summary["octets"]))


if __name__ == "__main__":
    unittest.main()
