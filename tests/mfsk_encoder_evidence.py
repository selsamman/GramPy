"""Independent test oracle for the native MFSK WAV encoder.

This module deliberately contains no imports from encoder production code.
Future encoder tests pass candidate events into these helpers and compare them
with the checked-in protocol evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


WIRE_VECTORS_SHA256 = (
    "e98ecc1982c97d4362846c6cf56e163cab035f73c9c9bc35b2406bccb613e4bc"
)
VARICODE_SHA256 = (
    "8e40e8927059dc592f97f15e1a96d2ad430c284f1d074c8df61e0847ffaf27a3"
)
FIXTURE_EVIDENCE_SHA256 = (
    "062fbfe512c32c645c4f16b83d8076aea7e481fdb0bd3c4c97735423d6055cb2"
)
PRIMARY_RGB_PPM_SHA256 = (
    "21d5e19be8566a266d8c01f214e4049b59b9fdbba96ab1069178e88a548dc104"
)

BINARY_LABEL_TO_TONE_INDEX = (
    0, 1, 3, 2, 7, 6, 4, 5, 15, 14, 12, 13, 8, 9, 11, 10
)
MODE_PARAMETERS = {
    "MFSK32": {
        "symbols_per_second": 31.25,
        "tone_spacing_hz": 31.25,
        "tone_span_hz": 468.75,
        "preamble_input_bits": 107,
        "leading_zero_input_bits": 35,
    },
    "MFSK64": {
        "symbols_per_second": 62.5,
        "tone_spacing_hz": 62.5,
        "tone_span_hz": 937.5,
        "preamble_input_bits": 180,
        "leading_zero_input_bits": 60,
    },
}


class EvidenceMismatch(AssertionError):
    """A candidate event differs from the independent encoder oracle."""


@dataclass(frozen=True)
class SymbolCount:
    complete_symbols: int
    residual_coded_bits: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return document


def require_exact(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise EvidenceMismatch(f"{label}: expected {expected!r}, got {actual!r}")


def require_close(
    label: str,
    actual: float,
    expected: float,
    *,
    absolute_tolerance: float = 1e-12,
) -> None:
    if abs(actual - expected) > absolute_tolerance:
        raise EvidenceMismatch(f"{label}: expected {expected!r}, got {actual!r}")


def convolutional_encode(input_bits: str, *, initial_state: int = 0) -> str:
    state = initial_state
    output: list[str] = []
    for character in input_bits:
        if character not in "01":
            raise ValueError("convolutional input must contain only zero and one")
        state = ((state << 1) | int(character)) & 0x7F
        output.extend(
            str((state & mask).bit_count() & 1) for mask in (0x6D, 0x4F)
        )
    return "".join(output)


def interleave_groups(groups: Sequence[Sequence[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for index, group in enumerate(groups):
        if len(group) != 4:
            raise ValueError("each interleaver input group must contain four bits")
        result.append(
            [
                int(group[0]),
                int(groups[index - 10][1]) if index >= 10 else 0,
                int(groups[index - 20][2]) if index >= 20 else 0,
                int(groups[index - 30][3]) if index >= 30 else 0,
            ]
        )
    return result


def binary_labels(groups: Iterable[Sequence[int]]) -> list[int]:
    return [
        sum(int(bit) << (3 - index) for index, bit in enumerate(group))
        for group in groups
    ]


def physical_tone_indices(labels: Iterable[int]) -> list[int]:
    result: list[int] = []
    for label in labels:
        if isinstance(label, bool) or not 0 <= label <= 15:
            raise ValueError("tone labels must be integers from zero through fifteen")
        result.append(BINARY_LABEL_TO_TONE_INDEX[label])
    return result


def count_symbols(input_bit_count: int, *, pending_coded_bits: int = 0) -> SymbolCount:
    if input_bit_count < 0 or pending_coded_bits not in (0, 2):
        raise ValueError("invalid symbol-count inputs")
    coded_bits = pending_coded_bits + 2 * input_bit_count
    return SymbolCount(coded_bits // 4, coded_bits % 4)


def picture_control_token(
    width: int,
    height: int,
    *,
    color: bool,
    samples_per_pixel: int,
) -> bytes:
    if width <= 0 or height <= 0:
        raise ValueError("picture dimensions must be positive")
    if samples_per_pixel not in (2, 4, 8):
        raise ValueError("unsupported picture speed")
    color_marker = "C" if color else ""
    speed_marker = "" if samples_per_pixel == 8 else f"p{samples_per_pixel}"
    return f"Pic:{width}x{height}{color_marker}{speed_marker};".encode("ascii")


def prologue_output_frames(sample_rate_hz: int) -> int:
    if sample_rate_hz <= 0 or sample_rate_hz % 8000:
        raise ValueError("sample rate must be a positive multiple of 8000")
    return 352 * (sample_rate_hz // 8000)


def raster_output_frames(
    width: int,
    height: int,
    *,
    color: bool,
    samples_per_pixel: int,
    sample_rate_hz: int,
) -> int:
    if width <= 0 or height <= 0:
        raise ValueError("picture dimensions must be positive")
    if samples_per_pixel not in (2, 4, 8):
        raise ValueError("unsupported picture speed")
    if sample_rate_hz <= 0 or sample_rate_hz % 8000:
        raise ValueError("sample rate must be a positive multiple of 8000")
    components = width * height * (3 if color else 1)
    return components * samples_per_pixel * (sample_rate_hz // 8000)


def grayscale_values(pixels: Sequence[tuple[int, int, int]]) -> tuple[int, ...]:
    return tuple(
        (31 * red + 61 * green + 8 * blue) // 100
        for red, green, blue in pixels
    )


def color_row_plane_values(
    width: int,
    height: int,
    pixels: Sequence[tuple[int, int, int]],
) -> tuple[int, ...]:
    if len(pixels) != width * height:
        raise ValueError("pixel count does not match dimensions")
    result: list[int] = []
    for row in range(height):
        row_pixels = pixels[row * width : (row + 1) * width]
        for component in range(3):
            result.extend(pixel[component] for pixel in row_pixels)
    return tuple(result)


def pixel_frequencies(
    values: Iterable[int],
    *,
    mode: str,
    carrier_hz: float,
) -> tuple[float, ...]:
    try:
        bandwidth = MODE_PARAMETERS[mode]["tone_span_hz"]
    except KeyError as error:
        raise ValueError(f"unsupported mode: {mode}") from error
    return tuple(
        carrier_hz + bandwidth * (int(value) - 128) / 256
        for value in values
    )


def read_ppm(path: Path) -> tuple[int, int, tuple[tuple[int, int, int], ...]]:
    parts = path.read_bytes().split(maxsplit=4)
    if len(parts) != 5 or parts[0] != b"P6" or parts[3] != b"255":
        raise ValueError("expected a simple maxval-255 binary P6 PPM")
    width, height = int(parts[1]), int(parts[2])
    raster = parts[4]
    if len(raster) != width * height * 3:
        raise ValueError("PPM raster length does not match its dimensions")
    pixels = tuple(
        (raster[offset], raster[offset + 1], raster[offset + 2])
        for offset in range(0, len(raster), 3)
    )
    return width, height, pixels
