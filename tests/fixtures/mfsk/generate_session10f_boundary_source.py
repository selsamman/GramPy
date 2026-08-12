#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


WIDTH = 160
HEIGHT = 120


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Generate the deterministic Session 10F boundary source"
    )
    result.add_argument("--output", required=True, type=Path)
    return result


def main() -> None:
    args = parser().parse_args()
    pixels = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            red = (17 * x + 31 * y + 37 * (x // 8)) % 256
            green = (29 * x + 11 * y + 53 * (y // 8)) % 256
            blue = (7 * x + 43 * y + 19 * ((x + y) // 8)) % 256
            if x == 0 and y == 0:
                red = 255
            pixels.extend((red, green, blue))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii") + pixels
    )


if __name__ == "__main__":
    main()
