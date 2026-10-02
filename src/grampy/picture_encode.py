"""Bounded PNG normalization and isolated MFSK picture-raster planning.

The text announcement, text-path flushes, prologue, and resumed text are
deliberately not represented here.  Those stateful transitions belong to the
next encoder slice.  This module only owns the PNG profile and the analog
pixel-component raster that follows that transition.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Literal

from PIL import Image, UnidentifiedImageError

from .mfsk_encode import MAX_WAV_FRAMES, _validate_carrier, _validate_sample_rate
from .text_encode import MODE_PARAMETERS, MfskMode


PictureColor = Literal["color", "grayscale"]
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_PICTURE_DIMENSION = 4095


@dataclass(frozen=True)
class NormalizedPicture:
    """A decoded source raster retained in its accepted source form.

    ``source_pixels`` is one 8-bit L or RGB decoded image.  Component order
    and grayscale conversion are streamed from it, avoiding a second complete
    normalized raster allocation.
    """

    width: int
    height: int
    color: PictureColor
    samples_per_pixel: int
    source_mode: Literal["L", "RGB"]
    source_pixels: bytes

    @property
    def component_count(self) -> int:
        return self.width * self.height * (3 if self.color == "color" else 1)

    def iter_component_values(self) -> Iterator[int]:
        if self.source_mode == "L":
            if self.color == "grayscale":
                yield from self.source_pixels
                return
            for value in self.source_pixels:
                yield value
                yield value
                yield value
            return

        if self.color == "grayscale":
            for offset in range(0, len(self.source_pixels), 3):
                red, green, blue = self.source_pixels[offset : offset + 3]
                yield (31 * red + 61 * green + 8 * blue) // 100
            return

        row_bytes = self.width * 3
        for row_start in range(0, len(self.source_pixels), row_bytes):
            row = self.source_pixels[row_start : row_start + row_bytes]
            for component in range(3):
                yield from row[component::3]


@dataclass(frozen=True)
class RasterEvent:
    value: int
    frequency_hz: float
    frame_count: int


@dataclass(frozen=True)
class PictureRasterPlan:
    picture: NormalizedPicture
    mode: MfskMode
    carrier_hz: float
    sample_rate_hz: int
    frames_per_component: int
    frame_count: int

    @property
    def pcm_data_bytes(self) -> int:
        return self.frame_count * 2

    def iter_events(self) -> Iterator[RasterEvent]:
        bandwidth = MODE_PARAMETERS[self.mode].tone_span_hz
        for value in self.picture.iter_component_values():
            yield RasterEvent(
                value=value,
                frequency_hz=self.carrier_hz + bandwidth * (value - 128) / 256,
                frame_count=self.frames_per_component,
            )


def picture_control_token(picture: NormalizedPicture) -> bytes:
    """Return the exact fldigi picture-control token for a normalized raster."""
    if not isinstance(picture, NormalizedPicture):
        raise TypeError("picture must be a NormalizedPicture")
    color_marker = "C" if picture.color == "color" else ""
    speed_marker = (
        "" if picture.samples_per_pixel == 8 else f"p{picture.samples_per_pixel}"
    )
    return (
        f"Pic:{picture.width}x{picture.height}{color_marker}{speed_marker};"
    ).encode("ascii")


def picture_announcement(picture: NormalizedPicture) -> bytes:
    """Return fldigi's conventional line-feed-prefixed announcement."""
    return b"\nSending " + picture_control_token(picture)


def normalize_png(
    path: Path,
    *,
    color: PictureColor,
    samples_per_pixel: int,
) -> NormalizedPicture:
    """Decode exactly the v1 PNG profile, without resizing or conversion."""
    if color not in ("color", "grayscale"):
        raise ValueError("picture color must be 'color' or 'grayscale'")
    _validate_samples_per_pixel(samples_per_pixel)
    path = Path(path)
    if path.stat().st_size > MAX_PNG_BYTES:
        raise ValueError("PNG input exceeds the 64 MiB limit")

    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("image input must be a PNG file")
            if image.mode not in ("L", "RGB"):
                raise ValueError("PNG input must be an 8-bit L or RGB image without alpha")
            if "transparency" in image.info:
                raise ValueError("PNG transparency is not supported")
            if not 1 <= image.width <= MAX_PICTURE_DIMENSION or not 1 <= image.height <= MAX_PICTURE_DIMENSION:
                raise ValueError("PNG dimensions must each be from 1 through 4095")
            image.load()
            source_mode: Literal["L", "RGB"] = image.mode
            source_pixels = image.tobytes()
    except (UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError("image input must be a valid PNG file") from error
    except OSError as error:
        if isinstance(error, (FileNotFoundError, PermissionError, IsADirectoryError)):
            raise
        raise ValueError("image input must be a valid PNG file") from error

    return NormalizedPicture(
        width=image.width,
        height=image.height,
        color=color,
        samples_per_pixel=samples_per_pixel,
        source_mode=source_mode,
        source_pixels=source_pixels,
    )


def plan_picture_raster(
    picture: NormalizedPicture,
    *,
    mode: MfskMode,
    carrier_hz: float,
    sample_rate_hz: int,
) -> PictureRasterPlan:
    """Plan a streaming analog raster without adding any text transition."""
    if not isinstance(picture, NormalizedPicture):
        raise TypeError("picture must be a NormalizedPicture")
    if mode not in MODE_PARAMETERS:
        raise ValueError(f"unsupported MFSK mode: {mode}")
    _validate_sample_rate(sample_rate_hz)
    carrier = _validate_carrier(mode, carrier_hz, sample_rate_hz)
    frames_per_component = picture.samples_per_pixel * (sample_rate_hz // 8_000)
    frame_count = picture.component_count * frames_per_component
    if frame_count > MAX_WAV_FRAMES:
        raise ValueError("picture raster exceeds the classic RIFF/WAVE limit")
    return PictureRasterPlan(
        picture=picture,
        mode=mode,
        carrier_hz=carrier,
        sample_rate_hz=sample_rate_hz,
        frames_per_component=frames_per_component,
        frame_count=frame_count,
    )


def _validate_samples_per_pixel(samples_per_pixel: int) -> None:
    if (
        isinstance(samples_per_pixel, bool)
        or not isinstance(samples_per_pixel, int)
        or samples_per_pixel not in (2, 4, 8)
    ):
        raise ValueError("picture samples per pixel must be 2, 4, or 8")


__all__ = [
    "MAX_PICTURE_DIMENSION",
    "MAX_PNG_BYTES",
    "NormalizedPicture",
    "PictureColor",
    "PictureRasterPlan",
    "RasterEvent",
    "normalize_png",
    "picture_announcement",
    "picture_control_token",
    "plan_picture_raster",
]
