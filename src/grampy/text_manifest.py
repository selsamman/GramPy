"""Build the compact, ordered text and picture product from decode results."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

import jsonschema

from .resources import load_json


SCHEMA = "grampy-text-manifest.v1"
SCHEMA_FILE = "grampy-text-manifest-v1.json"


def build_text_manifest(source: Mapping[str, Any]) -> dict[str, Any]:
    """Build display text without copying diagnostic event provenance.

    ``source`` needs the ordinary decode-result fields listed below, and may
    be either the existing diagnostic manifest or a lightweight view of live
    decoder results. No IQ processing or decoder decisions occur here.
    """

    source_input = source["input"]
    requested = dict(source_input["requested_interval"])
    sample_rate = float(source_input["sample_rate_hz"])
    if sample_rate <= 0:
        raise ValueError("sample rate must be positive")
    segments = [
        {
            "id": item["id"],
            "mode": item["mode"],
            "interval": dict(item["interval"]),
            "items": [],
        }
        for item in sorted(
            source["mode_segments"], key=lambda item: item["interval"]["start"]
        )
    ]
    events = list(source["text_events"])
    pictures = list(source["pictures"])
    warnings = [dict(item) for item in source.get("warnings", [])]
    if not segments and (events or pictures):
        configured_mode = source["decoder"]["configuration"].get("mode")
        segments.append({
            "id": "mode-undetermined",
            "mode": configured_mode if configured_mode in {"MFSK32", "MFSK64"} else "unknown",
            "interval": requested.copy(),
            "items": [],
        })
        warnings.append({
            "code": "text-product-mode-undetermined",
            "message": "content was decoded without a resolved mode segment",
        })

    by_id = {segment["id"]: segment for segment in segments}
    grouped_events: dict[str, list[dict[str, Any]]] = {
        segment["id"]: [] for segment in segments
    }
    grouped_pictures: dict[str, list[dict[str, Any]]] = {
        segment["id"]: [] for segment in segments
    }
    for event in events:
        segment = by_id.get(event.get("mode_segment")) or _containing_segment(
            segments, int(event["recognized_at_input_sample"])
        )
        if segment is None:
            warnings.append({
                "code": "text-product-unassigned-event",
                "message": f"event {event['id']} falls outside resolved mode segments",
            })
            continue
        grouped_events[segment["id"]].append(event)
    for picture in pictures:
        start, stop = _picture_interval(picture)
        segment = _containing_segment(segments, start, mode=picture.get("mode"))
        if segment is None:
            warnings.append({
                "code": "text-product-unassigned-picture",
                "message": f"picture {picture['id']} falls outside resolved mode segments",
            })
            continue
        grouped_pictures[segment["id"]].append({
            "source": picture, "start": start, "stop": stop
        })

    artifact_by_id = {item["id"]: item for item in source["artifacts"]}
    omitted: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = segment["id"]
        segment_events = sorted(
            grouped_events[segment_id],
            key=lambda item: item["recognized_at_input_sample"],
        )
        segment_pictures = sorted(
            grouped_pictures[segment_id], key=lambda item: item["start"]
        )
        spans, prefix = _framed_spans(segment_events, segment_id)
        if prefix:
            omission = _omission(prefix, "before_stx")
            if omission is not None:
                omitted.append(omission)
        items: list[dict[str, Any]] = []
        for span in spans:
            for chunk in _split_around_pictures(span["events"], segment_pictures, omitted):
                octets = [
                    event["octet"] for event in chunk
                    if event["octet"] is not None
                    and event.get("control_role") is None
                ]
                if not octets:
                    continue
                first = chunk[0]
                last = chunk[-1]
                item = {
                    "id": _stable_id("text", segment_id, span["frame_id"], first["id"], last["id"]),
                    "kind": "text",
                    "interval": {
                        "start": min(event["wire_interval"]["start"] for event in chunk),
                        "stop": max(event["wire_interval"]["stop"] for event in chunk),
                    },
                    "framing": span["framing"],
                    "frame_id": span["frame_id"],
                    "text": _decode_broadcast_octets(bytes(octets)),
                    "unmapped_event_count": sum(event["octet"] is None for event in chunk),
                    "_sort_sample": first["recognized_at_input_sample"],
                    "_event_ids": {event["id"] for event in chunk},
                }
                items.append(item)
        for entry in segment_pictures:
            picture = entry["source"]
            artifact = artifact_by_id.get(picture.get("raster_artifact"))
            rendered = _picture_artifact(artifact)
            if rendered is None:
                warnings.append({
                    "code": "text-product-picture-artifact-missing",
                    "message": f"picture {picture['id']} has no usable raster artifact",
                })
            header_ids = set(picture.get("header_event_ids", []))
            preceding = [
                item for item in items
                if item["kind"] == "text" and item["_sort_sample"] < entry["start"]
            ]
            matching_header = [
                item for item in preceding if item["_event_ids"] & header_ids
            ]
            associated = None
            if matching_header:
                associated = max(matching_header, key=lambda item: item["_sort_sample"])
            elif preceding:
                nearest = max(preceding, key=lambda item: item["_sort_sample"])
                if entry["start"] - nearest["_sort_sample"] <= 30 * sample_rate:
                    associated = nearest
            items.append({
                "id": picture["id"],
                "kind": "picture",
                "interval": {"start": entry["start"], "stop": entry["stop"]},
                "associated_text_item_id": associated["id"] if associated else None,
                "artifact": rendered,
                "header_text": picture.get("header_text"),
                "width": picture["width"],
                "height": picture["height"],
                "color": picture["color"],
                "complete": picture["complete"],
                "_sort_sample": entry["start"],
            })
        items.sort(key=lambda item: (item["_sort_sample"], item["kind"] == "picture"))
        for item in items:
            item.pop("_sort_sample")
            item.pop("_event_ids", None)
        segment["items"] = items

    document = {
        "schema": SCHEMA,
        "run_id": source["run_id"],
        "status": (
            "partial"
            if any(item["code"].startswith("text-product-") for item in warnings)
            else source["status"]
        ),
        "decoder": {
            "version": source["decoder"]["version"],
            "configuration": dict(source["decoder"]["configuration"]),
        },
        "input": {
            "metadata_sha256": source_input["metadata_sha256"],
            "data_sha256": source_input["data_sha256"],
            "sample_rate_hz": source_input["sample_rate_hz"],
            "requested_interval": requested,
        },
        "mode_segments": segments,
        "omitted_unframed": omitted,
        "warnings": warnings,
    }
    jsonschema.Draft202012Validator(load_json("schemas", SCHEMA_FILE)).validate(document)
    return document


def _containing_segment(
    segments: list[dict[str, Any]], sample: int, *, mode: str | None = None
) -> dict[str, Any] | None:
    return next(
        (
            segment for segment in segments
            if segment["interval"]["start"] <= sample < segment["interval"]["stop"]
            and (mode is None or segment["mode"] == mode)
        ),
        None,
    )


def _picture_interval(picture: Mapping[str, Any]) -> tuple[int, int]:
    start = int(picture["prologue_interval"]["start"])
    selected = next(
        (item["input_sample"] for item in picture.get("end_alternatives", []) if item.get("selected")),
        None,
    )
    stop = int(
        selected
        if selected is not None else
        picture.get("return_to_text_reacquisition_interval", {}).get("start", start)
    )
    return start, max(start, stop)


def _framed_spans(
    events: list[dict[str, Any]], segment_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    first_stx = next(
        (index for index, event in enumerate(events) if event.get("control_role") == "STX"),
        None,
    )
    if first_stx is None:
        return ([{"events": events, "framing": "uncertain", "frame_id": None}] if events else []), []
    prefix = events[:first_stx]
    spans: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    frame_id: str | None = None
    for event in events[first_stx:]:
        role = event.get("control_role")
        if role == "STX":
            if current:
                spans.append({
                    "events": current,
                    "framing": "incomplete" if frame_id else "uncertain",
                    "frame_id": frame_id,
                })
            current = []
            frame_id = _stable_id("frame", segment_id, event["id"])
        elif role == "EOT":
            if current:
                spans.append({
                    "events": current,
                    "framing": "complete_stx_eot" if frame_id else "uncertain",
                    "frame_id": frame_id,
                })
            current = []
            frame_id = None
        else:
            current.append(event)
    if current:
        spans.append({
            "events": current,
            "framing": "incomplete" if frame_id else "uncertain",
            "frame_id": frame_id,
        })
    return spans, prefix


def _split_around_pictures(
    events: list[dict[str, Any]],
    pictures: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    bucket: int | None = None
    inside: list[dict[str, Any]] = []
    for event in events:
        sample = event["recognized_at_input_sample"]
        if any(picture["start"] <= sample < picture["stop"] for picture in pictures):
            if current:
                chunks.append(current)
                current = []
            inside.append(event)
            bucket = None
            continue
        if inside:
            omission = _omission(inside, "inside_picture")
            if omission is not None:
                omitted.append(omission)
            inside = []
        position = sum(sample >= picture["stop"] for picture in pictures)
        if current and position != bucket:
            chunks.append(current)
            current = []
        current.append(event)
        bucket = position
    if inside:
        omission = _omission(inside, "inside_picture")
        if omission is not None:
            omitted.append(omission)
    if current:
        chunks.append(current)
    return chunks


def _omission(events: list[dict[str, Any]], reason: str) -> dict[str, Any] | None:
    count = sum(
        event["octet"] is not None and event.get("control_role") is None
        for event in events
    )
    if not count:
        return None
    return {
        "interval": {
            "start": min(event["wire_interval"]["start"] for event in events),
            "stop": max(event["wire_interval"]["stop"] for event in events),
        },
        "reason": reason,
        "character_count": count,
    }


def _picture_artifact(artifact: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if artifact is None:
        return None
    if artifact["kind"] == "png_uint8_raster":
        return {
            "kind": "png_uint8_raster",
            "path": artifact["path"],
            "sha256": artifact["sha256"],
        }
    if artifact["kind"] == "inline_uint8_raster":
        return {
            "kind": "inline_uint8_raster",
            "shape": artifact["shape"],
            "values": artifact["values"],
        }
    return None


def _decode_broadcast_octets(octets: bytes) -> str:
    """Read valid UTF-8 while retaining undecodable octets as Latin-1 characters."""
    decoded = octets.decode("utf-8", errors="surrogateescape")
    return "".join(
        chr(ord(char) - 0xDC00) if 0xDC80 <= ord(char) <= 0xDCFF else char
        for char in decoded
    )


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("://".join(map(str, parts)).encode()).hexdigest()[:24]
