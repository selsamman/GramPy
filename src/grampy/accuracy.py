from __future__ import annotations

from dataclasses import dataclass
import difflib
import math
import re
from typing import Any

import numpy as np


ACCURACY_SCHEMA = "grampy-accuracy.v1"
_LINE_ENDING = re.compile(r"\r\n|\r|\n")
_PRESENTATION_SPACE = re.compile(r"[ \t\f\v]+")


@dataclass(frozen=True)
class FramedPayload:
    text: str
    frame_count: int
    unmatched_stx: int
    unmatched_eot: int
    discarded_prefix_characters: int
    discarded_interframe_characters: int
    discarded_suffix_characters: int

    def diagnostics(self) -> dict[str, int]:
        return {
            "frame_count": self.frame_count,
            "unmatched_stx": self.unmatched_stx,
            "unmatched_eot": self.unmatched_eot,
            "discarded_prefix_characters": self.discarded_prefix_characters,
            "discarded_interframe_characters": self.discarded_interframe_characters,
            "discarded_suffix_characters": self.discarded_suffix_characters,
        }


def extract_framed_payload(decoded: str) -> FramedPayload:
    """Concatenate complete STX/EOT payloads and report discarded material.

    Framing is deliberately not inferred for incomplete epochs. Missing framing
    is a decoder diagnostic; any resulting missing program content is measured
    by the separate truth-relative text comparison.
    """

    payloads: list[str] = []
    cursor = 0
    first_stx: int | None = None
    last_eot: int | None = None
    discarded_interframe = 0
    unmatched_stx = 0
    unmatched_eot = 0

    while cursor < len(decoded):
        stx = decoded.find("\x02", cursor)
        eot_before = decoded.find("\x04", cursor, stx if stx >= 0 else len(decoded))
        while eot_before >= 0:
            unmatched_eot += 1
            cursor = eot_before + 1
            eot_before = decoded.find(
                "\x04", cursor, stx if stx >= 0 else len(decoded)
            )
        if stx < 0:
            break
        if first_stx is None:
            first_stx = stx
        elif stx > cursor:
            discarded_interframe += stx - cursor
        eot = decoded.find("\x04", stx + 1)
        next_stx = decoded.find("\x02", stx + 1)
        if eot < 0 or (next_stx >= 0 and next_stx < eot):
            unmatched_stx += 1
            cursor = stx + 1
            continue
        payloads.append(decoded[stx + 1 : eot])
        last_eot = eot
        cursor = eot + 1

    if first_stx is None:
        prefix = len(decoded)
        suffix = 0
    else:
        prefix = first_stx
        suffix = len(decoded) - (last_eot + 1 if last_eot is not None else cursor)
    return FramedPayload(
        text="".join(payloads),
        frame_count=len(payloads),
        unmatched_stx=unmatched_stx,
        unmatched_eot=unmatched_eot,
        discarded_prefix_characters=prefix,
        discarded_interframe_characters=discarded_interframe,
        discarded_suffix_characters=max(0, suffix),
    )


def normalize_presentation_text(text: str) -> str:
    """Normalize transcript line wrapping without altering visible content."""

    joined = _LINE_ENDING.sub(" ", text)
    return _PRESENTATION_SPACE.sub(" ", joined).strip()


def score_text(reference: str, decoded: str) -> dict[str, Any]:
    """Return a deterministic first-generation character scorecard.

    SequenceMatcher supplies stable matching blocks. A replace block consumes
    paired characters as substitutions and counts any length imbalance as
    insertions or deletions. The declared algorithm is part of the result so a
    later evaluator can change alignment methods without silently changing old
    scores.
    """

    matcher = difflib.SequenceMatcher(a=reference, b=decoded, autojunk=False)
    substitutions = deletions = insertions = matches = 0
    longest = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        left = i2 - i1
        right = j2 - j1
        if tag == "equal":
            matches += left
            longest = max(longest, left)
        elif tag == "delete":
            deletions += left
        elif tag == "insert":
            insertions += right
        else:
            paired = min(left, right)
            substitutions += paired
            deletions += left - paired
            insertions += right - paired
    errors = substitutions + deletions + insertions
    return {
        "schema": ACCURACY_SCHEMA,
        "kind": "text",
        "alignment_algorithm": "python-difflib-sequence-matcher-v1",
        "reference_characters": len(reference),
        "decoded_characters": len(decoded),
        "matches": matches,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "error_count": errors,
        "character_error_rate": errors / len(reference) if reference else None,
        "reference_coverage": matches / len(reference) if reference else None,
        "longest_correct_run": longest,
        "exact": reference == decoded,
    }


