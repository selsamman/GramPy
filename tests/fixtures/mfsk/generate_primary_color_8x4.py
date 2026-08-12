#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import struct
import zlib


WIDTH = 8
HEIGHT = 4
PIXELS = (
    (0, 0, 0), (32, 32, 32), (64, 64, 64), (96, 96, 96),
    (128, 128, 128), (160, 160, 160), (224, 224, 224), (255, 255, 255),
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 255, 255),
    (255, 0, 255), (255, 255, 0), (255, 255, 255), (0, 0, 0),
    (17, 0, 0), (127, 0, 0), (239, 0, 0), (0, 17, 0),
    (0, 127, 0), (0, 239, 0), (0, 0, 17), (0, 0, 239),
    (1, 2, 3), (5, 8, 13), (21, 34, 55), (89, 144, 233),
    (254, 129, 65), (7, 251, 131), (193, 31, 227), (240, 15, 129),
)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def generate() -> bytes:
    rows = []
    for row in range(HEIGHT):
        row_pixels = PIXELS[row * WIDTH : (row + 1) * WIDTH]
        rows.append(b"\0" + bytes(component for pixel in row_pixels for component in pixel))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0),
        )
        + png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + png_chunk(b"IEND", b"")
    )


def generate_ppm() -> bytes:
    rgb = bytes(component for pixel in PIXELS for component in pixel)
    return f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii") + rgb


def main() -> None:
    output = Path(__file__).with_name("primary-color-8x4.png")
    output.write_bytes(generate())
    print(output)
    ppm_output = output.with_suffix(".ppm")
    ppm_output.write_bytes(generate_ppm())
    print(ppm_output)


if __name__ == "__main__":
    main()
