from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import resource
import tempfile
import time
from typing import Any

import jsonschema
import numpy as np

from .acquisition import acquire_modes
from .sigmf import SigmfRecording, inspect_samples
from .picture_decode import (
    PictureDecode,
    PictureRangeConfig,
    PictureSampleSource,
    decode_pictures,
    parse_picture_headers,
)
from .text_decode import MFSKTextDecode, decode_mfsk_text
from .stateful_pipeline import decode_p11d_text_region
from .resources import load_json


SCHEMA_NAME = "mfsk-decode-manifest-v1.json"
DECODER_VERSION = "0.2.0-reference"
BOUNDED_PIPELINE_THRESHOLD_SECONDS = 180.0
BOUNDED_TEXT_CORE_SECONDS = 180.0
BOUNDED_TEXT_CONTEXT_SECONDS = 8.0


@dataclass(frozen=True)
class DecodeConfig:
    block_samples: int = 262_144
    orientation: str = "unknown"
    trace_level: str = "none"
    mode: str = "MFSK32"
    center_hz: float | None = None
    picture_component_estimator: str = "bounded_correlation"
    picture_component_window: str = "full_hann"
    picture_filter_profile: str = "response_matched"
    picture_boundary_estimator: str = "unified_grid"
    persistent_tone_policy: str = "measure"
    pipeline_organization: str = "supported_hybrid"
    picture_range_workers: int = 1
    picture_range_components: int = 16_384
    picture_max_in_flight_ranges: int = 1

    def __post_init__(self) -> None:
        if self.block_samples <= 0:
            raise ValueError("block_samples must be positive")
        if self.picture_component_estimator not in {
            "fft_peak", "phase_difference", "bounded_correlation"
        }:
            raise ValueError("unsupported picture component estimator")
        if self.picture_component_window not in {"center_crop", "full", "full_hann"}:
            raise ValueError("unsupported picture component window")
        if self.picture_filter_profile not in {"current_wide", "response_matched"}:
            raise ValueError("unsupported picture filter profile")
        if self.picture_boundary_estimator != "unified_grid":
            raise ValueError("unsupported picture boundary estimator")
        if self.persistent_tone_policy not in {"measure", "suppress"}:
            raise ValueError("unsupported persistent tone policy")
        if self.pipeline_organization not in {
            "supported_hybrid", "p11d", "independent_window_oracle"
        }:
            raise ValueError("unsupported pipeline organization")
        PictureRangeConfig(
            workers=self.picture_range_workers,
            components_per_range=self.picture_range_components,
            max_in_flight_ranges=self.picture_max_in_flight_ranges,
        )
        if self.orientation not in {"normal", "reverse", "unknown"}:
            raise ValueError("orientation must be normal, reverse, or unknown")
        if self.trace_level not in {"none", "summary", "events", "full"}:
            raise ValueError("invalid trace level")
        if self.mode not in {"auto", "MFSK32", "MFSK64"}:
            raise ValueError("mode must be auto, MFSK32, or MFSK64")
        if self.center_hz is not None and (
            not np.isfinite(self.center_hz) or self.center_hz <= 0
        ):
            raise ValueError("center_hz must be finite and positive")

    def to_dict(self) -> dict[str, Any]:
        document = {
            "block_samples": self.block_samples,
            "orientation": self.orientation,
            "trace_level": self.trace_level,
            "mode": self.mode,
            "center_hz": self.center_hz,
            "picture_component_estimator": self.picture_component_estimator,
            "picture_component_window": self.picture_component_window,
            "picture_filter_profile": self.picture_filter_profile,
            "picture_boundary_estimator": self.picture_boundary_estimator,
            "persistent_tone_policy": self.persistent_tone_policy,
            "pipeline_organization": self.pipeline_organization,
            "picture_range_workers": self.picture_range_workers,
            "picture_range_components": self.picture_range_components,
            "picture_max_in_flight_ranges": self.picture_max_in_flight_ranges,
            "persistent_intermediates": False,
        }
        _validate_schema(document, "mfsk-decode-config-v1.json")
        return document


