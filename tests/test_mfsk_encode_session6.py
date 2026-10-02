from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np
from PIL import Image
from scipy import signal

from grampy import api
from grampy.mfsk_segment_encode import plan_mfsk_segment
from grampy.picture_encode import normalize_png
from grampy.text_decode import decode_mfsk_text


def _write_audio(path: Path, samples: tuple[int, ...], *, rate: int = 48_000) -> bytes:
    pcm = struct.pack("<" + "h" * len(samples), *samples)
    with wave.open(str(path), "wb") as sink:
        sink.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        sink.writeframes(pcm)
    return pcm


def _wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        return source.readframes(source.getnframes())


class Session6CompositionTests(unittest.TestCase):
    def test_public_surface_and_text_conversion(self) -> None:
        self.assertEqual([field.name for field in fields(api.MfskSegment)], ["parts", "mode", "carrier_hz"])
        self.assertEqual([field.name for field in fields(api.EncodeResult)], ["output_path", "duration_seconds", "segments"])
        self.assertEqual(api.TextPart.from_text("é").data, "é".encode())
        with self.assertRaises(UnicodeEncodeError):
            api.TextPart.from_text("é", encoding="ascii")
        with self.assertRaises(LookupError):
            api.TextPart.from_text("x", encoding="missing-encoder")

    def test_adjacent_modes_have_no_implicit_gap_and_independent_framing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "adjacent.wav"
            first = api.MfskSegment((api.TextPart(b"FIRST"),), mode="MFSK32", carrier_hz=1400.0)
            second = api.MfskSegment((api.TextPart(b"SECOND"),), mode="MFSK64", carrier_hz=1600.0)
            result = api.encode_mfsk_wav(parts=(first, second), output_path=output)
            first_plan = plan_mfsk_segment(contents=(b"FIRST",), mode="MFSK32", carrier_hz=1400.0, sample_rate_hz=48_000)
            second_plan = plan_mfsk_segment(contents=(b"SECOND",), mode="MFSK64", carrier_hz=1600.0, sample_rate_hz=48_000)
            self.assertEqual(result.segments[0].start_seconds, 0.0)
            self.assertEqual(result.segments[1].start_seconds, first_plan.frame_count / 48_000)
            self.assertEqual(result.duration_seconds, (first_plan.frame_count + second_plan.frame_count) / 48_000)
            self.assertEqual(result.segments[0].contents[0].start_seconds, first_plan.content_start_frames[0] / 48_000)
            with wave.open(str(output), "rb") as source:
                self.assertEqual(source.getnframes(), first_plan.frame_count + second_plan.frame_count)
            self.assertEqual(output.stat().st_size, 44 + 2 * (first_plan.frame_count + second_plan.frame_count))

            pcm = np.frombuffer(_wav_pcm(output), dtype="<i2").astype(np.float64)
            for mode, start, stop, expected, carrier in (
                ("MFSK32", 0, first_plan.frame_count, b"FIRST", 1400.0),
                ("MFSK64", first_plan.frame_count, len(pcm), b"SECOND", 1600.0),
            ):
                with self.subTest(mode=mode):
                    analytic = signal.hilbert(pcm[start:stop] / 16_384).astype(np.complex64)
                    recovered = decode_mfsk_text(
                        analytic,
                        input_start=start,
                        sample_rate=48_000.0,
                        orientation_hint="normal",
                        trace_level="none",
                        mode=mode,
                        center_hint_hz=carrier,
                    )
                    self.assertIn(expected, bytes(recovered.text_summary["octets"]))

    def test_mixed_text_file_picture_audio_and_silence_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_file = root / "raw.txt"
            text_file.write_bytes(b"A\r\n\x00\xff")
            image = root / "small.png"
            Image.new("L", (1, 1), 128).save(image)
            audio = root / "clip.wav"
            pcm = _write_audio(audio, (0, 8192, -8192, 0))
            output = root / "mixed.wav"
            segment = api.MfskSegment((api.TextFilePart(text_file), api.ImagePart(image, "grayscale", 2), api.TextPart(b"END")))
            parts = (api.SilencePart(1 / 48_000), api.AudioPart(audio), segment)
            result = api.encode_mfsk_wav(parts=parts, output_path=output)
            plan = plan_mfsk_segment(
                contents=(text_file.read_bytes(), normalize_png(image, color="grayscale", samples_per_pixel=2), b"END"),
                mode="MFSK64", carrier_hz=1500.0, sample_rate_hz=48_000,
            )
            self.assertEqual(tuple(item.input_index for item in result.segments), (0, 1, 2))
            self.assertEqual(tuple(item.start_seconds for item in result.segments), (0.0, 1 / 48_000, 5 / 48_000))
            self.assertEqual(tuple(item.content_index for item in result.segments[2].contents), (0, 1, 2))
            self.assertEqual(tuple(item.start_seconds for item in result.segments[2].contents), tuple((5 + frame) / 48_000 for frame in plan.content_start_frames))
            self.assertEqual(result.duration_seconds, (5 + plan.frame_count) / 48_000)
            self.assertEqual(_wav_pcm(output)[:10], b"\x00\x00" + pcm)

    def test_audio_ancillary_chunk_is_skipped_and_pcm_copied_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            pcm = _write_audio(source, (1, -2, 3))
            original = source.read_bytes()
            ancillary = b"JUNK" + struct.pack("<I", 3) + b"abc\x00"
            revised = original[:12] + ancillary + original[12:]
            source.write_bytes(revised)
            with source.open("r+b") as handle:
                handle.seek(4)
                handle.write(struct.pack("<I", len(revised) - 8))
            output = root / "out.wav"
            api.encode_mfsk_wav(parts=(api.AudioPart(source),), output_path=output)
            self.assertEqual(_wav_pcm(output), pcm)
            self.assertEqual(output.stat().st_size, 44 + len(pcm))

    def test_preflight_preserves_existing_output_for_bad_input_and_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "existing.wav"
            output.write_bytes(b"KEEP")
            with self.assertRaises(FileNotFoundError):
                api.encode_mfsk_wav(parts=(api.AudioPart(root / "missing.wav"),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.SilencePart(0.00001),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.SilencePart(2**31 / 48_000),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.TextPart(b"wrong"),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.MfskSegment((api.TextPart(b"x"),), mode="bad"),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")
            audio = root / "audio.wav"
            original = _write_audio(audio, (1, 2))
            alias = root / "alias.wav"
            alias.hardlink_to(audio)
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.AudioPart(audio),), output_path=alias)
            self.assertEqual(_wav_pcm(audio), original)

            replacement = api.encode_mfsk_wav(parts=(api.SilencePart(1 / 48_000),), output_path=output)
            self.assertEqual(replacement.duration_seconds, 1 / 48_000)
            self.assertEqual(_wav_pcm(output), b"\x00\x00")
            symlink = root / "symlink.wav"
            symlink.symlink_to(audio)
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.AudioPart(audio),), output_path=symlink)
            self.assertEqual(_wav_pcm(audio), original)

    def test_malformed_audio_rejected_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            _write_audio(source, (1, 2, 3))
            malformed = source.read_bytes()[:-1]
            source.write_bytes(malformed)
            output = root / "existing.wav"
            output.write_bytes(b"KEEP")
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.AudioPart(source),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")

    def test_truncated_png_rejected_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "broken.png"
            Image.new("RGB", (2, 2), (1, 2, 3)).save(image)
            image.write_bytes(image.read_bytes()[:35])
            output = root / "existing.wav"
            output.write_bytes(b"KEEP")
            with self.assertRaises(ValueError):
                api.encode_mfsk_wav(parts=(api.MfskSegment((api.ImagePart(image),)),), output_path=output)
            self.assertEqual(output.read_bytes(), b"KEEP")

    def test_reported_write_failure_removes_replaced_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.wav"
            output.write_bytes(b"OLD")
            with patch("grampy.mfsk_compose._write_silence", side_effect=OSError("injected failure")):
                with self.assertRaisesRegex(OSError, "injected failure"):
                    api.encode_mfsk_wav(parts=(api.SilencePart(0.01),), output_path=output)
            self.assertFalse(output.exists())

    def test_removal_failure_reports_residual_path_and_preserves_cause(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.wav"
            with patch("grampy.mfsk_compose._write_silence", side_effect=OSError("write failed")):
                with patch.object(Path, "unlink", side_effect=PermissionError("remove failed")):
                    with self.assertRaisesRegex(PermissionError, "remove failed") as caught:
                        api.encode_mfsk_wav(parts=(api.SilencePart(0.01),), output_path=output)
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertIn("write failed", str(caught.exception.__cause__))
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
