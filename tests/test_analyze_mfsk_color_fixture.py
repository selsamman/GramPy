from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "tools" / "analyze-mfsk-color-fixture"
PPM = ROOT / "tests" / "fixtures" / "mfsk" / "primary-color-8x4.ppm"


class AnalyzeMfskColorFixtureTests(unittest.TestCase):
    def test_locates_known_row_plane_raster(self) -> None:
        rate = 48000
        samples_per_component = 48
        prefix = 1200
        suffix = 1200
        prologue_samples = 2112
        pixels = ppm_pixels(PPM)
        values = []
        for row in range(4):
            row_pixels = pixels[row * 8 : (row + 1) * 8]
            for component in range(3):
                values.extend(pixel[component] for pixel in row_pixels)
        frequencies = 1500 + 937.5 * (
            np.asarray(values, dtype=float) - 128
        ) / 256
        sample_frequencies = np.repeat(frequencies, samples_per_component)
        combined_frequencies = np.concatenate(
            [np.full(prologue_samples, 1031.25), sample_frequencies]
        )
        phase = 2 * np.pi * np.cumsum(combined_frequencies) / rate
        picture = 0.5 * np.cos(phase)
        samples = np.concatenate(
            [np.zeros(prefix), picture, np.zeros(suffix)]
        )
        pcm = np.round(samples * 32767).astype("<i2")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wav_path = root / "fixture.wav"
            output = root / "analysis.json"
            with wave.open(str(wav_path), "wb") as sink:
                sink.setnchannels(1)
                sink.setsampwidth(2)
                sink.setframerate(rate)
                sink.writeframes(pcm.tobytes())
            completed = subprocess.run(
                [
                    str(ANALYZER),
                    "--wav",
                    str(wav_path),
                    "--ppm",
                    str(PPM),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertLessEqual(
                abs(
                    evidence["raster"]["sample_start"]
                    - prefix
                    - prologue_samples
                ),
                samples_per_component,
            )
            self.assertEqual(evidence["raster"]["sample_count"], 4608)
            prologue = evidence["picture_prologue"]
            self.assertEqual(prologue["sample_count"], prologue_samples)
            self.assertAlmostEqual(prologue["duration_sec"], 0.044)
            self.assertLess(abs(prologue["frequency_error_hz"]), 2)
            ordering = evidence["ordering_rmse_hz"]
            self.assertLess(ordering["row_rgb_planes"], 20)
            self.assertGreater(ordering["pixel_rgb_interleaved"], 300)
            self.assertGreater(ordering["image_rgb_planes"], 300)


def ppm_pixels(path: Path) -> list[tuple[int, int, int]]:
    parts = path.read_bytes().split(maxsplit=4)
    rgb = parts[4]
    return [
        (rgb[offset], rgb[offset + 1], rgb[offset + 2])
        for offset in range(0, len(rgb), 3)
    ]


if __name__ == "__main__":
    unittest.main()
