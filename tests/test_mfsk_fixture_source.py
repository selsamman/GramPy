from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "mfsk"
GENERATOR = FIXTURE_DIR / "generate_primary_color_8x4.py"
PNG = FIXTURE_DIR / "primary-color-8x4.png"
PPM = FIXTURE_DIR / "primary-color-8x4.ppm"


class MfskFixtureSourceTests(unittest.TestCase):
    def test_checked_in_png_matches_deterministic_generator(self) -> None:
        module = load_generator()
        self.assertEqual(PNG.read_bytes(), module.generate())
        self.assertEqual(PPM.read_bytes(), module.generate_ppm())
        self.assertEqual(len(module.PIXELS), module.WIDTH * module.HEIGHT)

    def test_png_contains_exact_normative_rgb_vector(self) -> None:
        module = load_generator()
        width, height, rgb = decode_generated_rgb8(PNG.read_bytes())
        self.assertEqual((width, height), (module.WIDTH, module.HEIGHT))
        expected = bytes(
            component
            for pixel in module.PIXELS
            for component in pixel
        )
        self.assertEqual(rgb, expected)
        self.assertEqual(
            hashlib.sha256(PNG.read_bytes()).hexdigest(),
            "33e1986427384be02803fe5e8785f3068d17bbacaf6fb6f5b7f880cfea188ea2",
        )


def load_generator():
    spec = importlib.util.spec_from_file_location("mfsk_fixture_generator", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_generated_rgb8(png: bytes) -> tuple[int, int, bytes]:
    self_signature = b"\x89PNG\r\n\x1a\n"
    if not png.startswith(self_signature):
        raise AssertionError("invalid PNG signature")
    offset = len(self_signature)
    width = height = 0
    compressed = bytearray()
    while offset < len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        kind = png[offset + 4 : offset + 8]
        payload = png[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise AssertionError("fixture is not non-interlaced RGB8")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    rows = zlib.decompress(compressed)
    stride = width * 3
    rgb = bytearray()
    for row in range(height):
        start = row * (stride + 1)
        if rows[start] != 0:
            raise AssertionError("fixture does not use PNG filter zero")
        rgb.extend(rows[start + 1 : start + 1 + stride])
    return width, height, bytes(rgb)


if __name__ == "__main__":
    unittest.main()