def score_mode_sequence(
    expected: list[str], detected: list[dict[str, Any]]
) -> dict[str, Any]:
    """Score ordered acquisition events without inventing coordinate truth."""

    observed = [event["mode"] for event in detected]
    matcher = difflib.SequenceMatcher(a=expected, b=observed, autojunk=False)
    matched_expected: set[int] = set()
    matched_detected: set[int] = set()
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            matched_expected.add(block.a + offset)
            matched_detected.add(block.b + offset)
    matches = len(matched_expected)
    missed = [
        {"expected_order": index + 1, "mode": mode}
        for index, mode in enumerate(expected)
        if index not in matched_expected
    ]
    false = [
        {"detected_order": index + 1, **event}
        for index, event in enumerate(detected)
        if index not in matched_detected
    ]
    return {
        "schema": ACCURACY_SCHEMA,
        "kind": "mode-event-sequence",
        "alignment_algorithm": "python-difflib-sequence-matcher-v1",
        "truth_scope": "ordered_mode_change_sequence",
        "coordinate_truth_status": "not_available",
        "expected_count": len(expected),
        "detected_count": len(detected),
        "matched_count": matches,
        "missed_count": len(missed),
        "false_count": len(false),
        "recall": matches / len(expected) if expected else None,
        "precision": matches / len(detected) if detected else None,
        "exact": expected == observed,
        "expected_modes": expected,
        "detected_events": detected,
        "missed_events": missed,
        "false_events": false,
    }


def image_to_wire_components(image: np.ndarray) -> np.ndarray:
    """Flatten a uint8 grayscale/RGB raster in MFSK transmitted component order."""

    values = np.asarray(image)
    if values.dtype != np.uint8:
        raise ValueError("image must use uint8 components")
    if values.ndim == 2:
        return values.reshape(-1)
    if values.ndim != 3 or values.shape[2] != 3:
        raise ValueError("image must be grayscale HxW or RGB HxWx3")
    # Color is transmitted as one R row, one G row, then one B row.
    return values.transpose(0, 2, 1).reshape(-1)


def load_png_wire_components(
    path: str, *, expected_color: bool | None = None
) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - environment diagnosis
        raise RuntimeError(
            "PNG scoring requires the declared Pillow dependency"
        ) from error
    with Image.open(path) as source:
        if expected_color is None:
            mode = "L" if source.mode == "L" else "RGB"
        else:
            mode = "RGB" if expected_color else "L"
        converted = source.convert(mode)
        image = np.asarray(converted, dtype=np.uint8)
    return image_to_wire_components(image), {
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "mode": mode,
    }


def load_png_raster(
    path: str, *, expected_color: bool | None = None
) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - environment diagnosis
        raise RuntimeError(
            "PNG scoring requires the declared Pillow dependency"
        ) from error
    with Image.open(path) as source:
        if expected_color is None:
            mode = "L" if source.mode == "L" else "RGB"
        else:
            mode = "RGB" if expected_color else "L"
        image = np.asarray(source.convert(mode), dtype=np.uint8)
    return image, {
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "mode": mode,
    }


def score_raw_rasters(reference: np.ndarray, decoded: np.ndarray) -> dict[str, Any]:
    """Report same-position whole-raster and per-channel error."""

    truth = np.asarray(reference)
    observed = np.asarray(decoded)
    if truth.shape != observed.shape:
        raise ValueError(
            f"raster shapes differ: truth {truth.shape}, decoded {observed.shape}"
        )
    if truth.dtype != np.uint8 or observed.dtype != np.uint8:
        raise ValueError("rasters must use uint8 components")

    def metrics(left: np.ndarray, right: np.ndarray) -> dict[str, float | None]:
        delta = right.astype(np.float64) - left.astype(np.float64)
        mae = float(np.mean(np.abs(delta)))
        mse = float(np.mean(np.square(delta)))
        rmse = math.sqrt(mse)
        return {
            "mean_absolute_error_255": mae,
            "root_mean_square_error_255": rmse,
            "signed_bias_255": float(np.mean(delta)),
            "exact_component_fraction": float(np.mean(delta == 0)),
            "psnr_db": None if mse == 0 else 20.0 * math.log10(255.0 / rmse),
        }

    if truth.ndim == 2:
        channels = {"gray": metrics(truth, observed)}
    elif truth.ndim == 3 and truth.shape[2] == 3:
        channels = {
            name: metrics(truth[:, :, index], observed[:, :, index])
            for index, name in enumerate(("red", "green", "blue"))
        }
    else:
        raise ValueError("rasters must be grayscale HxW or RGB HxWx3")
    return {
        "schema": ACCURACY_SCHEMA,
        "kind": "raw-raster-error",
        "whole_raster": metrics(truth, observed),
        "channels": channels,
    }


