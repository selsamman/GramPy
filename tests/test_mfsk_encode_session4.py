from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

from grampy.picture_encode import (
    MAX_PNG_BYTES,
    NormalizedPicture,
    normalize_png,
    plan_picture_raster,
)


class Session4PictureTests(unittest.TestCase):
    def write_image(self, directory: str, mode: str, size: tuple[int, int], values: list[int]) -> Path:
        path = Path(directory) / "image.png"
        image = Image.new(mode, size)
        image.putdata(values if mode == "L" else [tuple(values[index:index + 3]) for index in range(0, len(values), 3)])
        image.save(path, "PNG")
        return path

    def test_l_and_rgb_normalization_have_exact_component_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            l_path = self.write_image(directory, "L", (2, 2), [0, 128, 255, 7])
            gray = normalize_png(l_path, color="grayscale", samples_per_pixel=8)
            color = normalize_png(l_path, color="color", samples_per_pixel=8)
            self.assertEqual(tuple(gray.iter_component_values()), (0, 128, 255, 7))
            # Each row is sent as complete R, G and B planes, including L input.
            self.assertEqual(tuple(color.iter_component_values()), (0, 128, 0, 128, 0, 128, 255, 7, 255, 7, 255, 7))

            rgb_path = self.write_image(
                directory, "RGB", (2, 2),
                [0, 128, 255, 128, 255, 0, 255, 0, 128, 7, 8, 9],
            )
            gray = normalize_png(rgb_path, color="grayscale", samples_per_pixel=8)
            color = normalize_png(rgb_path, color="color", samples_per_pixel=8)
            self.assertEqual(tuple(gray.iter_component_values()), (98, 195, 89, 7))
            self.assertEqual(
                tuple(color.iter_component_values()),
                (0, 128, 128, 255, 255, 0, 255, 7, 0, 8, 128, 9),
            )

    def test_l_color_public_wav_matches_equivalent_rgb_in_both_modes_and_all_speeds(self) -> None:
        from grampy.api import ImagePart, MfskSegment, encode_mfsk_wav

        with tempfile.TemporaryDirectory() as directory:
            l_path = Path(directory) / "gray.png"
            self.write_image(directory, "L", (2, 2), [0, 128, 255, 7]).rename(l_path)
            rgb_path = self.write_image(directory, "RGB", (2, 2),
                [0, 0, 0, 128, 128, 128, 255, 255, 255, 7, 7, 7])
            for mode in ("MFSK32", "MFSK64"):
                for speed in (8, 4, 2):
                    with self.subTest(mode=mode, speed=speed):
                        outputs = []
                        for source in (l_path, rgb_path):
                            output = Path(directory) / f"{source.stem}-{mode}-{speed}.wav"
                            encode_mfsk_wav(parts=(MfskSegment((ImagePart(source,
                                color="color", samples_per_pixel=speed),), mode, 1500),),
                                output_path=output)
                            outputs.append(output.read_bytes())
                        self.assertEqual(outputs[0], outputs[1])

    def test_raster_frequencies_and_timings_are_exact_at_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_image(directory, "L", (3, 1), [0, 128, 255])
            for mode, expected in (
                ("MFSK32", (1265.625, 1500.0, 1732.5439453125)),
                ("MFSK64", (1031.25, 1500.0, 1965.087890625)),
            ):
                for speed, frames in ((8, 48), (4, 24), (2, 12)):
                    picture = normalize_png(path, color="grayscale", samples_per_pixel=speed)
                    plan = plan_picture_raster(picture, mode=mode, carrier_hz=1500, sample_rate_hz=48_000)
                    events = tuple(plan.iter_events())
                    self.assertEqual(tuple(event.value for event in events), (0, 128, 255))
                    self.assertEqual(tuple(event.frequency_hz for event in events), expected)
                    self.assertEqual(tuple(event.frame_count for event in events), (frames,) * 3)
                    self.assertEqual(plan.frame_count, 3 * frames)
                    self.assertEqual(plan.pcm_data_bytes, 6 * frames)

    def test_geometry_profile_alpha_and_input_size_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            valid = self.write_image(directory, "L", (4095, 1), [0] * 4095)
            self.assertEqual(normalize_png(valid, color="grayscale", samples_per_pixel=8).width, 4095)
            too_wide = self.write_image(directory, "L", (4096, 1), [0] * 4096)
            with self.assertRaisesRegex(ValueError, "dimensions"):
                normalize_png(too_wide, color="grayscale", samples_per_pixel=8)
            alpha = Path(directory) / "alpha.png"
            Image.new("RGBA", (1, 1)).save(alpha, "PNG")
            with self.assertRaisesRegex(ValueError, "8-bit L or RGB"):
                normalize_png(alpha, color="color", samples_per_pixel=8)
            with mock.patch.object(Path, "stat", return_value=mock.Mock(st_size=MAX_PNG_BYTES + 1)):
                with self.assertRaisesRegex(ValueError, "64 MiB"):
                    normalize_png(valid, color="grayscale", samples_per_pixel=8)

    def test_resource_limits_and_invalid_forms_are_checked_before_raster_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_image(directory, "RGB", (1, 1), [0, 128, 255])
            with self.assertRaises(ValueError):
                normalize_png(path, color="monochrome", samples_per_pixel=8)  # type: ignore[arg-type]
            with self.assertRaises(ValueError):
                normalize_png(path, color="color", samples_per_pixel=True)  # type: ignore[arg-type]
            picture = normalize_png(path, color="color", samples_per_pixel=2)
            with self.assertRaises(ValueError):
                plan_picture_raster(picture, mode="MFSK64", carrier_hz=3531.25, sample_rate_hz=8_000)
            oversized = NormalizedPicture(
                width=4095,
                height=4095,
                color="color",
                samples_per_pixel=8,
                source_mode="RGB",
                source_pixels=b"",
            )
            with self.assertRaisesRegex(ValueError, "RIFF"):
                plan_picture_raster(oversized, mode="MFSK64", carrier_hz=1500, sample_rate_hz=192_000)
