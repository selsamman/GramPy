"""Session 7 package and bounded-streaming hardening checks."""

from __future__ import annotations

import tempfile
from pathlib import Path
import tomllib
import tracemalloc
import unittest
import wave

from grampy import api
from grampy.mfsk_compose import _AudioPlan, _copy_audio, _write_silence
from grampy.mfsk_segment_encode import _iter_file_tones
from grampy.picture_encode import normalize_png, plan_picture_raster
from PIL import Image
from tests.test_mfsk_encode_session6 import _write_audio


ROOT = Path(__file__).resolve().parents[1]


class _TrackingSink:
    def __init__(self) -> None:
        self.write_lengths: list[int] = []

    def write(self, payload: bytes) -> int:
        self.write_lengths.append(len(payload))
        return len(payload)


class Session7HardeningTests(unittest.TestCase):
    def test_distribution_metadata_public_exports_and_library_docs_agree(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(project["project"]["name"], "radiogrampy")
        self.assertGreaterEqual(project["project"]["requires-python"], ">=3.11")
        self.assertIn("Pillow", project["project"]["dependencies"])
        self.assertNotIn("mfsk-wav-encode", project["project"].get("scripts", {}))

        expected = {
            "AudioPart", "ContentStart", "EncodeConfig", "EncodeResult",
            "ImagePart", "MfskSegment", "SegmentStart", "SilencePart",
            "TextFilePart", "TextPart", "encode_mfsk_wav",
        }
        self.assertTrue(expected <= set(api.__all__))
        guide = (ROOT / "docs" / "encoder" / "api.md").read_text()
        readme = (ROOT / "README.md").read_text()
        self.assertIn("encode_mfsk_wav", guide)
        self.assertIn("library-only", guide)
        self.assertIn("encoder API guide", readme)

    def test_audio_copy_and_silence_use_fixed_size_pcm_writes(self) -> None:
        # This exercises the long-duration paths without retaining generated
        # output. The source exists before tracing so input creation is not
        # counted as encoder working memory.
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.wav"
            _write_audio(source, (123, -456, 789, 0) * 262_144)
            plan = _AudioPlan(source, 44, source.stat().st_size - 44)
            sink = _TrackingSink()
            tracemalloc.start()
            try:
                _copy_audio(sink, plan)
                _write_silence(sink, plan.frame_count)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

        self.assertEqual(sum(sink.write_lengths), plan.data_bytes * 2)
        self.assertTrue(sink.write_lengths)
        self.assertLessEqual(max(sink.write_lengths), 64 * 1024)
        # Two 64-KiB source/sink buffers plus interpreter overhead leave a
        # generous but duration-independent 512-KiB limit.
        self.assertLess(peak, 512 * 1024)

    def test_long_text_file_is_consumed_in_fixed_chunks(self) -> None:
        class ChunkRecordingEncoder:
            def __init__(self) -> None:
                self.lengths: list[int] = []

            def push_bytes(self, payload: bytes) -> tuple[()]:
                self.lengths.append(len(payload))
                return ()

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "long.txt"
            source.write_bytes(b"LONG TEXT\n" * (2 * 1024 * 1024 // 10))
            encoder = ChunkRecordingEncoder()
            tracemalloc.start()
            try:
                self.assertEqual(tuple(_iter_file_tones(encoder, source)), ())
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

        self.assertGreater(len(encoder.lengths), 1)
        self.assertLessEqual(max(encoder.lengths), 64 * 1024)
        # Buffered file I/O can momentarily retain its 64-KiB source buffer in
        # addition to the encoder chunk; this remains fixed, not file-sized.
        self.assertLess(peak, 384 * 1024)

    def test_large_image_keeps_one_source_raster_and_streams_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "large.png"
            Image.new("L", (1024, 1024), 127).save(source)
            tracemalloc.start()
            try:
                picture = normalize_png(source, color="grayscale", samples_per_pixel=8)
                plan = plan_picture_raster(
                    picture, mode="MFSK32", carrier_hz=1500.0, sample_rate_hz=48_000
                )
                self.assertEqual(sum(1 for _ in plan.iter_events()), 1024 * 1024)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

        self.assertEqual(len(picture.source_pixels), 1024 * 1024)
        # One decoded raster is an allowed image-sized allocation; event
        # iteration must not add another image-sized list or component plane.
        self.assertLess(peak, 3 * 1024 * 1024)

    def test_result_coordinates_match_completed_wav_after_mixed_parts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "source.wav"
            _write_audio(audio, (1, -1, 2, -2))
            output = root / "mixed.wav"
            parts = (
                api.SilencePart(2 / 48_000),
                api.AudioPart(audio),
                api.MfskSegment((api.TextPart(b"ONE"),), "MFSK32", 1400.0),
                api.MfskSegment((api.TextPart(b"TWO"),), "MFSK64", 1600.0),
            )
            result = api.encode_mfsk_wav(parts=parts, output_path=output)
            with wave.open(str(output), "rb") as completed:
                total_frames = completed.getnframes()
                self.assertEqual(result.duration_seconds, total_frames / 48_000)

            starts = [round(segment.start_seconds * 48_000) for segment in result.segments]
            self.assertEqual(starts, sorted(starts))
            self.assertEqual(starts[0], 0)
            self.assertLess(starts[-1], total_frames)
            for segment in result.segments:
                for content in segment.contents:
                    frame = round(content.start_seconds * 48_000)
                    self.assertGreaterEqual(frame, round(segment.start_seconds * 48_000))
                    self.assertLess(frame, total_frames)


if __name__ == "__main__":
    unittest.main()
