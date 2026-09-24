"""Time-aligned, truth-anchored estimates of MFSK output quality."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import numpy as np
from scipy.ndimage import median_filter

from .resources import load_json


METHOD = "reference-fidelity-proxy.v1"
MIN_TEXT_WEIGHT = 2.0
MIN_PICTURE_COMPONENTS = 20
TEXT_VALID_BASE = 0.79
TEXT_MARGIN_GAIN = 0.257
PICTURE_CLIP_PENALTY = 0.4
PICTURE_ROUGHNESS_PENALTY = 0.4
PICTURE_ROUGHNESS_THRESHOLD = 40


def add_decode_confidence(
    quality: Mapping[str, Any],
    source: Mapping[str, Any],
    text_manifest: Mapping[str, Any],
    *,
    artifact_root: Path,
) -> dict[str, Any]:
    """Estimate output fidelity from decoder evidence, without using IQ power.

    The score is a truth-anchored proxy, not observed accuracy or a probability.
    Picture evidence uses clipping and spatial outliers because saved
    stability and quality_hz saturate on the full-broadcast reference capture.
    """
    _check_identity(quality, source, text_manifest)
    document = copy.deepcopy(quality)
    points = document["points"]
    count = document["grid"]["point_count"]
    if len(points) != count:
        raise ValueError("quality point count disagrees with grid")
    origin = document["grid"]["origin_sample"]
    rate = float(document["input"]["sample_rate_hz"])
    text_margin_sum = np.zeros(count, dtype=np.float64)
    text_valid_weight = np.zeros(count, dtype=np.float64)
    text_weight = np.zeros(count, dtype=np.float64)
    picture_scores = np.full(count, np.nan, dtype=np.float64)
    picture_coverage = np.zeros(count, dtype=np.float64)
    text_intervals = [
        item["interval"]
        for segment in text_manifest["mode_segments"]
        for item in segment["items"] if item["kind"] == "text"
    ]
    picture_items = [
        item
        for segment in text_manifest["mode_segments"]
        for item in segment["items"] if item["kind"] == "picture"
    ]
    picture_by_id = {item["id"]: item for item in source["pictures"]}
    artifacts = {item["id"]: item for item in source["artifacts"]}
    warnings = [
        item for item in document["warnings"]
        if item.get("code") != "decode-confidence-pending"
    ]

    for event in source["text_events"]:
        if event.get("control_role") in ("STX", "EOT", "NUL"):
            continue
        interval = event["wire_interval"]
        first = max(0, math.floor((interval["start"] - origin) / rate))
        last = min(count - 1, math.floor((interval["stop"] - 1 - origin) / rate))
        if last < first:
            continue
        valid, margin = _event_margin(event)
        for index in range(first, last + 1):
            second_start = origin + math.floor(index * rate)
            second_stop = origin + math.floor((index + 1) * rate)
            overlap = max(
                (
                    _overlap(interval["start"], interval["stop"],
                             max(second_start, item["start"]),
                             min(second_stop, item["stop"]))
                    for item in text_intervals
                ),
                default=0,
            )
            if overlap <= 0:
                continue
            weight = overlap / max(1, interval["stop"] - interval["start"])
            if valid:
                text_margin_sum[index] += margin * weight
                text_valid_weight[index] += weight
            text_weight[index] += weight

    missing_picture = False
    for item in picture_items:
        picture_coverage += _interval_coverage(
            item["interval"], origin, rate, count
        )
        picture = picture_by_id.get(item["id"])
        inline = picture.get("component_evidence", []) if picture else []
        if inline:
            positions = np.asarray(
                [record["input_interval"]["start"] for record in inline],
                dtype=np.float64,
            )
            clipped = np.asarray(
                ["clipped" in record["damage_flags"] for record in inline],
                dtype=bool,
            )
            values = np.asarray([record["value"] for record in inline], dtype=np.uint8)
        else:
            artifact = artifacts.get(picture.get("component_evidence_artifact")) if picture else None
            if artifact is None or artifact.get("kind") != "npz_component_evidence":
                missing_picture = True
                warnings.append({
                    "code": "decode-confidence-picture-evidence-missing",
                    "message": f"{item['id']} has no component evidence",
                })
                continue
            path = artifact_root / artifact["path"]
            if not path.is_file():
                missing_picture = True
                warnings.append({
                    "code": "decode-confidence-picture-evidence-missing",
                    "message": f"{item['id']} component evidence file is unavailable",
                })
                continue
            with np.load(path, allow_pickle=False) as data:
                component_start = float(data["input_start"][0])
                component_step = float(data["input_samples_per_component"][0])
                clipped = np.asarray(data["clipped"], dtype=bool)
                values = np.asarray(data["value"], dtype=np.uint8)
            if not math.isfinite(component_step) or component_step <= 0:
                raise ValueError(f"invalid component clock for {item['id']}")
            positions = component_start + np.arange(len(clipped)) * component_step
        if len(values) != len(clipped) or len(positions) != len(clipped):
            raise ValueError(f"component evidence lengths disagree for {item['id']}")
        rough = _picture_roughness(values, picture)
        eligible = (
            (positions >= item["interval"]["start"])
            & (positions < item["interval"]["stop"])
            & (positions >= origin)
            & (positions < document["input"]["requested_interval"]["stop"])
        )
        indices = np.floor((positions[eligible] - origin) / rate).astype(np.int64)
        valid = (indices >= 0) & (indices < count)
        totals = np.bincount(indices[valid], minlength=count)
        failures = np.bincount(
            indices[valid], weights=clipped[eligible][valid].astype(float),
            minlength=count,
        )
        rough_counts = np.bincount(
            indices[valid], weights=rough[eligible][valid].astype(float),
            minlength=count,
        )
        available = totals >= MIN_PICTURE_COMPONENTS
        scores = np.maximum(
            0.0,
            1.0 - (
                PICTURE_CLIP_PENALTY * failures[available]
                + PICTURE_ROUGHNESS_PENALTY * rough_counts[available]
            ) / totals[available],
        )
        picture_scores[available] = scores

    for index, point in enumerate(points):
        if picture_coverage[index] >= 0.5:
            point[2] = (
                round(float(picture_scores[index]), 3)
                if math.isfinite(picture_scores[index]) else None
            )
        elif text_weight[index] >= MIN_TEXT_WEIGHT:
            point[2] = round(float(min(1.0, (
                TEXT_VALID_BASE * text_valid_weight[index]
                + TEXT_MARGIN_GAIN * text_margin_sum[index]
            ) / text_weight[index])), 3)
        else:
            point[2] = None

    document["methods"]["decode_confidence"] = {
        "id": METHOD,
        "calibrated_error_probability": False,
        "text_event_score": {
            "minimum_absolute_input_llr": "1-exp(-value)",
            "normalized_viterbi_decision_path_metric_gap": "clamp(value,0,1)",
            "formula": "clamp((0.79*valid_weight + 0.257*valid_margin_sum)/all_event_weight,0,1)",
            "invalid_varicode": "contributes to all_event_weight only",
            "aggregation": "wire_overlap_weighted_ratio",
            "minimum_effective_events_per_second": MIN_TEXT_WEIGHT,
        },
        "picture_component_score": {
            "evidence": "out_of_range_and_spatial_outlier_component_fractions",
            "formula": "clamp(1-0.4*clipped_fraction-0.4*spatial_outlier_fraction,0,1)",
            "spatial_outlier": "absolute component difference from 3x3 spatial median > 40/255",
            "minimum_components_per_second": MIN_PICTURE_COMPONENTS,
            "incomplete_picture_multiplier": 1.0,
            "stability_fields_used": False,
        },
        "reference_fit": {
            "source": "received-corpus program 456 independent text and image truth",
            "text_target": "fraction of emitted characters matching aligned source text in five-second windows",
            "picture_target": "1-mean_absolute_component_error/255 in five-second windows",
            "validation": "hold out each text mode and each of three complete pictures",
        },
    }
    document["status"] = (
        "complete"
        if source["status"] == "complete" and not missing_picture
        and not document["exceptions"]
        else "partial"
    )
    document["warnings"] = warnings
    jsonschema.Draft202012Validator(
        load_json("schemas", "grampy-quality-manifest-v1.json")
    ).validate(document)
    return document


def _check_identity(*documents: Mapping[str, Any]) -> None:
    run_ids = {document["run_id"] for document in documents}
    identities = {
        (document["input"]["metadata_sha256"], document["input"]["data_sha256"],
         document["input"]["requested_interval"]["start"],
         document["input"]["requested_interval"]["stop"])
        for document in documents
    }
    if len(run_ids) != 1 or len(identities) != 1:
        raise ValueError("quality, decode, and text sources do not describe the same run")


def _event_margin(event: Mapping[str, Any]) -> tuple[bool, float]:
    if event["octet"] is None or "invalid_varicode" in event.get("damage_flags", []):
        return False, 0.0
    confidence = event["confidence"]
    value = float(confidence["value"])
    if not math.isfinite(value) or value < 0:
        return False, 0.0
    if confidence["kind"] == "minimum_absolute_input_llr":
        return True, -math.expm1(-value)
    if confidence["kind"] == "normalized_viterbi_decision_path_metric_gap":
        return True, min(1.0, value)
    raise ValueError(f"unsupported text confidence kind: {confidence['kind']}")


def _picture_roughness(values: np.ndarray, picture: Mapping[str, Any]) -> np.ndarray:
    height = int(picture["height"])
    width = int(picture["width"])
    color = bool(picture["color"])
    expected = height * width * (3 if color else 1)
    if height <= 0 or width <= 0 or len(values) > expected:
        raise ValueError(f"invalid component geometry for {picture['id']}")
    raster = np.zeros(expected, dtype=np.uint8)
    raster[:len(values)] = values
    if color:
        display = raster.reshape(height, 3, width).transpose(0, 2, 1)
        typical = median_filter(display, size=(3, 3, 1), mode="nearest")
        difference = np.abs(display.astype(np.int16) - typical.astype(np.int16))
        ordered = difference.transpose(0, 2, 1).reshape(-1)
    else:
        display = raster.reshape(height, width)
        typical = median_filter(display, size=(3, 3), mode="nearest")
        ordered = np.abs(display.astype(np.int16) - typical.astype(np.int16)).reshape(-1)
    return ordered[:len(values)] > PICTURE_ROUGHNESS_THRESHOLD


def _overlap(start: float, stop: float, other_start: float, other_stop: float) -> float:
    return max(0.0, min(stop, other_stop) - max(start, other_start))


def _interval_coverage(
    interval: Mapping[str, int], origin: int, rate: float, count: int
) -> np.ndarray:
    coverage = np.zeros(count, dtype=np.float64)
    first = max(0, math.floor((interval["start"] - origin) / rate))
    last = min(count - 1, math.floor((interval["stop"] - 1 - origin) / rate))
    for index in range(first, last + 1):
        start = origin + math.floor(index * rate)
        stop = origin + math.floor((index + 1) * rate)
        coverage[index] = _overlap(interval["start"], interval["stop"], start, stop) / (stop - start)
    return coverage