def run_reference_pipeline(
    *,
    meta_path: Path,
    data_path: Path,
    start_sample: int | None,
    stop_sample: int | None,
    config: DecodeConfig,
    artifact_dir: Path | None = None,
    artifact_path_prefix: str | None = None,
) -> dict[str, Any]:
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    stage_wall_seconds: dict[str, float] = {}

    def finish_stage(name: str, started: float) -> None:
        stage_wall_seconds[name] = time.perf_counter() - started

    started_at = datetime.now(timezone.utc)
    stage_start = time.perf_counter()
    recording = SigmfRecording.open(
        meta_path,
        data_path,
        start_sample=start_sample,
        stop_sample=stop_sample,
    )
    finish_stage("ingest_open_validate", stage_start)
    stage_start = time.perf_counter()
    hashes = recording.hashes()
    finish_stage("input_hashing", stage_start)
    stage_start = time.perf_counter()
    sample_summary = inspect_samples(recording, config.block_samples)
    finish_stage("sample_inspection", stage_start)
    stage_start = time.perf_counter()
    acquisition = acquire_modes(recording)
    finish_stage("acquisition_segmentation", stage_start)
    stage_start = time.perf_counter()
    bounded_organization = (
        config.mode != "auto"
        and recording.requested_stop - recording.requested_start
        > recording.sample_rate * BOUNDED_PIPELINE_THRESHOLD_SECONDS
    )
    samples = (
        np.empty(0, dtype=np.complex64)
        if config.mode == "auto" or bounded_organization
        else recording.read_complex64(
            recording.requested_start, recording.requested_stop
        )
    )
    finish_stage("sample_materialization", stage_start)
    stage_start = time.perf_counter()
    if config.mode == "auto":
        text_decode = None
        decode_warning = {
            "code": "segmented-payload-decode-deferred",
            "message": (
                "automatic acquisition produced mode segments; segmented payload "
                "decoding is deferred to remediation R2/R3"
            ),
        }
    else:
        try:
            text_decode = (
                _decode_bounded_text(
                    recording, acquisition, config, run_wall_start=wall_start
                )
                if bounded_organization
                else decode_mfsk_text(
                    samples,
                    input_start=recording.requested_start,
                    sample_rate=recording.sample_rate,
                    orientation_hint=config.orientation,
                    trace_level=config.trace_level,
                    mode=config.mode,
                    center_hint_hz=config.center_hz,
                    persistent_tone_policy=config.persistent_tone_policy,
                    fit_transition_clock=True,
                )
            )
            decode_warning = None
        except ValueError as error:
            text_decode = None
            decode_warning = {
                "code": "mfsk-text-acquisition-failed",
                "message": str(error),
            }
    finish_stage("text_acquisition_evidence_fec_framing", stage_start)
    stage_start = time.perf_counter()
    if text_decode is not None:
        try:
            if bounded_organization:
                picture_decode = _decode_bounded_pictures(
                    recording,
                    text_decode,
                    mode=config.mode,
                    artifact_dir=artifact_dir,
                    artifact_path_prefix=artifact_path_prefix,
                    run_wall_start=wall_start,
                    component_estimator=config.picture_component_estimator,
                    component_window=config.picture_component_window,
                    filter_profile=config.picture_filter_profile,
                    boundary_estimator=config.picture_boundary_estimator,
                    range_config=(
                        PictureRangeConfig(
                            workers=config.picture_range_workers,
                            components_per_range=config.picture_range_components,
                            max_in_flight_ranges=config.picture_max_in_flight_ranges,
                        )
                        if _p11d_picture_ranges_enabled(config) else None
                    ),
                )
            else:
                picture_decode = decode_pictures(
                    samples,
                    input_start=recording.requested_start,
                    sample_rate=recording.sample_rate,
                    mode=config.mode,
                    orientation=text_decode.mode_segment["orientation"],
                    center_hz=text_decode.mode_segment["center_hz"],
                    text_events=text_decode.text_events,
                    symbol_clock=text_decode.transition_clock,
                    symbol_clock_covariance=(
                        text_decode.transition_clock_covariance
                    ),
                    decoded_bits=text_decode.decoded_bits,
                    artifact_dir=artifact_dir,
                    artifact_path_prefix=artifact_path_prefix,
                    component_estimator=config.picture_component_estimator,
                    component_window=config.picture_component_window,
                    filter_profile=config.picture_filter_profile,
                    boundary_estimator=config.picture_boundary_estimator,
                )
                _reacquire_picture_text_epochs(
                    samples,
                    input_start=recording.requested_start,
                    sample_rate=recording.sample_rate,
                    mode=config.mode,
                    orientation=text_decode.mode_segment["orientation"],
                    center_hz=text_decode.mode_segment["center_hz"],
                    picture_decode=picture_decode,
                    text_decode=text_decode,
                )
            _suppress_accepted_picture_text(text_decode, picture_decode)
            picture_warning = None
        except ValueError as error:
            picture_decode = None
            picture_warning = {
                "code": "mfsk-picture-decode-failed",
                "message": str(error),
            }
    else:
        picture_decode = None
        picture_warning = None
    finish_stage("picture_transition_raster_artifacts", stage_start)
    stage_start = time.perf_counter()
    config_document = config.to_dict()
    stable_run_id = hashlib.sha256(
        json.dumps(
            {
                "hashes": hashes,
                "interval": [recording.requested_start, recording.requested_stop],
                "config": config_document,
                "decoder_version": DECODER_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]

    warnings = list(recording.warnings)
    framing = (
        text_decode.text_summary["framing"]
        if text_decode is not None
        else {"stx_found": False, "eot_found": False}
    )
    complete = framing["stx_found"] and framing["eot_found"]
    if decode_warning is not None:
        warnings.append(decode_warning)
    elif not complete:
        warnings.append(
            {
                "code": "incomplete-text-framing",
                "message": f"{config.mode} text did not contain both STX and a later EOT",
            }
        )
    if picture_warning is not None:
        warnings.append(picture_warning)
    if text_decode is not None:
        for event in text_decode.text_events:
            event.get("provenance", {}).pop("picture_flush_tones", None)
    manifest: dict[str, Any] = {
        "schema": "grampy-decode-manifest.v1",
        "run_id": stable_run_id,
        "status": "complete" if complete else "partial",
        "input": {
            "metadata_path": str(meta_path),
            "data_path": str(data_path),
            **hashes,
            "datatype": recording.datatype,
            "sample_rate_hz": recording.sample_rate,
            "sample_count": recording.sample_count,
            "interval": {"start": 0, "stop": recording.sample_count},
            "requested_interval": {
                "start": recording.requested_start,
                "stop": recording.requested_stop,
            },
            "sample_map": recording.sample_map.to_dict(),
            "ancestry": list(recording.ancestry),
            "sample_summary": sample_summary,
        },
        "decoder": {
            "version": DECODER_VERSION,
            "configuration": config_document,
            "dependencies": _dependency_versions(),
            "platform": {
                "python": platform.python_version(),
                "machine": platform.machine(),
                "system": platform.system(),
            },
        },
        "signal_regions": [item.to_dict() for item in acquisition.regions],
        "mode_hypotheses": list(acquisition.mode_hypotheses),
        "frequency_tracks": [item.to_dict() for item in acquisition.frequency_tracks],
        "mode_segments": (
            list(acquisition.mode_segments)
            if config.mode == "auto"
            else [
                item for item in acquisition.mode_segments
                if item["mode"] == config.mode
            ]
            if bounded_organization and any(
                item["mode"] == config.mode
                for item in acquisition.mode_segments
            )
            else [text_decode.mode_segment] if text_decode else []
        ),
        "text_epochs": text_decode.text_epochs if text_decode else [],
        "text_events": text_decode.text_events if text_decode else [],
        "text_summary": (
            text_decode.text_summary
            if text_decode
            else {"octets": [], "text": "", "framing": framing}
        ),
        "pictures": picture_decode.pictures if picture_decode else [],
        "transitions": picture_decode.transitions if picture_decode else [],
        "warnings": warnings,
        "recoverable_errors": [],
        "terminal_failure": None,
        "artifacts": picture_decode.artifacts if picture_decode else [],
        "diagnostics": {
            "trace_level": config.trace_level,
            "persistent_intermediate_files": 0,
            "persistent_artifact_files": (
                picture_decode.diagnostics["persistent_artifact_files"]
                if picture_decode else 0
            ),
            "bytes_read": (
                2 * meta_path.stat().st_size
                + data_path.stat().st_size
                + 2 * (recording.requested_stop - recording.requested_start)
                * recording.bytes_per_sample
                + (
                    picture_decode.diagnostics.get("requested_read_bytes", 0)
                    if picture_decode else 0
                )
            ),
            "bytes_written": (
                picture_decode.diagnostics["artifact_bytes"]
                if picture_decode else 0
            ),
            "peak_temporary_storage_bytes": 0,
            "repeated_input_sample_reads": (
                2 * (recording.requested_stop - recording.requested_start)
                + (
                    picture_decode.diagnostics.get("requested_read_samples", 0)
                    if picture_decode else 0
                )
            ),
            "duplicated_expensive_transforms": (
                max(
                    0,
                    len(
                        text_decode.diagnostics["tone_evidence"].get(
                            "acquisition_candidates", []
                        )
                    )
                    - 1,
                )
                if text_decode else 0
            ),
            "working_set_organization": (
                _bounded_working_set_organization(config)
                if bounded_organization else "complete_requested_region"
            ),
            "maximum_materialized_iq_samples": (
                text_decode.diagnostics.get("bounded_organization", {}).get(
                    "maximum_materialized_iq_samples", len(samples)
                )
                if text_decode else len(samples)
            ),
            "incremental_time_to_result_seconds": {
                "first_stable_text": (
                    text_decode.diagnostics.get("bounded_organization", {}).get(
                        "first_stable_text_wall_seconds"
                    )
                    if text_decode else None
                ),
                "first_picture_descriptor": (
                    picture_decode.diagnostics.get(
                        "first_picture_descriptor_wall_seconds"
                    )
                    if picture_decode else None
                ),
                "first_complete_picture": (
                    picture_decode.diagnostics.get(
                        "first_complete_picture_wall_seconds"
                    )
                    if picture_decode else None
                ),
                "availability": (
                    "measured_during_bounded_batch_execution"
                    if bounded_organization else "unavailable_complete_region"
                ),
            },
            "counts": {
                "lock_loss": (
                    text_decode.diagnostics["tone_evidence"]
                    .get("frequency_track", {})
                    .get("lock_loss_count", 0)
                    if text_decode else 0
                ),
                "reacquisition": (
                    text_decode.diagnostics["tone_evidence"]
                    .get("frequency_track", {})
                    .get("reacquisition_count", 0)
                    if text_decode else 0
                ),
                "erasures": (
                    text_decode.diagnostics["bit_evidence"].get(
                        "erasure_count", 0
                    )
                    if text_decode else 0
                ),
                "invalid_varicode": (
                    text_decode.diagnostics["varicode_evidence"]["invalid_count"]
                    if text_decode else 0
                ),
                "header_rejection": (
                    picture_decode.diagnostics["header_rejections"]
                    if picture_decode else 0
                ),
                "clipped_pixels": (
                    picture_decode.diagnostics["clipped_components"]
                    if picture_decode else 0
                ),
                "damaged_components": (
                    picture_decode.diagnostics["damaged_components"]
                    if picture_decode else 0
                ),
            },
            "text_pipeline": text_decode.diagnostics if text_decode else {},
            "picture_pipeline": (
                picture_decode.diagnostics if picture_decode else {}
            ),
            "stage_wall_seconds": stage_wall_seconds,
        },
        "timing": {
            "started_at": started_at.isoformat(),
            "wall_seconds": time.perf_counter() - wall_start,
            "cpu_seconds": time.process_time() - cpu_start,
            "peak_rss_bytes": _peak_rss_bytes(),
        },
    }
    validate_manifest(manifest)
    finish_stage("manifest_assembly_validation", stage_start)
    manifest["diagnostics"]["stage_wall_seconds"] = stage_wall_seconds
    manifest["timing"]["wall_seconds"] = time.perf_counter() - wall_start
    manifest["timing"]["cpu_seconds"] = time.process_time() - cpu_start
    manifest["timing"]["peak_rss_bytes"] = _peak_rss_bytes()
    return manifest


def _decode_bounded_text(
    recording: SigmfRecording,
    acquisition: Any,
    config: DecodeConfig,
    *,
    run_wall_start: float,
) -> MFSKTextDecode:
    """Decode long inputs as independently ranked overlapping text epochs."""
    core_samples = int(round(BOUNDED_TEXT_CORE_SECONDS * recording.sample_rate))
    context_samples = int(round(BOUNDED_TEXT_CONTEXT_SECONDS * recording.sample_rate))
    matching_segments = [
        segment for segment in acquisition.mode_segments
        if segment["mode"] == config.mode
    ]
    source_segments = (
        matching_segments
        if matching_segments and config.center_hz is None
        else [{
            "interval": {
                "start": recording.requested_start,
                "stop": recording.requested_stop,
            },
            "center_hz": config.center_hz,
            "orientation": config.orientation,
        }]
    )
    compact_eligible = (
        _p11d_compact_text_enabled(config)
        and config.persistent_tone_policy == "measure"
        and all(
            segment.get("center_hz") is not None
            and segment.get("orientation") in {"normal", "reverse"}
            for segment in source_segments
        )
    )
    if compact_eligible:
        return _decode_p11d_bounded_text(
            recording,
            config,
            source_segments,
            run_wall_start=run_wall_start,
        )
    events: list[dict[str, Any]] = []
    epochs: list[dict[str, Any]] = []
    window_summaries: list[dict[str, Any]] = []
    diagnostics_template: dict[str, Any] | None = None
    maximum_materialized = 0
    failures = 0
    first_stable_text_wall_seconds: float | None = None
    for segment_index, segment in enumerate(source_segments, 1):
        segment_start = max(
            recording.requested_start, int(segment["interval"]["start"])
        )
        segment_stop = min(
            recording.requested_stop, int(segment["interval"]["stop"])
        )
        for core_start in range(segment_start, segment_stop, core_samples):
            core_stop = min(segment_stop, core_start + core_samples)
            read_start = max(recording.requested_start, core_start - context_samples)
            read_stop = min(recording.requested_stop, core_stop + context_samples)
            bounded_samples = recording.read_complex64(read_start, read_stop)
            maximum_materialized = max(maximum_materialized, len(bounded_samples))
            try:
                decoded = decode_mfsk_text(
                    bounded_samples,
                    input_start=read_start,
                    sample_rate=recording.sample_rate,
                    orientation_hint=(
                        config.orientation
                        if config.orientation != "unknown"
                        else segment.get("orientation", "unknown")
                    ),
                    trace_level=config.trace_level,
                    mode=config.mode,
                    center_hint_hz=(
                        config.center_hz
                        if config.center_hz is not None
                        else segment.get("center_hz")
                    ),
                    persistent_tone_policy=config.persistent_tone_policy,
                    fit_transition_clock=True,
                )
            except ValueError as error:
                failures += 1
                window_summaries.append({
                    "core_interval": {"start": core_start, "stop": core_stop},
                    "read_interval": {"start": read_start, "stop": read_stop},
                    "status": "not_acquired",
                    "reason": str(error),
                })
                del bounded_samples
                continue
            if diagnostics_template is None:
                diagnostics_template = copy.deepcopy(decoded.diagnostics)
            kept = [
                copy.deepcopy(event) for event in decoded.text_events
                if core_start <= event["recognized_at_input_sample"] < core_stop
            ]
            for event in kept:
                event["id"] = f"text-{len(events) + 1:06d}"
                event["mode_segment"] = segment.get(
                    "id", "mode-bounded-summary"
                )
                event["provenance"]["bounded_window"] = {
                    "read_interval": {"start": read_start, "stop": read_stop},
                    "core_interval": {"start": core_start, "stop": core_stop},
                    "center_hz": decoded.mode_segment["center_hz"],
                    "orientation": decoded.mode_segment["orientation"],
                }
                events.append(event)
                if (
                    first_stable_text_wall_seconds is None
                    and event["octet"] is not None
                    and not event["damage_flags"]
                    and float(event["confidence"]["value"]) >= 0.25
                ):
                    first_stable_text_wall_seconds = (
                        time.perf_counter() - run_wall_start
                    )
            for epoch in decoded.text_epochs:
                overlap_start = max(core_start, epoch["interval"]["start"])
                overlap_stop = min(core_stop, epoch["interval"]["stop"])
                if overlap_stop <= overlap_start:
                    continue
                bounded_epoch = copy.deepcopy(epoch)
                bounded_epoch["id"] = f"text-epoch-{len(epochs) + 1:06d}"
                bounded_epoch["interval"] = {
                    "start": overlap_start, "stop": overlap_stop
                }
                bounded_epoch["start_evidence"] = "bounded_overlapping_window"
                bounded_epoch["bounded_window"] = {
                    "read_interval": {"start": read_start, "stop": read_stop},
                    "core_interval": {"start": core_start, "stop": core_stop},
                }
                epochs.append(bounded_epoch)
            window_summaries.append({
                "core_interval": {"start": core_start, "stop": core_stop},
                "read_interval": {"start": read_start, "stop": read_stop},
                "status": "decoded",
                "event_count": len(kept),
                "center_hz": decoded.mode_segment["center_hz"],
                "orientation": decoded.mode_segment["orientation"],
                "peak_materialized_iq_samples": len(bounded_samples),
            })
            del decoded, bounded_samples
    if diagnostics_template is None:
        raise ValueError("no bounded text window acquired")
    events.sort(key=lambda item: item["recognized_at_input_sample"])
    events, header_refinements = _refine_damaged_picture_headers(
        recording, config, events
    )
    for index, event in enumerate(events, 1):
        event["id"] = f"text-{index:06d}"
        containing = next(
            (
                epoch for epoch in epochs
                if epoch["interval"]["start"] <= event["wire_interval"]["start"]
                and event["wire_interval"]["stop"] <= epoch["interval"]["stop"]
            ),
            None,
        )
        event["provenance"]["text_epoch"] = (
            containing["id"] if containing is not None else None
        )
    octets = [
        event["octet"] for event in events
        if event["octet"] is not None and event["control_role"] is None
    ]
    centers = [
        float(item["center_hz"]) for item in window_summaries
        if item["status"] == "decoded"
    ]
    orientations = [
        item["orientation"] for item in window_summaries
        if item["status"] == "decoded"
    ]
    diagnostics_template["bounded_organization"] = {
        "kind": "overlapping_complete-region_text_windows",
        "core_samples": core_samples,
        "context_samples_each_side": context_samples,
        "maximum_materialized_iq_samples": maximum_materialized,
        "window_count": len(window_summaries),
        "failed_window_count": failures,
        "first_stable_text_wall_seconds": first_stable_text_wall_seconds,
        "windows": window_summaries,
        "trace_budget": {
            "policy": "per-window evidence summarized; event/full rows not aggregated",
            "requested_level": config.trace_level,
        },
        "picture_header_refinements": header_refinements,
    }
    diagnostics_template["varicode_evidence"]["event_count"] = len(events)
    diagnostics_template["varicode_evidence"]["invalid_count"] = sum(
        event["octet"] is None for event in events
    )
    diagnostics_template["tone_evidence"].pop("symbols", None)
    diagnostics_template["bit_evidence"].pop("deinterleaved_groups", None)
    diagnostics_template["fec_evidence"].pop("decoded_bits", None)
    return MFSKTextDecode(
        mode_segment={
            "id": "mode-bounded-summary",
            "mode": config.mode,
            "orientation": (
                max(set(orientations), key=orientations.count)
                if orientations else "normal"
            ),
            "interval": {
                "start": min(
                    (item["core_interval"]["start"] for item in window_summaries
                     if item["status"] == "decoded"),
                    default=recording.requested_start,
                ),
                "stop": max(
                    (item["core_interval"]["stop"] for item in window_summaries
                     if item["status"] == "decoded"),
                    default=recording.requested_stop,
                ),
            },
            "source": "bounded_segment_and_text_evidence",
            "confidence": {"kind": "window_consensus", "value": 1.0},
            "acquisition_state": "locked",
            "symbol_phase_uncertainty_input_samples": 48,
            "center_hz": float(np.median(centers)),
        },
        text_events=events,
        text_summary={
            "octets": octets,
            "text": bytes(octets).decode("latin-1"),
            "framing": {
                "stx_found": any(item["control_role"] == "STX" for item in events),
                "eot_found": any(item["control_role"] == "EOT" for item in events),
            },
        },
        diagnostics=diagnostics_template,
        text_epochs=epochs,
    )


def _p11d_compact_text_enabled(config: DecodeConfig) -> bool:
    """Select only text organizations that passed the fixed-mode quality gate."""
    return config.pipeline_organization == "p11d" or (
        config.pipeline_organization == "supported_hybrid"
        and config.mode == "MFSK64"
    )


def _p11d_picture_ranges_enabled(config: DecodeConfig) -> bool:
    return config.pipeline_organization == "p11d" or (
        config.pipeline_organization == "supported_hybrid"
        and config.mode == "MFSK64"
    )


def _bounded_working_set_organization(config: DecodeConfig) -> str:
    if _p11d_compact_text_enabled(config):
        return "p11d_bounded_text_and_picture_ranges"
    return "bounded_overlapping_text_windows_and_complete_picture_windows"


def _decode_p11d_bounded_text(
    recording: SigmfRecording,
    config: DecodeConfig,
    source_segments: list[dict[str, Any]],
    *,
    run_wall_start: float,
) -> MFSKTextDecode:
    """Decode fixed, acquisition-resolved segments through compact P11D state."""
    events: list[dict[str, Any]] = []
    epochs: list[dict[str, Any]] = []
    segment_summaries: list[dict[str, Any]] = []
    decoded_segments: list[MFSKTextDecode] = []
    first_stable_text_wall_seconds: float | None = None
    maximum_materialized = 0
    for segment_index, segment in enumerate(source_segments, 1):
        segment_start = max(
            recording.requested_start, int(segment["interval"]["start"])
        )
        segment_stop = min(
            recording.requested_stop, int(segment["interval"]["stop"])
        )
        if segment_stop <= segment_start:
            continue
        segment_id = str(segment.get("id", f"mode-p11d-{segment_index:04d}"))
        decoded = decode_p11d_text_region(
            recording.read_complex64,
            input_start=segment_start,
            input_stop=segment_stop,
            sample_rate=recording.sample_rate,
            mode=config.mode,
            center_hz=float(segment["center_hz"]),
            orientation=str(segment["orientation"]),
            block_samples=config.block_samples,
            initial_state=0,
            mode_segment_id=segment_id,
        )
        decoded_segments.append(decoded)
        bounded = decoded.diagnostics["bounded_organization"]
        maximum_materialized = max(
            maximum_materialized,
            int(bounded["maximum_materialized_iq_samples"]),
        )
        epoch_ids: dict[str | None, str] = {}
        for epoch in decoded.text_epochs:
            source_id = epoch.get("id")
            target_id = f"text-epoch-{len(epochs) + 1:06d}"
            epoch_ids[source_id] = target_id
            item = copy.deepcopy(epoch)
            item["id"] = target_id
            item["mode_segment"] = segment_id
            epochs.append(item)
        for event in decoded.text_events:
            item = copy.deepcopy(event)
            item["id"] = f"text-{len(events) + 1:06d}"
            item["mode_segment"] = segment_id
            provenance = item["provenance"]
            provenance["text_epoch"] = epoch_ids.get(
                provenance.get("text_epoch"), provenance.get("text_epoch")
            )
            provenance["bounded_window"] = {
                "read_interval": {"start": segment_start, "stop": segment_stop},
                "core_interval": {"start": segment_start, "stop": segment_stop},
                "center_hz": decoded.mode_segment["center_hz"],
                "orientation": decoded.mode_segment["orientation"],
                "organization": "p11d_compact_segment",
            }
            events.append(item)
            if (
                first_stable_text_wall_seconds is None
                and item["octet"] is not None
                and not item["damage_flags"]
                and float(item["confidence"]["value"]) >= 0.25
            ):
                first_stable_text_wall_seconds = time.perf_counter() - run_wall_start
        segment_summaries.append({
            "mode_segment": segment_id,
            "interval": {"start": segment_start, "stop": segment_stop},
            "center_hz": decoded.mode_segment["center_hz"],
            "orientation": decoded.mode_segment["orientation"],
            "event_count": len(decoded.text_events),
            "track_planning": bounded["track_planning"],
            "track_hypotheses": bounded["track_hypotheses"],
            "text_pass": bounded["text_pass"],
        })
    if not decoded_segments:
        raise ValueError("no compact P11D text segment was available")

    events.sort(key=lambda item: item["recognized_at_input_sample"])
    events, header_refinements = _refine_damaged_picture_headers(
        recording, config, events
    )
    for index, event in enumerate(events, 1):
        event["id"] = f"text-{index:06d}"
    octets = [
        event["octet"] for event in events
        if event["octet"] is not None and event["control_role"] is None
    ]
    diagnostics = copy.deepcopy(decoded_segments[0].diagnostics)
    diagnostics["tone_evidence"]["symbol_count"] = sum(
        item.diagnostics["tone_evidence"]["symbol_count"]
        for item in decoded_segments
    )
    diagnostics["bit_evidence"]["erasure_count"] = sum(
        item.diagnostics["bit_evidence"]["erasure_count"]
        for item in decoded_segments
    )
    diagnostics["fec_evidence"]["coded_llr_count"] = sum(
        item.diagnostics["fec_evidence"]["coded_llr_count"]
        for item in decoded_segments
    )
    diagnostics["fec_evidence"]["decoded_bit_count"] = sum(
        item.diagnostics["fec_evidence"]["decoded_bit_count"]
        for item in decoded_segments
    )
    diagnostics["varicode_evidence"] = {
        "event_count": len(events),
        "invalid_count": sum(event["octet"] is None for event in events),
    }
    diagnostics["bounded_organization"] = {
        "kind": "p11d_compact_tracks_and_stateful_text_pass",
        "maximum_materialized_iq_samples": maximum_materialized,
        "segment_count": len(segment_summaries),
        "first_stable_text_wall_seconds": first_stable_text_wall_seconds,
        "segments": segment_summaries,
        "picture_header_refinements": header_refinements,
        "oracle_fallback": {
            "configuration": "independent_window_oracle",
            "selected": False,
        },
        "trace_budget": {
            "policy": "compact state and segment summaries; symbol rows not retained",
            "requested_level": config.trace_level,
        },
    }
    centers = [item.mode_segment["center_hz"] for item in decoded_segments]
    orientations = [item.mode_segment["orientation"] for item in decoded_segments]
    return MFSKTextDecode(
        mode_segment={
            "id": "mode-p11d-summary",
            "mode": config.mode,
            "orientation": max(set(orientations), key=orientations.count),
            "interval": {
                "start": min(item["interval"]["start"] for item in segment_summaries),
                "stop": max(item["interval"]["stop"] for item in segment_summaries),
            },
            "source": "rsid_and_p11d_compact_tracks",
            "confidence": {"kind": "accepted_acquisition_segments", "value": 1.0},
            "acquisition_state": "locked",
            "symbol_phase_uncertainty_input_samples": 48,
            "center_hz": float(np.median(centers)),
        },
        text_events=events,
        text_summary={
            "octets": octets,
            "text": bytes(octets).decode("latin-1"),
            "framing": {
                "stx_found": any(event["control_role"] == "STX" for event in events),
                "eot_found": any(event["control_role"] == "EOT" for event in events),
            },
        },
        diagnostics=diagnostics,
        text_epochs=epochs,
        decoded_bits=(),
        transition_clock=decoded_segments[0].transition_clock,
        transition_clock_covariance=None,
    )


def _refine_damaged_picture_headers(
    recording: SigmfRecording,
    config: DecodeConfig,
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Re-evaluate only damaged ``Pic`` landmarks in centered bounded context."""
    accepted, _ = parse_picture_headers(events)
    accepted_intervals = [
        item["header_wire_interval"] for item in accepted
    ]
    accepted_completions = [
        item["header_completed_at_input_sample"] for item in accepted
    ]
    byte_events = [event for event in events if event["octet"] is not None]
    stream = bytes(event["octet"] for event in byte_events)
    candidate_indices = {
        index for index in range(max(0, len(stream) - 2))
        if stream[index : index + 3] == b"Pic"
    }
    candidate_indices.update(
        match.start()
        for match in re.finditer(
            rb"[0-9]{2,4}x[0-9]{2,4}C?(?:p[248])?;", stream
        )
    )
    candidate_indices.update(
        index
        for index, event in enumerate(byte_events)
        if event.get("control_role") == "EOT"
        and sum(
            bool(other.get("damage_flags"))
            for other in events
            if event["recognized_at_input_sample"]
            <= other["recognized_at_input_sample"]
            <= event["recognized_at_input_sample"]
            + int(round(15.0 * recording.sample_rate))
        )
        >= 3
    )
    refinements: list[dict[str, Any]] = []
    refined_headers: list[dict[str, Any]] = []
    refined_intervals: list[dict[str, int]] = []
    refined_recognition_intervals: list[tuple[int, int]] = []
    unresolved_core_counts: dict[int, int] = {}
    # Long windows let the following raster dominate MFSK acquisition.  A
    # header is locally recoverable in bounded text context immediately after
    # its ``Pic`` fragment or the preceding EOT landmark.
    context = int(round(15.0 * recording.sample_rate))

    def compatibility_core_start(
        candidate_event: dict[str, Any], candidate_sample: int
    ) -> int:
        """Align compatibility windows to the candidate's mode segment."""
        bounded_window = candidate_event.get("provenance", {}).get(
            "bounded_window", {}
        )
        core_interval = bounded_window.get("core_interval", {})
        alignment_origin = int(
            core_interval.get("start", recording.requested_start)
        )
        core = int(round(180.0 * recording.sample_rate))
        return alignment_origin + (
            (candidate_sample - alignment_origin) // core
        ) * core

    for candidate_index in sorted(candidate_indices):
        candidate_event = byte_events[candidate_index]
        candidate_sample = candidate_event["recognized_at_input_sample"]
        if any(
            interval["start"] <= candidate_sample <= interval["stop"]
            for interval in accepted_intervals
        ) or any(
            0
            <= completion - candidate_sample
            <= int(round(20.0 * recording.sample_rate))
            for completion in accepted_completions
        ):
            continue
        window = candidate_event["provenance"].get("bounded_window", {})
        symbol_rate = 62.5 if config.mode == "MFSK64" else 31.25
        half_symbol = int(round(recording.sample_rate / (2.0 * symbol_rate)))
        decoded: MFSKTextDecode | None = None
        nearby: list[dict[str, Any]] = []
        alignment_attempts: list[dict[str, Any]] = []
        last_error: ValueError | None = None
        read_start = read_stop = candidate_sample
        selected_shift = 0
        for alignment_shift in (0, -half_symbol, half_symbol):
            shifted_sample = candidate_sample + alignment_shift
            attempt_start = max(
                recording.requested_start, shifted_sample - context
            )
            attempt_stop = min(
                recording.requested_stop, shifted_sample + context
            )
            if attempt_stop - attempt_start < recording.sample_rate:
                continue
            attempt = {
                "alignment_shift_input_samples": alignment_shift,
                "read_interval": {
                    "start": attempt_start, "stop": attempt_stop,
                },
            }
            try:
                candidate_decode = decode_mfsk_text(
                    recording.read_complex64(attempt_start, attempt_stop),
                    input_start=attempt_start,
                    sample_rate=recording.sample_rate,
                    orientation_hint=window.get(
                        "orientation",
                        config.orientation
                        if config.orientation != "unknown" else "unknown",
                    ),
                    trace_level="none",
                    mode=config.mode,
                    center_hint_hz=window.get("center_hz", config.center_hz),
                    persistent_tone_policy=config.persistent_tone_policy,
                    fit_transition_clock=True,
                )
            except ValueError as error:
                last_error = error
                attempt["status"] = "not_acquired"
                alignment_attempts.append(attempt)
                continue
            descriptors, _ = parse_picture_headers(candidate_decode.text_events)
            attempt_nearby = [
                item for item in descriptors
                if abs(
                    item["header_completed_at_input_sample"] - candidate_sample
                ) <= int(round(20.0 * recording.sample_rate))
            ]
            attempt["status"] = (
                "exact_header" if attempt_nearby else "no_exact_header"
            )
            alignment_attempts.append(attempt)
            if attempt_nearby:
                decoded = candidate_decode
                nearby = attempt_nearby
                read_start = attempt_start
                read_stop = attempt_stop
                selected_shift = alignment_shift
                break
        if not nearby:
            status = (
                "not_acquired"
                if alignment_attempts
                and all(
                    item["status"] == "not_acquired"
                    for item in alignment_attempts
                )
                else "no_exact_header"
            )
            evidence: dict[str, Any] = {
                "candidate_input_sample": candidate_sample,
                "alignment_attempts": alignment_attempts,
                "status": status,
            }
            if last_error is not None and status == "not_acquired":
                evidence["reason"] = str(last_error)
            refinements.append({
                **evidence,
            })
            core_start = compatibility_core_start(
                candidate_event, candidate_sample
            )
            unresolved_core_counts[core_start] = (
                unresolved_core_counts.get(core_start, 0) + 1
            )
            continue
        assert decoded is not None
        descriptor = min(
            nearby,
            key=lambda item: abs(
                item["header_completed_at_input_sample"] - candidate_sample
            ),
        )
        header_ids = set(descriptor["header_event_ids"])
        source = [
            copy.deepcopy(event) for event in decoded.text_events
            if event["id"] in header_ids
        ]
        for event in source:
            event["provenance"]["bounded_header_refinement"] = {
                "candidate_input_sample": candidate_sample,
                "alignment_shift_input_samples": selected_shift,
                "read_interval": {"start": read_start, "stop": read_stop},
            }
        refined_headers.extend(source)
        refined_intervals.append(descriptor["header_wire_interval"])
        refined_recognition_intervals.append(
            (
                min(event["recognized_at_input_sample"] for event in source),
                max(event["recognized_at_input_sample"] for event in source),
            )
        )
        accepted_intervals.append(descriptor["header_wire_interval"])
        accepted_completions.append(descriptor["header_completed_at_input_sample"])
        accepted.append(descriptor)
        refinements.append({
            "candidate_input_sample": candidate_sample,
            "alignment_shift_input_samples": selected_shift,
            "alignment_attempts": alignment_attempts,
            "read_interval": {"start": read_start, "stop": read_stop},
            "status": "recovered",
            "header_text": descriptor["header_text"],
            "header_wire_interval": descriptor["header_wire_interval"],
        })
    compatibility_core = int(round(180.0 * recording.sample_rate))
    compatibility_context = int(round(8.0 * recording.sample_rate))
    broadly_damaged = (
        2 * len(unresolved_core_counts) > max(1, len(accepted))
    )
    compatibility_core_starts = sorted(
        core_start
        for core_start, count in unresolved_core_counts.items()
        if broadly_damaged or count >= 3
    )
    for core_start in compatibility_core_starts:
        core_stop = min(recording.requested_stop, core_start + compatibility_core)
        read_start = max(recording.requested_start, core_start - compatibility_context)
        read_stop = min(recording.requested_stop, core_stop + compatibility_context)
        core_windows = [
            event["provenance"].get("bounded_window", {})
            for event in byte_events
            if read_start <= event["recognized_at_input_sample"] < read_stop
        ]
        core_centers = [
            float(window["center_hz"])
            for window in core_windows if window.get("center_hz") is not None
        ]
        core_orientations = [
            str(window["orientation"])
            for window in core_windows if window.get("orientation") is not None
        ]
        try:
            decoded = decode_mfsk_text(
                recording.read_complex64(read_start, read_stop),
                input_start=read_start,
                sample_rate=recording.sample_rate,
                orientation_hint=(
                    max(set(core_orientations), key=core_orientations.count)
                    if core_orientations else config.orientation
                ),
                trace_level="none",
                mode=config.mode,
                center_hint_hz=(
                    float(np.median(core_centers))
                    if core_centers else config.center_hz
                ),
                persistent_tone_policy=config.persistent_tone_policy,
                fit_transition_clock=True,
            )
        except ValueError as error:
            refinements.append({
                "core_interval": {"start": core_start, "stop": core_stop},
                "read_interval": {"start": read_start, "stop": read_stop},
                "status": "compatibility_core_not_acquired",
                "reason": str(error),
            })
            continue
        descriptors, _ = parse_picture_headers(decoded.text_events)
        recovered = 0
        for descriptor in descriptors:
            completion = int(descriptor["header_completed_at_input_sample"])
            if not core_start <= completion < core_stop:
                continue
            if any(
                item["header_text"] == descriptor["header_text"]
                and abs(
                    int(item["header_completed_at_input_sample"]) - completion
                ) <= int(round(2.0 * recording.sample_rate))
                for item in accepted
            ):
                continue
            header_ids = set(descriptor["header_event_ids"])
            source = [
                copy.deepcopy(event) for event in decoded.text_events
                if event["id"] in header_ids
            ]
            for event in source:
                event["provenance"]["bounded_header_refinement"] = {
                    "kind": "targeted_compatibility_core",
                    "core_interval": {"start": core_start, "stop": core_stop},
                    "read_interval": {"start": read_start, "stop": read_stop},
                }
            refined_headers.extend(source)
            refined_intervals.append(descriptor["header_wire_interval"])
            refined_recognition_intervals.append((
                min(event["recognized_at_input_sample"] for event in source),
                max(event["recognized_at_input_sample"] for event in source),
            ))
            accepted.append(descriptor)
            accepted_intervals.append(descriptor["header_wire_interval"])
            accepted_completions.append(completion)
            recovered += 1
        refinements.append({
            "core_interval": {"start": core_start, "stop": core_stop},
            "read_interval": {"start": read_start, "stop": read_stop},
            "status": "compatibility_core_complete",
            "recovered_header_count": recovered,
        })
    if not refined_headers:
        return events, refinements
    retained = [
        event for event in events
        if not any(
            interval["start"] <= event["wire_interval"]["start"]
            and event["wire_interval"]["stop"] <= interval["stop"]
            for interval in refined_intervals
        )
        and not any(
            start <= event["recognized_at_input_sample"] <= stop
            for start, stop in refined_recognition_intervals
        )
    ]
    retained.extend(refined_headers)
    retained.sort(key=lambda item: item["recognized_at_input_sample"])
    return retained, refinements


def _suppress_accepted_picture_text(
    text_decode: MFSKTextDecode, picture_decode: PictureDecode
) -> None:
    """Exclude false text only inside waveform-accepted picture intervals."""
    suppressed_ids: set[str] = set()
    for picture in picture_decode.pictures:
        start = picture["prologue_interval"]["start"]
        stop = next(
            item["input_sample"]
            for item in picture["end_alternatives"]
            if item["selected"]
        )
        ids = [
            event["id"]
            for event in text_decode.text_events
            if start <= event["recognized_at_input_sample"] < stop
        ]
        picture["suppressed_text_event_ids"] = ids
        suppressed_ids.update(ids)
    if not suppressed_ids:
        return
    text_decode.text_events[:] = [
        event for event in text_decode.text_events if event["id"] not in suppressed_ids
    ]
    octets = [
        event["octet"]
        for event in text_decode.text_events
        if event["octet"] is not None and event["control_role"] is None
    ]
    text_decode.text_summary["octets"] = octets
    text_decode.text_summary["text"] = bytes(octets).decode("latin-1")


def _decode_bounded_pictures(
    recording: SigmfRecording,
    text_decode: MFSKTextDecode,
    *,
    mode: str,
    artifact_dir: Path | None,
    artifact_path_prefix: str | None,
    run_wall_start: float,
    component_estimator: str,
    component_window: str,
    filter_profile: str,
    boundary_estimator: str,
    range_config: PictureRangeConfig | None,
) -> PictureDecode:
    descriptors, rejected = parse_picture_headers(text_decode.text_events)
    first_descriptor_wall_seconds = (
        time.perf_counter() - run_wall_start if descriptors else None
    )
    first_complete_wall_seconds: float | None = None
    pictures: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    clipped = 0
    damaged = 0
    maximum_materialized = 0
    requested_read_samples = 0
    range_execution: list[dict[str, Any]] = []
    for descriptor in descriptors:
        component_count = (
            descriptor["width"] * descriptor["height"]
            * (3 if descriptor["color"] else 1)
        )
        read_start = max(
            recording.requested_start,
            descriptor["header_completed_at_input_sample"]
            - int(round(2.0 * recording.sample_rate)),
        )
        if range_config is None:
            duration = (
                2.5
                + component_count * descriptor["samples_per_component"] / 8000.0
                + 12.0
            )
            read_stop = min(
                recording.requested_stop,
                descriptor["header_completed_at_input_sample"]
                + int(round(duration * recording.sample_rate)),
            )
        else:
            # Boundary/flush evidence and the one-sided guard need only a small
            # prefix. Raster samples are subsequently read by exact FIR ranges.
            read_stop = min(
                recording.requested_stop,
                descriptor["header_completed_at_input_sample"]
                + int(round(3.0 * recording.sample_rate)),
            )
        bounded_samples = recording.read_complex64(read_start, read_stop)
        requested_read_samples += read_stop - read_start
        maximum_materialized = max(maximum_materialized, len(bounded_samples))
        header_ids = set(descriptor["header_event_ids"])
        source_events = [
            event for event in text_decode.text_events if event["id"] in header_ids
        ]
        source_centers = [
            float(event["provenance"]["bounded_window"]["center_hz"])
            for event in source_events
            if "bounded_window" in event["provenance"]
        ]
        source_orientations = [
            event["provenance"]["bounded_window"]["orientation"]
            for event in source_events
            if "bounded_window" in event["provenance"]
        ]
        center_hz = (
            float(np.median(source_centers))
            if source_centers else text_decode.mode_segment["center_hz"]
        )
        orientation = (
            max(set(source_orientations), key=source_orientations.count)
            if source_orientations else text_decode.mode_segment["orientation"]
        )
        decoded = decode_pictures(
            bounded_samples,
            input_start=read_start,
            sample_rate=recording.sample_rate,
            mode=mode,
            orientation=orientation,
            center_hz=center_hz,
            text_events=source_events,
            symbol_clock=text_decode.transition_clock,
            symbol_clock_covariance=text_decode.transition_clock_covariance,
            decoded_bits=text_decode.decoded_bits,
            artifact_dir=artifact_dir,
            artifact_path_prefix=artifact_path_prefix,
            id_offset=len(pictures),
            component_estimator=component_estimator,
            component_window=component_window,
            filter_profile=filter_profile,
            boundary_estimator=boundary_estimator,
            component_source=(
                PictureSampleSource(
                    input_start=recording.requested_start,
                    input_stop=recording.requested_stop,
                    identity=str(recording.data_path.resolve()),
                    reader=recording.read_complex64,
                )
                if range_config is not None else None
            ),
            range_config=range_config,
        )
        range_execution.extend(decoded.diagnostics.get("range_execution", []))
        requested_read_samples += decoded.diagnostics.get(
            "picture_requested_samples", 0
        )
        recovery_start = min(
            recording.requested_stop,
            decoded.pictures[0]["return_to_text_reacquisition_interval"]["stop"],
        ) if decoded.pictures else read_stop
        recovery_stop = min(
            recording.requested_stop,
            recovery_start + int(round(10.0 * recording.sample_rate)),
        )
        recovery_samples = (
            recording.read_complex64(recovery_start, recovery_stop)
            if recovery_stop > recovery_start else np.empty(0, dtype=np.complex64)
        )
        requested_read_samples += len(recovery_samples)
        maximum_materialized = max(maximum_materialized, len(recovery_samples))
        _reacquire_picture_text_epochs(
            recovery_samples,
            input_start=recovery_start,
            sample_rate=recording.sample_rate,
            mode=mode,
            orientation=orientation,
            center_hz=center_hz,
            picture_decode=decoded,
            text_decode=text_decode,
        )
        pictures.extend(decoded.pictures)
        if (
            first_complete_wall_seconds is None
            and any(item["complete"] for item in decoded.pictures)
        ):
            first_complete_wall_seconds = time.perf_counter() - run_wall_start
        transitions.extend(decoded.transitions)
        artifacts.extend(decoded.artifacts)
        clipped += decoded.diagnostics["clipped_components"]
        damaged += decoded.diagnostics["damaged_components"]
        del decoded, bounded_samples, recovery_samples
    return PictureDecode(
        pictures=pictures,
        transitions=transitions,
        artifacts=artifacts,
        diagnostics={
            "header_candidates": len(descriptors),
            "header_rejections": rejected,
            "picture_count": len(pictures),
            "clipped_components": clipped,
            "damaged_components": damaged,
            "persistent_artifact_files": sum(
                item["kind"] != "inline_uint8_raster" for item in artifacts
            ),
            "artifact_bytes": sum(item.get("bytes", 0) for item in artifacts),
            "working_set_organization": (
                "bounded_deterministic_picture_ranges"
                if range_config is not None else "complete_picture_bounded_windows"
            ),
            "maximum_materialized_iq_samples": maximum_materialized,
            "requested_read_samples": requested_read_samples,
            "requested_read_bytes": requested_read_samples * recording.bytes_per_sample,
            "range_execution": range_execution,
            "first_picture_descriptor_wall_seconds": (
                first_descriptor_wall_seconds
            ),
            "first_complete_picture_wall_seconds": first_complete_wall_seconds,
        },
    )


def _reacquire_picture_text_epochs(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
    mode: str,
    orientation: str,
    center_hz: float,
    picture_decode: Any,
    text_decode: Any,
) -> None:
    """Start bounded, independent modem epochs after completed pictures.

    Header discovery still uses the reference complete-region pass, but no
    event from that pass is credited as post-picture reacquisition.
    """
    context_samples = int(round(10.0 * sample_rate))
    attempted = 0
    acquired = 0
    for index, picture in enumerate(picture_decode.pictures, 1):
        interval = picture["return_to_text_reacquisition_interval"]
        local_start = interval["stop"] - input_start
        local_stop = min(len(samples), local_start + context_samples)
        evidence = {
            "attempted": False,
            "context_interval": {
                "start": input_start + max(0, local_start),
                "stop": input_start + max(0, local_stop),
            },
            "organization": "bounded_complete_region_reference",
            "source": "independent_post_picture_iq_decode",
        }
        if not picture["complete"] or local_stop - local_start < sample_rate:
            picture["reacquisition_evidence"] = evidence
            continue
        evidence["attempted"] = True
        attempted += 1
        try:
            resumed = decode_mfsk_text(
                samples[local_start:local_stop],
                input_start=input_start + local_start,
                sample_rate=sample_rate,
                orientation_hint=orientation,
                trace_level="none",
                mode=mode,
                center_hint_hz=center_hz,
            )
        except ValueError as error:
            evidence.update({"status": "not_acquired", "failure": str(error)})
            picture["first_trustworthy_resumed_text_input_sample"] = None
            picture["reacquisition_evidence"] = evidence
            continue
        epoch = resumed.text_epochs[0] if resumed.text_epochs else None
        if epoch is None:
            evidence["status"] = "no_text_epoch"
            picture["first_trustworthy_resumed_text_input_sample"] = None
            picture["reacquisition_evidence"] = evidence
            continue
        epoch = {
            **epoch,
            "id": f"text-epoch-after-picture-{index:04d}",
            "start_evidence": "independent_post_picture_iq_decode",
            "start_reset_cause": "picture_completion",
            "state_assumptions": {
                **epoch["state_assumptions"],
                "deinterleaver": "neutral_fill",
                "fec_initial_state": "unknown",
                "varicode": "empty_pending_word",
                "prior_text_modem_state": "discarded_at_picture_start",
            },
            "retained_state": ["frequency_track", "clock_rate_prior"],
            "discarded_state": ["deinterleaver", "fec_survivors", "varicode"],
            "picture": picture["id"],
        }
        committed_start = epoch["committed_interval"]["start"]
        trustworthy = next(
            (
                event
                for event in resumed.text_events
                if event["octet"] is not None
                and event["wire_interval"]["start"] >= committed_start
                and float(event["confidence"]["value"]) >= 0.25
                and not event["damage_flags"]
            ),
            None,
        )
        evidence.update(
            {
                "status": "acquired" if trustworthy is not None else "warmup_only",
                "epoch": epoch["id"],
                "state_assumptions": epoch["state_assumptions"],
                "hypotheses": epoch["hypotheses"],
                "decoded_event_count": len(resumed.text_events),
                "committed_octet_count": sum(
                    event["octet"] is not None
                    and event["wire_interval"]["start"] >= committed_start
                    and float(event["confidence"]["value"]) >= 0.25
                    and not event["damage_flags"]
                    for event in resumed.text_events
                ),
            }
        )
        acquired += trustworthy is not None
        text_decode.text_epochs.append(epoch)
        picture["following_text_epoch"] = epoch["id"]
        picture["first_trustworthy_resumed_text_input_sample"] = (
            trustworthy["recognized_at_input_sample"]
            if trustworthy is not None
            else None
        )
        picture["reacquisition_evidence"] = evidence
        picture_decode.transitions.append(
            {
                "id": f"transition-picture-to-text-{index:04d}",
                "picture": picture["id"],
                "kind": "picture_to_text",
                "completion_reason": picture["completion_reason"],
                "boundary_alternatives": picture["end_alternatives"],
                "following_text_epoch": epoch["id"],
                "evidence": evidence,
            }
        )
    picture_decode.diagnostics.update(
        {
            "post_picture_reacquisition_attempts": attempted,
            "post_picture_reacquisitions": acquired,
            "post_picture_context_samples_per_attempt": context_samples,
            "post_picture_working_set_organization": (
                "bounded_10_second_complete_region"
            ),
        }
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    _validate_schema(manifest, SCHEMA_NAME)


def _validate_schema(document: dict[str, Any], schema_name: str) -> None:
    schema = load_json("schemas", schema_name)
    jsonschema.Draft202012Validator(schema).validate(document)


def write_manifest_atomic(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Make bytes_written describe the final manifest itself. Iteration reaches
    # a fixed point once the decimal digit count stops changing.
    for _ in range(8):
        payload = _manifest_bytes(manifest)
        previous = manifest["diagnostics"]["bytes_written"]
        artifact_bytes = sum(
            artifact.get("bytes", 0) for artifact in manifest["artifacts"]
        )
        manifest["diagnostics"]["bytes_written"] = len(payload) + artifact_bytes
        if previous == len(payload) + artifact_bytes:
            break
    payload = _manifest_bytes(manifest)
    validate_manifest(manifest)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _dependency_versions() -> dict[str, str]:
    versions = {
        "numpy": np.__version__,
        "jsonschema": importlib.metadata.version("jsonschema"),
    }
    for optional in ("scipy", "sigmf"):
        try:
            versions[optional] = importlib.metadata.version(optional)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)