def score_picture_truth_availability(
    *, truth_status: str, truth_path_exists: bool
) -> dict[str, str]:
    if truth_status == "missing":
        return {
            "status": "not_scored_missing_truth",
            "reason": "program manifest explicitly declares absent pixel truth",
        }
    if not truth_path_exists:
        return {
            "status": "error_truth_artifact_missing",
            "reason": "program manifest references a missing truth artifact",
        }
    return {"status": "scored", "reason": "pixel truth available"}


def align_component_streams(
    reference: np.ndarray,
    decoded: np.ndarray,
    *,
    max_offset: int = 24,
    change_penalty: float = 25.0,
    offset_penalty: float = 0.0005,
) -> dict[str, Any]:
    """Find a regularized, bounded offset path through two component streams.

    The path may remain at its current offset or move one component per step.
    This represents constant phase, gradual drift, and persistent slips while
    making rapid noise-following expensive. The path and its burden are output,
    not hidden preprocessing.
    """

    truth = np.asarray(reference, dtype=np.float32).reshape(-1)
    observed = np.asarray(decoded, dtype=np.float32).reshape(-1)
    if not len(truth) or not len(observed):
        raise ValueError("component streams must not be empty")
    count = min(len(truth), len(observed))
    raw_absolute = np.abs(truth[:count] - observed[:count])
    offsets = np.arange(-max_offset, max_offset + 1, dtype=np.int16)
    states = len(offsets)
    infinity = np.float64(1e30)
    previous = np.full(states, infinity, dtype=np.float64)
    back = np.zeros((count, states), dtype=np.int8)

    def emissions(index: int) -> np.ndarray:
        positions = index + offsets.astype(np.int64)
        valid = (positions >= 0) & (positions < len(truth))
        result = np.full(states, infinity, dtype=np.float64)
        result[valid] = (
            np.abs(truth[positions[valid]] - observed[index]) / 255.0
            + offset_penalty * np.abs(offsets[valid])
        )
        return result

    previous = emissions(0)
    for index in range(1, count):
        stay = previous
        from_lower = np.concatenate(([infinity], previous[:-1] + change_penalty))
        from_upper = np.concatenate((previous[1:] + change_penalty, [infinity]))
        choices = np.stack((from_lower, stay, from_upper))
        selected = np.argmin(choices, axis=0)
        back[index] = selected.astype(np.int8) - 1
        previous = emissions(index) + choices[selected, np.arange(states)]

    state = int(np.argmin(previous))
    path = np.empty(count, dtype=np.int16)
    path[-1] = offsets[state]
    for index in range(count - 1, 0, -1):
        state += int(back[index, state])
        path[index - 1] = offsets[state]

    positions = np.arange(count, dtype=np.int64) + path
    valid = (positions >= 0) & (positions < len(truth))
    absolute = np.abs(truth[positions[valid]] - observed[:count][valid])
    changes = np.flatnonzero(np.diff(path) != 0) + 1
    segment_starts = np.concatenate(([0], changes))
    segment_stops = np.concatenate((changes, [count]))
    return {
        "schema": ACCURACY_SCHEMA,
        "kind": "picture-component-alignment",
        "algorithm": "bounded-regularized-offset-viterbi-v1",
        "reference_components": int(len(truth)),
        "decoded_components": int(len(observed)),
        "compared_components": int(np.count_nonzero(valid)),
        "raw_mean_absolute_error_255": float(np.mean(raw_absolute)),
        "raw_exact_component_fraction": float(np.mean(raw_absolute == 0)),
        "aligned_mean_absolute_error_255": float(np.mean(absolute)),
        "aligned_exact_component_fraction": float(np.mean(absolute == 0)),
        "zero_offset_fraction": float(np.mean(path == 0)),
        "maximum_absolute_offset_components": int(np.max(np.abs(path))),
        "offset_change_count": int(len(changes)),
        "offset_changes": [
            {"component_index": int(index), "offset": int(path[index])}
            for index in changes
        ],
        "offset_path_rle": [
            {
                "start_component": int(start),
                "stop_component": int(stop),
                "offset": int(path[start]),
            }
            for start, stop in zip(segment_starts, segment_stops, strict=True)
        ],
        "alignment_parameters": {
            "max_offset_components": max_offset,
            "change_penalty": change_penalty,
            "offset_penalty": offset_penalty,
        },
    }
