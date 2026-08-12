from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import hashlib
import math
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any, Callable
import zlib

import numpy as np
from scipy import signal

from .tracking import ClockTrack, FrequencyTrack
from .text_decode import _tone_crossover
from .wire import picture_flush_tones

HEADER = re.compile(
    rb"Pic:(?P<width>[1-9][0-9]{0,3})x(?P<height>[1-9][0-9]{0,3})"
    rb"(?P<color>C)?(?:p(?P<speed>[0-9]+))?;"
)


@dataclass(frozen=True)
class PictureDecode:
    pictures: list[dict[str, Any]]
    transitions: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class ComponentClock:
    """Affine, fractional picture-component clock in input coordinates."""

    epoch_input_sample: float
    samples_per_component: float
    rate_error_ppm: float = 0.0
    phase_offset_samples: float = 0.0
    uncertainty_samples: float = 0.0
    source: str = "nominal_header_speed"

    @property
    def tracked_samples_per_component(self) -> float:
        return self.samples_per_component * (1.0 + self.rate_error_ppm * 1e-6)

    def boundary(self, component: int) -> float:
        return (
            self.epoch_input_sample
            + self.phase_offset_samples
            + component * self.tracked_samples_per_component
        )

    def interval(self, component: int) -> tuple[int, int]:
        start = int(round(self.boundary(component)))
        stop = int(round(self.boundary(component + 1)))
        return start, max(start + 1, stop)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "affine_fractional_component_clock",
            "epoch_input_sample": self.epoch_input_sample,
            "nominal_samples_per_component": self.samples_per_component,
            "tracked_samples_per_component": self.tracked_samples_per_component,
            "rate_error_ppm": self.rate_error_ppm,
            "phase_offset_input_samples": self.phase_offset_samples,
            "uncertainty_input_samples": self.uncertainty_samples,
            "source": self.source,
        }


@dataclass(frozen=True)
class PictureRangeConfig:
    """Independent resource controls for the P11D picture range path."""

    workers: int = 1
    components_per_range: int = 16_384
    max_in_flight_ranges: int = 1

    def __post_init__(self) -> None:
        if self.workers < 1:
            raise ValueError("picture range workers must be positive")
        if self.components_per_range < 1:
            raise ValueError("picture range size must be positive")
        if self.max_in_flight_ranges < 1:
            raise ValueError("maximum in-flight picture ranges must be positive")


@dataclass(frozen=True)
class PictureSampleSource:
    """A bounded, random-access IQ source used by an immutable picture job."""

    input_start: int
    input_stop: int
    identity: str
    reader: Callable[[int, int], np.ndarray]

    def __post_init__(self) -> None:
        if self.input_stop <= self.input_start:
            raise ValueError("picture sample source must have a non-empty interval")


@dataclass(frozen=True)
class PictureJob:
    """All information needed to decode one picture's component evidence."""

    id: str
    source_identity: str
    source_start: int
    source_stop: int
    component_count: int
    component_clock: ComponentClock
    sample_rate: float
    center_hz: float
    bandwidth_hz: float
    orientation: str
    component_estimator: str
    component_window: str
    filter_profile: str
    width: int = 0
    height: int = 0
    color: bool = False
    output_identity: str = ""
    header_event_ids: tuple[str, ...] = ()
    carrier_anchors: tuple[tuple[int, float, float, str], ...] = ()

    def __post_init__(self) -> None:
        if self.source_stop <= self.source_start or self.component_count < 0:
            raise ValueError("invalid picture job extent")
        if self.orientation not in {"normal", "reverse"}:
            raise ValueError("picture job orientation must be fixed")
        if bool(self.width) != bool(self.height) or self.width < 0 or self.height < 0:
            raise ValueError("picture job geometry is invalid")
        if self.width and self.component_count != self.width * self.height * (
            3 if self.color else 1
        ):
            raise ValueError("picture job geometry and component count disagree")


@dataclass(frozen=True)
class PictureComponentRange:
    job_id: str
    ordinal: int
    first_component: int
    stop_component: int


@dataclass(frozen=True)
class PictureRangeDecode:
    frequencies: np.ndarray
    quality: np.ndarray
    component_intervals: tuple[tuple[int, int], ...]
    diagnostics: dict[str, Any]


class PictureRangeCancelled(RuntimeError):
    pass


class PictureRangeFailure(RuntimeError):
    def __init__(self, item: PictureComponentRange, error: BaseException) -> None:
        super().__init__(
            f"picture range {item.ordinal} [{item.first_component}, "
            f"{item.stop_component}) failed: {error}"
        )
        self.picture_range = item
        self.__cause__ = error


def decode_pictures(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
    mode: str,
    orientation: str,
    center_hz: float,
    text_events: list[dict[str, Any]],
    frequency_track: FrequencyTrack | None = None,
    symbol_clock: ClockTrack | None = None,
    symbol_clock_covariance: tuple[
        tuple[float, float], tuple[float, float]
    ] | None = None,
    decoded_bits: tuple[int, ...] = (),
    artifact_dir: Path | None = None,
    artifact_path_prefix: str | None = None,
    inline_component_limit: int = 4096,
    component_rate_error_ppm: float = 0.0,
    id_offset: int = 0,
    component_estimator: str = "fft_peak",
    component_window: str = "center_crop",
    filter_profile: str = "current_wide",
    boundary_estimator: str = "unified_grid",
    component_source: PictureSampleSource | None = None,
    range_config: PictureRangeConfig | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> PictureDecode:
    if (component_source is None) != (range_config is None):
        raise ValueError("picture component source and range config are paired")
    if frequency_track is None:
        frequency_track = FrequencyTrack.fixed(
            center_hz=center_hz,
            input_sample=input_start,
        )
    descriptors, rejected = parse_picture_headers(text_events)
    pictures: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    clipped_component_count = 0
    damaged_component_count = 0
    range_diagnostics: list[dict[str, Any]] = []
    bandwidth = 937.5 if mode == "MFSK64" else 468.75
    largest_picture = max(
        (
            descriptor["width"]
            * descriptor["height"]
            * (3 if descriptor["color"] else 1)
            for descriptor in descriptors
        ),
        default=0,
    )
    channel_samples = (
        _isolate_picture_channel(
            samples, sample_rate, center_hz, bandwidth, profile=filter_profile
        )
        if largest_picture > inline_component_limit
        else samples
    )
    for local_index, descriptor in enumerate(descriptors, 1):
        index = id_offset + local_index
        picture_id = f"picture-{index:04d}"
        transition_id = f"transition-{index:04d}"
        descriptor = {**descriptor, "id": picture_id}
        prologue_count = int(round(352 * sample_rate / 8000.0))
        transition_clock_evidence = descriptor.get(
            "transition_crossover_clock"
        )
        descriptor_clock, descriptor_covariance = (
            _transition_clock_from_evidence(transition_clock_evidence)
        )
        picture_symbol_clock = descriptor_clock or symbol_clock
        picture_symbol_clock_covariance = (
            descriptor_covariance
            if descriptor_clock is not None
            else symbol_clock_covariance
        )
        protocol_boundary_prediction = _protocol_boundary_prediction(
            mode=mode,
            sample_rate=sample_rate,
            header_completed_at=descriptor["header_completed_at_input_sample"],
            header_decoded_bit_stop=descriptor.get("header_decoded_bit_stop"),
            header_recognized_symbol=descriptor.get("header_recognized_symbol"),
            prologue_count=prologue_count,
            symbol_clock=picture_symbol_clock,
            symbol_clock_covariance=picture_symbol_clock_covariance,
        )
        if (
            protocol_boundary_prediction is not None
            and transition_clock_evidence is not None
        ):
            protocol_boundary_prediction["transition_crossover_clock"] = (
                transition_clock_evidence
            )
        component_samples_nominal = (
            descriptor["samples_per_component"] * sample_rate / 8000.0
        )
        component_samples = max(1, int(round(component_samples_nominal)))
        predicted_prologue_sample = (
            descriptor["header_completed_at_input_sample"]
            + round(0.965 * sample_rate)
        )
        prologue_center_hz = frequency_track.center_at(predicted_prologue_sample)
        expected_prologue_frequency = (
            prologue_center_hz + bandwidth / 2
            if orientation == "reverse"
            else prologue_center_hz - bandwidth / 2
        )
        component_count = (
            descriptor["width"]
            * descriptor["height"]
            * (3 if descriptor["color"] else 1)
        )
        flush_grid_prediction = None
        if (
            protocol_boundary_prediction is not None
            and (decoded_bits or descriptor.get("picture_flush_tones"))
        ):
            flush_grid_prediction = _fit_known_flush_grid(
                channel_samples,
                input_start=input_start,
                sample_rate=sample_rate,
                mode=mode,
                orientation=orientation,
                center_hz=prologue_center_hz,
                header_decoded_bit_stop=descriptor.get(
                    "header_decoded_bit_stop"
                ),
                decoded_bits=decoded_bits,
                known_flush_tones=descriptor.get("picture_flush_tones"),
                nominal_prologue_start=float(
                    protocol_boundary_prediction[
                        "nominal_predicted_prologue_start_input_sample"
                    ]
                ),
                prologue_count=prologue_count,
            )
            protocol_boundary_prediction["flush_grid_verification"] = (
                flush_grid_prediction
            )
        if boundary_estimator == "unified_grid":
            if protocol_boundary_prediction is None:
                raise ValueError(
                    "unified picture boundary estimation requires decoded-bit phase"
                )
            unified_grid = _fit_unified_boundary_grid(
                mode=mode,
                sample_rate=sample_rate,
                prologue_count=prologue_count,
                protocol_prediction=protocol_boundary_prediction,
                symbol_clock=picture_symbol_clock,
                symbol_clock_covariance=picture_symbol_clock_covariance,
                transition_clock_evidence=transition_clock_evidence,
                flush_grid_prediction=flush_grid_prediction,
            )
            protocol_boundary_prediction["unified_grid_estimate"] = unified_grid
            if unified_grid.get("status") != "estimated":
                raise ValueError(
                    "unified picture boundary evidence is insufficient: "
                    f"{unified_grid.get('status')}"
                )
            raster_start_fractional = float(
                unified_grid[
                    "predicted_first_raster_input_sample_fractional"
                ]
                - input_start
            )
            raster_start = int(round(raster_start_fractional))
            boundary_uncertainty_samples = float(
                unified_grid["raster_uncertainty_input_samples"]
            )
            boundary_uncertainty_calibrated = bool(
                unified_grid.get("uncertainty_calibrated", False)
            )
            alignment_score = float(
                unified_grid["local_residual_sigma_input_samples"]
            )
            prologue_local = int(
                round(
                    unified_grid[
                        "predicted_prologue_start_input_sample_fractional"
                    ]
                    - input_start
                )
            )
            prologue_frequency = _phase_advance_frequency(
                channel_samples[
                    max(0, prologue_local) : max(0, raster_start)
                ],
                sample_rate,
            )
            sigma = max(0.25, boundary_uncertainty_samples)
            start_alternatives = [
                {
                    "rank": rank,
                    "first_raster_input_sample": int(
                        round(raster_start_fractional + offset)
                    ),
                    "first_raster_input_sample_fractional": (
                        raster_start_fractional + offset
                    ),
                    "uncertainty_sigma_offset": sigma_offset,
                    "score": 0.5 * sigma_offset * sigma_offset,
                    "selected": sigma_offset == 0.0,
                }
                for rank, sigma_offset, offset in (
                    (1, 0.0, 0.0),
                    (2, -1.0, -sigma),
                    (3, 1.0, sigma),
                )
            ]
            protocol_boundary_prediction["status"] = (
                "qualified_unified_global_text_local_header_flush_grid"
            )
            protocol_boundary_prediction["operative"] = True
            boundary_alignment_kind = (
                "unified_global_text_local_header_flush_grid"
            )
            try:
                (
                    local_guard_start,
                    _,
                    local_guard_score,
                    local_guard_alternatives,
                ) = _locate_protocol_change(
                    channel_samples,
                    predicted_raster=int(round(raster_start_fractional)),
                    sample_rate=sample_rate,
                    mode=mode,
                    prologue_count=prologue_count,
                    expected_frequency=expected_prologue_frequency,
                    center_hz=prologue_center_hz,
                    bandwidth_hz=bandwidth,
                    component_samples=component_samples,
                    component_count=component_count,
                )
                protocol_boundary_prediction["local_change_guard"] = {
                    "status": "one_sided_constraint",
                    "selected_input_sample": input_start + local_guard_start,
                    "offset_from_unified_grid_input_samples": (
                        local_guard_start - raster_start_fractional
                    ),
                    "possible_late_primary_prediction": bool(
                        local_guard_start
                        < raster_start_fractional
                        - 0.5 * component_samples
                    ),
                    "interpretation": (
                        "an earlier modulation change can falsify a late grid; "
                        "a later change is compatible with leading zeros"
                    ),
                    "score": local_guard_score,
                    "alternatives": local_guard_alternatives,
                    "operative": False,
                }
            except ValueError as error:
                protocol_boundary_prediction["local_change_guard"] = {
                    "status": "unavailable",
                    "reason": str(error),
                    "operative": False,
                }
        else:
            raise ValueError(
                f"unsupported picture boundary estimator: {boundary_estimator}"
            )
        clock_uncertainty_samples = max(
            0.5, abs(component_samples_nominal - component_samples)
        )
        clock_uncertainty_samples = max(
            clock_uncertainty_samples, boundary_uncertainty_samples
        )
        component_clock_source = (
            "header_speed_with_supplied_rate_evidence"
            if component_rate_error_ppm
            else "header_speed_nominal_fractional"
        )
        if picture_symbol_clock is not None:
            protocol_boundary_prediction["component_rate_candidate"] = {
                "estimated_rate_error_ppm": picture_symbol_clock.rate_error_ppm,
                "source": "global_transition_crossover_clock",
                "status": "not_separately_qualified",
                "operative": False,
            }
        component_clock = ComponentClock(
            epoch_input_sample=raster_start_fractional,
            samples_per_component=component_samples_nominal,
            rate_error_ppm=component_rate_error_ppm,
            uncertainty_samples=clock_uncertainty_samples,
            source=component_clock_source,
        )
        raster_stop = int(round(component_clock.boundary(component_count)))
        observed_stop = min(
            raster_stop,
            (
                component_source.input_stop - input_start
                if component_source is not None
                else len(channel_samples)
            ),
        )
        observed_count = sum(
            component_clock.interval(component)[1] <= observed_stop
            for component in range(component_count)
        )
        if component_source is None:
            frequencies, quality, component_intervals = _fractional_component_frequencies(
                channel_samples,
                observed_count,
                sample_rate,
                component_clock=component_clock,
                center_hz=frequency_track.center_at(input_start + raster_start),
                bandwidth_hz=bandwidth,
                estimator=component_estimator,
                component_window=component_window,
            )
        else:
            absolute_clock = ComponentClock(
                epoch_input_sample=input_start + component_clock.epoch_input_sample,
                samples_per_component=component_clock.samples_per_component,
                rate_error_ppm=component_clock.rate_error_ppm,
                phase_offset_samples=component_clock.phase_offset_samples,
                uncertainty_samples=component_clock.uncertainty_samples,
                source=component_clock.source,
            )
            ranged = decode_picture_component_ranges(
                PictureJob(
                    id=picture_id,
                    source_identity=component_source.identity,
                    source_start=component_source.input_start,
                    source_stop=component_source.input_stop,
                    component_count=observed_count,
                    component_clock=absolute_clock,
                    sample_rate=sample_rate,
                    center_hz=float(
                        frequency_track.center_at(input_start + raster_start)
                    ),
                    bandwidth_hz=bandwidth,
                    orientation=orientation,
                    component_estimator=component_estimator,
                    component_window=component_window,
                    filter_profile=(
                        filter_profile
                        if largest_picture > inline_component_limit else "none"
                    ),
                    width=descriptor["width"],
                    height=descriptor["height"],
                    color=descriptor["color"],
                    output_identity=f"raster-{index:04d}",
                    header_event_ids=tuple(descriptor["header_event_ids"]),
                    carrier_anchors=tuple(
                        (
                            anchor.input_sample,
                            anchor.center_hz,
                            anchor.uncertainty_hz,
                            anchor.source,
                        )
                        for anchor in frequency_track.anchors
                    ),
                ),
                component_source,
                range_config,
                cancelled=cancelled,
            )
            frequencies = ranged.frequencies
            quality = ranged.quality
            component_intervals = [
                (start - input_start, stop - input_start)
                for start, stop in ranged.component_intervals
            ]
            range_diagnostics.append(ranged.diagnostics)
        component_centers = frequency_track.center_at(
            input_start
            + np.asarray(
                [
                    0.5 * (start + stop)
                    for start, stop in component_intervals
                ],
                dtype=np.float64,
            )
        )
        direction = -1.0 if orientation == "reverse" else 1.0
        unclipped = 128.0 + direction * 256.0 * (
            frequencies - component_centers
        ) / bandwidth
        values = np.clip(np.rint(unclipped), 0, 255).astype(np.uint8)
        clipped = (unclipped < 0.0) | (unclipped > 255.0)
        damaged = quality > max(20.0, bandwidth / 16.0)
        clipped_component_count += int(np.count_nonzero(clipped))
        damaged_component_count += int(np.count_nonzero(clipped | damaged))
        raster = _assemble_raster(
            values,
            descriptor["width"],
            descriptor["height"],
            descriptor["color"],
        )
        component_records = [
            {
                "index": component,
                "input_interval": {
                    "start": input_start + component_intervals[component][0],
                    "stop": input_start + component_intervals[component][1],
                },
                "frequency_hz": float(frequencies[component]),
                "value_unclipped": float(unclipped[component]),
                "value": int(values[component]),
                "quality": {
                    "kind": "median_absolute_frequency_residual_hz",
                    "value": float(quality[component]),
                    "calibrated": False,
                },
                "damage_flags": (
                    (["clipped"] if clipped[component] else [])
                    + (["unstable_frequency"] if damaged[component] else [])
                ),
            }
            for component in range(observed_count)
        ]
        artifact_id = f"raster-{index:04d}"
        component_artifact_id = None
        if component_count <= inline_component_limit:
            artifacts.append(
                {
                    "id": artifact_id,
                    "kind": "inline_uint8_raster",
                    "shape": list(raster.shape),
                    "display_order": "RGB" if descriptor["color"] else "grayscale",
                    "values": raster.reshape(-1).tolist(),
                }
            )
        elif artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            png_name = f"{artifact_id}.png"
            png_payload = _png_bytes(raster)
            _write_atomic(artifact_dir / png_name, png_payload)
            artifacts.append(
                {
                    "id": artifact_id,
                    "kind": "png_uint8_raster",
                    "shape": list(raster.shape),
                    "display_order": "RGB" if descriptor["color"] else "grayscale",
                    "path": _artifact_path(artifact_path_prefix, png_name),
                    "sha256": hashlib.sha256(png_payload).hexdigest(),
                    "bytes": len(png_payload),
                }
            )
            component_artifact_id = f"component-evidence-{index:04d}"
            evidence_name = f"{component_artifact_id}.npz"
            evidence_path = artifact_dir / evidence_name
            _write_npz_atomic(
                evidence_path,
                frequency_hz=frequencies.astype(np.float32),
                value_unclipped=unclipped.astype(np.float32),
                value=values,
                quality_hz=quality.astype(np.float32),
                clipped=clipped,
                unstable_frequency=damaged,
                input_start=np.asarray(
                    [input_start + raster_start], dtype=np.int64
                ),
                input_samples_per_component=np.asarray(
                    [component_clock.tracked_samples_per_component], dtype=np.float64
                ),
                damage=(clipped | damaged),
            )
            evidence_bytes = evidence_path.stat().st_size
            artifacts.append(
                {
                    "id": component_artifact_id,
                    "kind": "npz_component_evidence",
                    "component_count": observed_count,
                    "path": _artifact_path(artifact_path_prefix, evidence_name),
                    "sha256": _sha256_file(evidence_path),
                    "bytes": evidence_bytes,
                    "arrays": {
                        "frequency_hz": "float32",
                        "value_unclipped": "float32",
                        "value": "uint8",
                        "quality_hz": "float32",
                        "clipped": "bool",
                        "unstable_frequency": "bool",
                        "input_start": "int64[1]",
                        "input_samples_per_component": "float64[1]",
                        "damage": "bool",
                    },
                }
            )
            component_records = []
        else:
            raise ValueError(
                "large picture requires an artifact output directory"
            )
        available_stop = (
            component_source.input_stop - input_start
            if component_source is not None else len(samples)
        )
        post_flush_stop = min(
            available_stop,
            raster_stop + int(round((1.440 if mode == "MFSK64" else 1.728) * sample_rate)),
        )
        resumed = next(
            (
                event["wire_interval"]["start"]
                for event in text_events
                if event["wire_interval"]["start"] >= input_start + post_flush_stop
                and event["octet"] is not None
            ),
            None,
        )
        public_descriptor = {
            key: value
            for key, value in descriptor.items()
            if key not in {"picture_flush_tones", "transition_crossover_clock"}
        }
        pictures.append(
            {
                **public_descriptor,
                "mode": mode,
                "orientation": orientation,
                "prologue_interval": {
                    "start": input_start + raster_start - prologue_count,
                    "stop": input_start + raster_start,
                },
                "first_raster_input_sample": input_start + raster_start,
                "first_raster_input_sample_fractional": (
                    input_start + raster_start_fractional
                ),
                "protocol_boundary_prediction": protocol_boundary_prediction,
                "expected_component_count": component_count,
                "observed_component_count": observed_count,
                "complete": observed_count == component_count,
                "completion_reason": (
                    "expected_component_count"
                    if observed_count == component_count
                    else "input_interval_exhausted"
                ),
                "component_clock": component_clock.to_dict(),
                "carrier_track_assumption": {
                    "policy": "interpolate_or_hold_piecewise_frequency_track",
                    "track": frequency_track.to_dict(),
                },
                "component_estimator": component_estimator,
                "damage_summary": {
                    "component_count": int(np.count_nonzero(clipped | damaged)),
                    "clipped_count": int(np.count_nonzero(clipped)),
                    "unstable_frequency_count": int(np.count_nonzero(damaged)),
                    "threshold_calibrated": False,
                },
                "start_alternatives": start_alternatives,
                "end_alternatives": _picture_end_alternatives(
                    input_start, raster_stop, component_clock
                ),
                "raster_artifact": artifact_id,
                "component_evidence": component_records,
                "component_evidence_artifact": component_artifact_id,
                "return_to_text_reacquisition_interval": {
                    "start": input_start + min(raster_stop, available_stop),
                    "stop": input_start + post_flush_stop,
                },
                "first_trustworthy_resumed_text_input_sample": resumed,
                "following_text_epoch": None,
            }
        )
        transitions.append(
            {
                "id": transition_id,
                "picture": picture_id,
                "kind": "text_to_picture",
                "header_recognized_at_input_sample": descriptor[
                    "header_completed_at_input_sample"
                ],
                "prologue_interval": pictures[-1]["prologue_interval"],
                "first_raster_input_sample": input_start + raster_start,
                "alignment": {
                    "kind": boundary_alignment_kind,
                    "score": alignment_score,
                    "measured_prologue_frequency_hz": prologue_frequency,
                    "inferred_picture_center_hz": prologue_center_hz,
                    "frequency_track": frequency_track.to_dict(),
                    "uncertainty_input_samples": boundary_uncertainty_samples,
                    "uncertainty_calibrated": boundary_uncertainty_calibrated,
                    "score_margin_to_next_distinct_hypothesis": (
                        float(start_alternatives[1]["score"])
                        - float(start_alternatives[0]["score"])
                        if len(start_alternatives) > 1
                        else None
                    ),
                    "ambiguity_assessment": (
                        "uncalibrated_distinct_hypotheses_retained"
                    ),
                    "ranked_start_alternatives": start_alternatives,
                },
            }
        )
    return PictureDecode(
        pictures=pictures,
        transitions=transitions,
        artifacts=artifacts,
        diagnostics={
            "header_candidates": len(descriptors),
            "header_rejections": rejected,
            "picture_count": len(pictures),
            "clipped_components": clipped_component_count,
            "damaged_components": damaged_component_count,
            "persistent_artifact_files": sum(
                artifact["kind"] != "inline_uint8_raster"
                for artifact in artifacts
            ),
            "artifact_bytes": sum(
                artifact.get("bytes", 0) for artifact in artifacts
            ),
            "component_estimator": component_estimator,
            "boundary_estimator": "unified_grid",
            "range_execution": range_diagnostics,
            "picture_requested_samples": sum(
                item["requested_samples"] for item in range_diagnostics
            ),
        },
    )


def _isolate_picture_channel(
    samples: np.ndarray,
    sample_rate: float,
    center_hz: float,
    bandwidth_hz: float,
    profile: str = "current_wide",
) -> np.ndarray:
    taps = _picture_filter_taps(sample_rate, center_hz, bandwidth_hz, profile)
    # A whole-window FFT convolution temporarily allocates several complex128
    # arrays and dominated the bounded picture working set.  The same FIR can
    # be applied causally in complex64 and shifted by its known linear-phase
    # delay to preserve the prior ``mode="same"`` coordinate convention.
    filtered = signal.lfilter(taps, np.asarray([1.0], dtype=np.float32), samples)
    filtered = filtered.astype(np.complex64, copy=False)
    delay = (len(taps) - 1) // 2
    if delay:
        filtered[:-delay] = filtered[delay:]
        filtered[-delay:] = 0.0
    return filtered


def _picture_filter_taps(
    sample_rate: float,
    center_hz: float,
    bandwidth_hz: float,
    profile: str,
) -> np.ndarray:
    if profile == "none":
        return np.asarray([1.0], dtype=np.float32)
    if profile == "current_wide":
        guard_hz = bandwidth_hz * 0.75
        taps_count = 257
    elif profile == "response_matched":
        guard_hz = bandwidth_hz * 0.10
        taps_count = 1025
    else:
        raise ValueError(f"unsupported picture filter profile: {profile}")
    low = max(1.0, center_hz - bandwidth_hz / 2.0 - guard_hz)
    high = min(
        sample_rate / 2.0 - 1.0,
        center_hz + bandwidth_hz / 2.0 + guard_hz,
    )
    return signal.firwin(
        taps_count,
        [low, high],
        pass_zero=False,
        fs=sample_rate,
        window=("kaiser", 7.0),
    ).astype(np.float32)


def _picture_component_ranges(
    job: PictureJob, components_per_range: int
) -> tuple[PictureComponentRange, ...]:
    return tuple(
        PictureComponentRange(
            job_id=job.id,
            ordinal=ordinal,
            first_component=first,
            stop_component=min(job.component_count, first + components_per_range),
        )
        for ordinal, first in enumerate(
            range(0, job.component_count, components_per_range)
        )
    )


def decode_picture_component_ranges(
    job: PictureJob,
    source: PictureSampleSource,
    config: PictureRangeConfig,
    *,
    cancelled: Callable[[], bool] | None = None,
) -> PictureRangeDecode:
    """Decode one picture with bounded, deterministic FIR/component ranges.

    One worker follows exactly the same range contract as multiple workers.
    Results are merged by immutable component index, never completion order.
    """
    if source.identity != job.source_identity:
        raise ValueError("picture job source identity changed")
    if (source.input_start, source.input_stop) != (
        job.source_start, job.source_stop
    ):
        raise ValueError("picture job source bounds changed")
    ranges = _picture_component_ranges(job, config.components_per_range)
    taps = _picture_filter_taps(
        job.sample_rate, job.center_hz, job.bandwidth_hz, job.filter_profile
    )
    delay = (len(taps) - 1) // 2
    denominator = np.asarray([1.0], dtype=np.float32)

    def is_cancelled() -> bool:
        return bool(cancelled is not None and cancelled())

    def decode_one(item: PictureComponentRange) -> tuple[
        PictureComponentRange,
        np.ndarray,
        np.ndarray,
        tuple[tuple[int, int], ...],
        str,
        tuple[int, int] | None,
    ]:
        if is_cancelled():
            raise PictureRangeCancelled(f"picture job {job.id} was cancelled")
        output_start = job.component_clock.interval(item.first_component)[0]
        output_stop = job.component_clock.interval(item.stop_component - 1)[1]
        valid_output_start = max(output_start, job.source_start)
        nonzero_stop = min(output_stop, job.source_stop - delay)
        owned = np.zeros(output_stop - output_start, dtype=np.complex64)
        read_interval: tuple[int, int] | None = None
        if nonzero_stop > valid_output_start:
            read_start = max(job.source_start, valid_output_start - delay)
            read_stop = min(job.source_stop, nonzero_stop + delay)
            if read_stop > read_start:
                raw = np.asarray(source.reader(read_start, read_stop))
                if raw.ndim != 1 or len(raw) != read_stop - read_start:
                    raise ValueError("picture source returned the wrong interval")
                filtered = signal.lfilter(taps, denominator, raw).astype(
                    np.complex64, copy=False
                )
                take_start = valid_output_start + delay - read_start
                take_stop = nonzero_stop + delay - read_start
                owned[
                    valid_output_start - output_start :
                    nonzero_stop - output_start
                ] = filtered[
                    take_start:take_stop
                ]
                read_interval = (read_start, read_stop)
        local_clock = ComponentClock(
            epoch_input_sample=(
                job.component_clock.boundary(item.first_component) - output_start
            ),
            samples_per_component=job.component_clock.samples_per_component,
            rate_error_ppm=job.component_clock.rate_error_ppm,
            phase_offset_samples=0.0,
            uncertainty_samples=job.component_clock.uncertainty_samples,
            source=job.component_clock.source,
        )
        frequencies, quality, local_intervals = _fractional_component_frequencies(
            owned,
            item.stop_component - item.first_component,
            job.sample_rate,
            component_clock=local_clock,
            center_hz=job.center_hz,
            bandwidth_hz=job.bandwidth_hz,
            estimator=job.component_estimator,
            component_window=job.component_window,
        )
        intervals = tuple(
            (output_start + start, output_start + stop)
            for start, stop in local_intervals
        )
        return (
            item,
            frequencies,
            quality,
            intervals,
            hashlib.sha256(owned.tobytes()).hexdigest(),
            read_interval,
        )

    frequencies = np.empty(job.component_count, dtype=np.float64)
    quality = np.empty(job.component_count, dtype=np.float64)
    interval_rows: list[tuple[int, int] | None] = [None] * job.component_count
    filtered_digests: list[str | None] = [None] * len(ranges)
    read_rows: list[tuple[int, int] | None] = [None] * len(ranges)
    submitted = 0
    executor = ThreadPoolExecutor(max_workers=config.workers)
    pending: dict[Future[Any], PictureComponentRange] = {}
    try:
        while submitted < len(ranges) or pending:
            if is_cancelled():
                raise PictureRangeCancelled(f"picture job {job.id} was cancelled")
            while (
                submitted < len(ranges)
                and len(pending) < config.max_in_flight_ranges
            ):
                item = ranges[submitted]
                pending[executor.submit(decode_one, item)] = item
                submitted += 1
            completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in completed:
                item = pending.pop(future)
                try:
                    result = future.result()
                except PictureRangeCancelled:
                    raise
                except BaseException as error:
                    raise PictureRangeFailure(item, error) from error
                completed_item, part_frequency, part_quality, part_intervals, part_digest, part_read = result
                first = completed_item.first_component
                stop = completed_item.stop_component
                frequencies[first:stop] = part_frequency
                quality[first:stop] = part_quality
                interval_rows[first:stop] = part_intervals
                filtered_digests[completed_item.ordinal] = part_digest
                read_rows[completed_item.ordinal] = part_read
    finally:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)

    if any(item is None for item in interval_rows):
        raise AssertionError("picture range merge left an unowned component")
    intervals = tuple(item for item in interval_rows if item is not None)
    reads = [item for item in read_rows if item is not None]
    return PictureRangeDecode(
        frequencies=frequencies,
        quality=quality,
        component_intervals=intervals,
        diagnostics={
            "job_id": job.id,
            "source_identity": job.source_identity,
            "output_identity": job.output_identity,
            "geometry": {
                "width": job.width,
                "height": job.height,
                "color": job.color,
            },
            "header_event_ids": list(job.header_event_ids),
            "carrier_anchor_count": len(job.carrier_anchors),
            "worker_count": config.workers,
            "components_per_range": config.components_per_range,
            "max_in_flight_ranges": config.max_in_flight_ranges,
            "range_count": len(ranges),
            "filtered_range_sha256": [
                item for item in filtered_digests if item is not None
            ],
            "filter_taps": len(taps),
            "filter_delay_samples": delay,
            "requested_read_intervals": [
                {"start": start, "stop": stop} for start, stop in reads
            ],
            "requested_samples": sum(stop - start for start, stop in reads),
            "maximum_range_output_samples": max(
                (
                    job.component_clock.interval(item.stop_component - 1)[1]
                    - job.component_clock.interval(item.first_component)[0]
                    for item in ranges
                ),
                default=0,
            ),
        },
    )


def _artifact_path(prefix: str | None, name: str) -> str:
    return f"{prefix}/{name}" if prefix else name


def _png_bytes(raster: np.ndarray) -> bytes:
    if raster.ndim == 2:
        color_type = 0
        rows = raster
    elif raster.ndim == 3 and raster.shape[2] == 3:
        color_type = 2
        rows = raster.reshape(raster.shape[0], raster.shape[1] * 3)
    else:
        raise ValueError("PNG raster must be grayscale or RGB uint8")
    height, width = raster.shape[:2]
    raw = b"".join(b"\x00" + row.tobytes() for row in rows)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return (
            struct.pack(">I", len(payload))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, level=6))
        + chunk(b"IEND", b"")
    )


def _write_atomic(path: Path, payload: bytes) -> None:
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


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp.npz", dir=path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        np.savez_compressed(temporary_path, **arrays)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_picture_headers(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    stream = bytearray()
    event_indices: list[int] = []
    for index, event in enumerate(events):
        if event["octet"] is not None:
            stream.append(event["octet"])
            event_indices.append(index)
    descriptors = []
    rejected = 0
    for match in re.finditer(rb"Pic:[^;\r\n]{0,40};", bytes(stream)):
        parsed = HEADER.fullmatch(match.group())
        if parsed is None:
            rejected += 1
            continue
        width = int(parsed.group("width"))
        height = int(parsed.group("height"))
        speed = int(parsed.group("speed") or 8)
        if width > 4095 or height > 4095 or speed not in {2, 4, 8}:
            rejected += 1
            continue
        source_events = [
            events[event_indices[offset]]
            for offset in range(match.start(), match.end())
        ]
        header_confidence = min(
            float(event["confidence"]["value"]) for event in source_events
        )
        if any(event.get("damage_flags") for event in source_events):
            rejected += 1
            continue
        descriptors.append(
            {
                "header_text": match.group().decode("ascii"),
                "width": width,
                "height": height,
                "color": parsed.group("color") is not None,
                "samples_per_component": speed,
                "confidence": {
                    "kind": "minimum_contributing_octet_confidence",
                    "value": header_confidence,
                    "calibrated": False,
                    "support": (
                        "strong"
                        if header_confidence >= 0.25
                        else "weak_exact_grammar"
                    ),
                    "acceptance_basis": "exact_grammar_and_no_damaged_octets",
                },
                "header_wire_interval": {
                    "start": min(
                        event["wire_interval"]["start"] for event in source_events
                    ),
                    "stop": max(
                        event["wire_interval"]["stop"] for event in source_events
                    ),
                },
                "header_completed_at_input_sample": source_events[-1][
                    "recognized_at_input_sample"
                ],
                "header_decoded_bit_stop": source_events[-1]
                .get("provenance", {})
                .get("decoded_bit_interval", {})
                .get("stop"),
                "header_recognized_symbol": source_events[-1]
                .get("provenance", {})
                .get("recognized_symbol"),
                "picture_flush_tones": source_events[-1]
                .get("provenance", {})
                .get("picture_flush_tones"),
                "transition_crossover_clock": source_events[-1]
                .get("provenance", {})
                .get("transition_crossover_clock"),
                "header_event_ids": [event["id"] for event in source_events],
            }
        )
    return descriptors, rejected


def _protocol_header_to_prologue_symbols(
    mode: str, header_decoded_bit_stop: int
) -> int:
    """Predict whole symbols from receiver recognition to TX prologue.

    ``header_decoded_bit_stop`` is the exclusive final-header codeword stop;
    fldigi's flush-leading one is the look-ahead bit at that index. The event's
    latest physical evidence changes lane with its parity, which cancels the
    MFSK64 transmitter's 90/91 emitted-symbol distinction.
    """
    if mode == "MFSK32":
        flush_input_bits = 1 + 107
    elif mode == "MFSK64":
        flush_input_bits = 1 + 180
    else:
        raise ValueError(f"unsupported MFSK picture mode: {mode}")
    accumulator_coded_bits = 2 * (header_decoded_bit_stop % 2)
    emitted_symbols = (
        accumulator_coded_bits + 2 * flush_input_bits
    ) // 4
    recognition_boundary_symbols = 30 + (header_decoded_bit_stop % 2)
    return emitted_symbols - recognition_boundary_symbols


def _transition_clock_from_evidence(
    evidence: dict[str, Any] | None,
) -> tuple[
    ClockTrack | None,
    tuple[tuple[float, float], tuple[float, float]] | None,
]:
    if not evidence or evidence.get("status") != "estimated":
        return None, None
    try:
        clock = ClockTrack(
            epoch_input_sample=float(evidence["epoch_input_sample"]),
            samples_per_symbol=float(evidence["nominal_symbol_samples"]),
            rate_error_ppm=float(evidence["estimated_rate_error_ppm"]),
            uncertainty_samples=float(
                evidence["phase_uncertainty_input_samples"]
            ),
        )
        covariance_values = np.asarray(
            evidence["parameter_covariance"], dtype=np.float64
        )
    except (KeyError, TypeError, ValueError):
        return None, None
    if covariance_values.shape != (2, 2) or not np.isfinite(
        covariance_values
    ).all():
        return None, None
    covariance = (
        (float(covariance_values[0, 0]), float(covariance_values[0, 1])),
        (float(covariance_values[1, 0]), float(covariance_values[1, 1])),
    )
    return clock, covariance


def _protocol_boundary_prediction(
    *,
    mode: str,
    sample_rate: float,
    header_completed_at: int,
    header_decoded_bit_stop: int | None,
    prologue_count: int,
    header_recognized_symbol: int | None = None,
    symbol_clock: ClockTrack | None = None,
    symbol_clock_covariance: tuple[
        tuple[float, float], tuple[float, float]
    ] | None = None,
) -> dict[str, Any] | None:
    if header_decoded_bit_stop is None:
        return None
    symbol_rate = 62.5 if mode == "MFSK64" else 31.25
    samples_per_symbol = sample_rate / symbol_rate
    offset_symbols = _protocol_header_to_prologue_symbols(
        mode, int(header_decoded_bit_stop)
    )
    nominal_prologue_start = float(
        header_completed_at + offset_symbols * samples_per_symbol
    )
    prologue_start = nominal_prologue_start
    raster_scale = 1.0
    uncertainty = samples_per_symbol / 2.0
    source = "mode_group_phase_and_header_event_provenance"
    if symbol_clock is not None and header_recognized_symbol is not None:
        prologue_symbol = int(header_recognized_symbol) + offset_symbols
        prologue_start = (
            symbol_clock.epoch_input_sample
            + prologue_symbol * symbol_clock.tracked_samples_per_symbol
        )
        raster_scale = (
            symbol_clock.tracked_samples_per_symbol / samples_per_symbol
        )
        source = "transition_crossover_clock_and_protocol_symbol_index"
        uncertainty = symbol_clock.uncertainty_samples
        if symbol_clock_covariance is not None:
            covariance = np.asarray(symbol_clock_covariance, dtype=np.float64)
            vector = np.asarray([1.0, float(prologue_symbol)])
            uncertainty = max(
                0.25,
                float(np.sqrt(max(0.0, vector @ covariance @ vector))),
            )
    raster_start = prologue_start + prologue_count * raster_scale
    return {
        "status": "non_operative_session10f_diagnostic",
        "source": source,
        "mode": mode,
        "header_decoded_bit_stop": int(header_decoded_bit_stop),
        "header_recognized_symbol": (
            int(header_recognized_symbol)
            if header_recognized_symbol is not None else None
        ),
        "prologue_symbol_index": (
            int(header_recognized_symbol) + offset_symbols
            if header_recognized_symbol is not None
            else None
        ),
        "recognition_to_prologue_symbols": offset_symbols,
        "nominal_samples_per_symbol": samples_per_symbol,
        "predicted_prologue_start_input_sample": int(round(prologue_start)),
        "predicted_first_raster_input_sample": int(round(raster_start)),
        "predicted_prologue_start_input_sample_fractional": prologue_start,
        "predicted_first_raster_input_sample_fractional": raster_start,
        "nominal_predicted_prologue_start_input_sample": int(
            round(nominal_prologue_start)
        ),
        "uncertainty_input_samples": uncertainty,
        "uncertainty_calibrated": False,
        "operative": False,
    }


def _fit_known_flush_grid(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
    mode: str,
    orientation: str,
    center_hz: float,
    header_decoded_bit_stop: int | None,
    decoded_bits: tuple[int, ...],
    known_flush_tones: list[int] | None,
    nominal_prologue_start: float,
    prologue_count: int,
) -> dict[str, Any]:
    """Fit the prologue boundary from transitions in the known TX flush."""
    if known_flush_tones is not None:
        tones = [int(tone) for tone in known_flush_tones]
    else:
        if (
            header_decoded_bit_stop is None
            or header_decoded_bit_stop > len(decoded_bits)
        ):
            return {"status": "decoded_bits_unavailable", "operative": False}
        tones = picture_flush_tones(
            decoded_bits[: int(header_decoded_bit_stop)], mode
        )
    if orientation == "reverse":
        tones = [15 - tone for tone in tones]
    symbol_rate = 62.5 if mode == "MFSK64" else 31.25
    symbol_samples = sample_rate / symbol_rate
    window_samples = max(8, int(round(symbol_samples / 2.0)))
    radius_samples = max(4, int(math.ceil(symbol_samples / 2.0)))
    lattice: list[float] = []
    crossings: list[float] = []
    weights: list[float] = []
    observations: list[dict[str, Any]] = []
    for index, (old_tone, new_tone) in enumerate(zip(tones, tones[1:])):
        relative_symbol = float(index + 1 - len(tones))
        if old_tone == new_tone:
            observations.append(
                {
                    "relative_symbol": relative_symbol,
                    "old_tone": int(old_tone),
                    "new_tone": int(new_tone),
                    "status": "uninformative_same_tone",
                    "retained": False,
                }
            )
            continue
        nominal_boundary = (
            nominal_prologue_start + relative_symbol * symbol_samples
        )
        old_frequency = center_hz + (old_tone - 7.5) * symbol_rate
        new_frequency = center_hz + (new_tone - 7.5) * symbol_rate
        crossing = _tone_crossover(
            samples,
            input_start=input_start,
            nominal_boundary=nominal_boundary,
            sample_rate=sample_rate,
            old_frequency_hz=old_frequency,
            new_frequency_hz=new_frequency,
            window_samples=window_samples,
            radius_samples=radius_samples,
        )
        if crossing is None:
            observations.append(
                {
                    "relative_symbol": relative_symbol,
                    "nominal_boundary_input_sample": float(nominal_boundary),
                    "old_tone": int(old_tone),
                    "new_tone": int(new_tone),
                    "frequency_step_hz": float(
                        abs(new_frequency - old_frequency)
                    ),
                    "status": "rejected_no_crossover",
                    "retained": False,
                }
            )
            continue
        base_weight = float((new_tone - old_tone) ** 2)
        lattice.append(relative_symbol)
        crossings.append(crossing)
        weights.append(base_weight)
        observations.append(
            {
                "relative_symbol": relative_symbol,
                "nominal_boundary_input_sample": float(nominal_boundary),
                "crossover_input_sample": float(crossing),
                "old_tone": int(old_tone),
                "new_tone": int(new_tone),
                "frequency_step_hz": float(abs(new_frequency - old_frequency)),
                "base_weight": base_weight,
                "status": "measured",
            }
        )
    if len(crossings) < 6:
        return {
            "status": "insufficient_crossovers",
            "emitted_flush_symbol_count": len(tones),
            "informative_transition_count": len(crossings),
            "observations": observations,
            "operative": False,
        }
    x = np.asarray(lattice, dtype=np.float64)
    y = np.asarray(crossings, dtype=np.float64)
    base_weights = np.asarray(weights, dtype=np.float64)
    design = np.column_stack((np.ones(len(x)), x))
    fit_weights = base_weights.copy()
    coefficients = np.zeros(2)
    scale = 1.0
    for _ in range(6):
        root = np.sqrt(np.maximum(fit_weights, np.finfo(np.float64).tiny))
        coefficients = np.linalg.lstsq(
            design * root[:, None], y * root, rcond=None
        )[0]
        residuals = y - design @ coefficients
        median = float(np.median(residuals))
        scale = max(
            0.25,
            1.4826 * float(np.median(np.abs(residuals - median))),
        )
        huber = np.minimum(
            1.0,
            2.5 * scale
            / np.maximum(np.abs(residuals - median), 1e-12),
        )
        fit_weights = base_weights * huber
    residuals = y - design @ coefficients
    normal = design.T @ (fit_weights[:, None] * design)
    degrees = max(1, len(y) - 2)
    weighted_variance = float(
        np.sum(fit_weights * np.square(residuals))
        / max(np.sum(fit_weights), np.finfo(np.float64).tiny)
    )
    covariance = np.linalg.pinv(normal) * weighted_variance * (
        np.sum(fit_weights) / degrees
    )
    prologue_start, tracked_symbol_samples = map(float, coefficients)
    measured_observations = [
        observation
        for observation in observations
        if observation["status"] == "measured"
    ]
    for observation, base_weight, robust_weight in zip(
        measured_observations, base_weights, fit_weights
    ):
        predicted = float(
            prologue_start
            + observation["relative_symbol"] * tracked_symbol_samples
        )
        observation.update(
            {
                "predicted_input_sample": predicted,
                "residual_input_samples": float(
                    observation["crossover_input_sample"] - predicted
                ),
                "robust_weight": float(robust_weight),
                "robust_factor": float(robust_weight / max(base_weight, 1e-12)),
                "status": "retained",
                "retained": True,
            }
        )
    rate_scale = tracked_symbol_samples / symbol_samples
    raster_start = prologue_start + prologue_count * rate_scale
    raster_vector = np.asarray(
        [1.0, prologue_count / symbol_samples], dtype=np.float64
    )
    raster_variance = float(raster_vector @ covariance @ raster_vector)
    return {
        "status": "estimated",
        "source": "known_flush_transition_crossover_fit",
        "emitted_flush_symbol_count": len(tones),
        "informative_transition_count": len(crossings),
        "predicted_prologue_start_input_sample_fractional": prologue_start,
        "predicted_first_raster_input_sample_fractional": raster_start,
        "tracked_samples_per_symbol": tracked_symbol_samples,
        "estimated_rate_error_ppm": (rate_scale - 1.0) * 1e6,
        "prologue_uncertainty_input_samples": max(
            0.25, float(np.sqrt(max(0.0, covariance[0, 0])))
        ),
        "raster_uncertainty_input_samples": max(
            0.25, float(np.sqrt(max(0.0, raster_variance)))
        ),
        "residual_sigma_input_samples": max(
            0.25, float(np.sqrt(max(0.0, weighted_variance)))
        ),
        "parameter_covariance": covariance.tolist(),
        "observations": observations,
        "operative": False,
    }


def _fit_unified_boundary_grid(
    *,
    mode: str,
    sample_rate: float,
    prologue_count: int,
    protocol_prediction: dict[str, Any],
    symbol_clock: ClockTrack | None,
    symbol_clock_covariance: tuple[
        tuple[float, float], tuple[float, float]
    ] | None,
    transition_clock_evidence: dict[str, Any] | None,
    flush_grid_prediction: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fit one picture-local grid from global text and header-flush evidence.

    Parameters are expressed at the prologue boundary: its fractional input
    coordinate and the tracked symbol period.  The text-derived affine clock
    supplies a joint prior on those parameters.  Every measurable transition
    in the exactly reconstructed header flush updates that same fit.  Missing
    local evidence therefore increases conditional variance instead of
    selecting a different boundary estimator.
    """
    symbol_rate = 62.5 if mode == "MFSK64" else 31.25
    nominal_symbol_samples = sample_rate / symbol_rate
    prologue_symbol = protocol_prediction.get("prologue_symbol_index")
    global_mean: np.ndarray | None = None
    global_covariance: np.ndarray | None = None
    if (
        symbol_clock is not None
        and symbol_clock_covariance is not None
        and prologue_symbol is not None
    ):
        clock_covariance = np.asarray(
            symbol_clock_covariance, dtype=np.float64
        )
        if clock_covariance.shape == (2, 2) and np.isfinite(
            clock_covariance
        ).all():
            prologue_symbol_float = float(prologue_symbol)
            transform = np.asarray(
                [[1.0, prologue_symbol_float], [0.0, 1.0]],
                dtype=np.float64,
            )
            global_mean = np.asarray(
                [
                    symbol_clock.epoch_input_sample
                    + prologue_symbol_float
                    * symbol_clock.tracked_samples_per_symbol,
                    symbol_clock.tracked_samples_per_symbol,
                ],
                dtype=np.float64,
            )
            global_covariance = transform @ clock_covariance @ transform.T
            global_covariance = 0.5 * (
                global_covariance + global_covariance.T
            )
            eigenvalues, eigenvectors = np.linalg.eigh(global_covariance)
            eigenvalues = np.maximum(eigenvalues, 1e-8)
            global_covariance = (
                eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
            )
            if global_covariance[0, 0] < 0.25**2:
                global_covariance[0, 0] += 0.25**2 - global_covariance[0, 0]

    flush_observations = [
        dict(observation)
        for observation in (
            flush_grid_prediction.get("observations", [])
            if flush_grid_prediction is not None
            else []
        )
    ]
    local_observations = [
        observation
        for observation in flush_observations
        if observation.get("crossover_input_sample") is not None
        and observation.get("base_weight") is not None
    ]
    local_x = np.asarray(
        [observation["relative_symbol"] for observation in local_observations],
        dtype=np.float64,
    )
    local_y = np.asarray(
        [
            observation["crossover_input_sample"]
            for observation in local_observations
        ],
        dtype=np.float64,
    )
    local_base_weights = np.asarray(
        [observation["base_weight"] for observation in local_observations],
        dtype=np.float64,
    )
    if len(local_base_weights):
        positive = local_base_weights[local_base_weights > 0.0]
        normalization = float(np.median(positive)) if len(positive) else 1.0
        local_base_weights = local_base_weights / max(normalization, 1e-12)
    local_design = np.column_stack(
        (np.ones(len(local_x), dtype=np.float64), local_x)
    )

    if global_mean is None and len(local_x) < 2:
        return {
            "status": "insufficient_evidence",
            "source": "unified_global_text_local_header_flush_grid",
            "conditional_evidence": "none",
            "text_transition_observations": (
                transition_clock_evidence.get("observations", [])
                if transition_clock_evidence
                else []
            ),
            "header_flush_observations": flush_observations,
            "operative": False,
        }

    prior_precision = np.zeros((2, 2), dtype=np.float64)
    prior_rhs = np.zeros(2, dtype=np.float64)
    if global_mean is not None and global_covariance is not None:
        prior_precision = np.linalg.pinv(global_covariance)
        prior_rhs = prior_precision @ global_mean
        coefficients = global_mean.copy()
    else:
        coefficients = np.linalg.lstsq(
            local_design
            * np.sqrt(np.maximum(local_base_weights, 1e-12))[:, None],
            local_y * np.sqrt(np.maximum(local_base_weights, 1e-12)),
            rcond=None,
        )[0]

    local_robust_weights = np.zeros(len(local_x), dtype=np.float64)
    local_scale = max(
        0.25,
        float(
            (flush_grid_prediction or {}).get(
                "residual_sigma_input_samples", 0.25
            )
        ),
    )
    for _ in range(8):
        if len(local_x):
            residuals = local_y - local_design @ coefficients
            residual_center = float(np.median(residuals))
            local_scale = max(
                0.25,
                1.4826
                * float(np.median(np.abs(residuals - residual_center))),
            )
            huber = np.minimum(
                1.0,
                2.5
                * local_scale
                / np.maximum(
                    np.abs(residuals - residual_center), 1e-12
                ),
            )
            local_robust_weights = (
                local_base_weights * huber / (local_scale * local_scale)
            )
            normal = (
                prior_precision
                + local_design.T
                @ (local_robust_weights[:, None] * local_design)
            )
            rhs = (
                prior_rhs
                + local_design.T @ (local_robust_weights * local_y)
            )
        else:
            normal = prior_precision
            rhs = prior_rhs
        if np.linalg.matrix_rank(normal) < 2:
            return {
                "status": "singular_evidence",
                "source": "unified_global_text_local_header_flush_grid",
                "conditional_evidence": "local_flush_only",
                "header_flush_observations": flush_observations,
                "operative": False,
            }
        coefficients = np.linalg.solve(normal, rhs)

    posterior_covariance = np.linalg.pinv(normal)
    prologue_start, tracked_symbol_samples = map(float, coefficients)
    raster_vector = np.asarray(
        [1.0, prologue_count / nominal_symbol_samples], dtype=np.float64
    )
    raster_start = float(raster_vector @ coefficients)
    raster_variance = float(
        raster_vector @ posterior_covariance @ raster_vector
    )
    for observation, normalized_base_weight, robust_weight in zip(
        local_observations, local_base_weights, local_robust_weights
    ):
        predicted = float(
            prologue_start
            + observation["relative_symbol"] * tracked_symbol_samples
        )
        observation.update(
            {
                "unified_predicted_input_sample": predicted,
                "unified_residual_input_samples": float(
                    observation["crossover_input_sample"] - predicted
                ),
                "normalized_base_weight": float(normalized_base_weight),
                "unified_robust_weight": float(robust_weight),
                "unified_retained": bool(robust_weight > 0.0),
            }
        )
    if global_mean is not None:
        conditional_evidence = (
            "global_text_and_local_header_flush"
            if len(local_x)
            else "global_text_only"
        )
    else:
        conditional_evidence = "local_header_flush_only"
    return {
        "status": "estimated",
        "source": "unified_global_text_local_header_flush_grid",
        "conditional_evidence": conditional_evidence,
        "nominal_symbol_samples": nominal_symbol_samples,
        "tracked_symbol_samples": tracked_symbol_samples,
        "estimated_rate_error_ppm": (
            tracked_symbol_samples / nominal_symbol_samples - 1.0
        )
        * 1e6,
        "predicted_prologue_start_input_sample_fractional": prologue_start,
        "predicted_first_raster_input_sample_fractional": raster_start,
        "prologue_uncertainty_input_samples": max(
            0.25, float(np.sqrt(max(0.0, posterior_covariance[0, 0])))
        ),
        "raster_uncertainty_input_samples": max(
            0.25, float(np.sqrt(max(0.0, raster_variance)))
        ),
        "local_residual_sigma_input_samples": local_scale,
        "parameter_covariance": posterior_covariance.tolist(),
        "global_prior": (
            {
                "prologue_start_input_sample_fractional": float(global_mean[0]),
                "tracked_symbol_samples": float(global_mean[1]),
                "parameter_covariance": global_covariance.tolist(),
                "posterior_innovation": (
                    coefficients - global_mean
                ).tolist(),
            }
            if global_mean is not None and global_covariance is not None
            else None
        ),
        "text_transition_observations": (
            transition_clock_evidence.get("observations", [])
            if transition_clock_evidence
            else []
        ),
        "header_flush_observations": flush_observations,
        "uncertainty_calibrated": False,
        "operative": True,
    }


def _locate_protocol_change(
    samples: np.ndarray,
    *,
    predicted_raster: int,
    sample_rate: float,
    mode: str,
    prologue_count: int,
    expected_frequency: float,
    center_hz: float,
    bandwidth_hz: float,
    component_samples: int,
    component_count: int,
) -> tuple[int, float, float, list[dict[str, Any]]]:
    """Refine a protocol boundary with competing modulation models.

    The pre-boundary samples are fitted as one constant tone.  The following
    samples are fitted both as that same constant tone and as independently
    valued picture components.  The score rewards the point where the latter
    becomes the better model.  This is an explicitly experimental Session 10F
    path; the legacy selector remains the default.
    """
    if mode == "MFSK64":
        symbol_rate = 62.5
    elif mode == "MFSK32":
        symbol_rate = 31.25
    else:
        raise ValueError(f"unsupported MFSK picture mode: {mode}")
    symbol_samples = sample_rate / symbol_rate
    radius = max(component_samples, int(np.ceil(symbol_samples / 2.0)))
    # This detector is diagnostic-only once the protocol grid is available.
    # A short post-boundary span and coarse-to-fine search are enough to expose
    # modulation materially before that grid without multiplying work by every
    # sample in the half-symbol search interval.
    post_count = min(component_count, 24)
    post_samples = post_count * component_samples
    pre_samples = min(prologue_count, int(round(symbol_samples)))
    first = max(pre_samples, predicted_raster - radius)
    last = min(
        len(samples) - post_samples - 1,
        predicted_raster + radius,
    )
    if last <= first or post_count <= 0:
        raise ValueError("insufficient IQ context for protocol picture boundary")

    half_band = bandwidth_hz * 0.51

    def evaluate(candidate_values: np.ndarray) -> tuple[np.ndarray, ...]:
        candidate_scores = np.empty(len(candidate_values), dtype=np.float64)
        candidate_pre = np.empty(len(candidate_values), dtype=np.float64)
        candidate_components = np.empty(len(candidate_values), dtype=np.float64)
        candidate_constant = np.empty(len(candidate_values), dtype=np.float64)
        candidate_prologue = np.empty(len(candidate_values), dtype=np.float64)
        for index, candidate_value in enumerate(candidate_values):
            candidate = int(candidate_value)
            pre = samples[candidate - pre_samples : candidate]
            prologue_frequency = _phase_advance_frequency(pre, sample_rate)
            pre_residual = _tone_fit_residual(
                pre, sample_rate, prologue_frequency
            )
            expected_penalty = min(
                1.0,
                abs(prologue_frequency - expected_frequency)
                / max(1.0, bandwidth_hz),
            )
            post = samples[candidate : candidate + post_samples]
            constant_residual = _tone_fit_residual(
                post, sample_rate, prologue_frequency
            )
            blocks = post.reshape(post_count, component_samples)
            block_residual = 0.0
            out_of_band = 0.0
            for block in blocks:
                block_frequency = _phase_advance_frequency(block, sample_rate)
                block_residual += _tone_fit_residual(
                    block, sample_rate, block_frequency
                )
                out_of_band += max(
                    0.0, abs(block_frequency - center_hz) - half_band
                ) / max(1.0, bandwidth_hz)
            component_residual = (block_residual + out_of_band) / post_count
            position_penalty = (
                0.002
                * abs(candidate - predicted_raster)
                / max(1, radius)
            )
            candidate_prologue[index] = prologue_frequency
            candidate_pre[index] = pre_residual
            candidate_components[index] = component_residual
            candidate_constant[index] = constant_residual
            candidate_scores[index] = (
                pre_residual
                + 0.05 * expected_penalty
                + component_residual
                - constant_residual
                + position_penalty
            )
        return (
            candidate_scores,
            candidate_pre,
            candidate_components,
            candidate_constant,
            candidate_prologue,
        )

    coarse_step = max(1, component_samples // 2)
    coarse_candidates = np.arange(
        first, last + 1, coarse_step, dtype=np.int64
    )
    if not len(coarse_candidates) or coarse_candidates[-1] != last:
        coarse_candidates = np.append(coarse_candidates, last)
    coarse_scores, *_ = evaluate(coarse_candidates)
    coarse_minima = _separated_score_minima(
        coarse_candidates,
        coarse_scores,
        separation=max(2, component_samples),
    )[:4]
    fine_candidates = np.unique(
        np.concatenate(
            [
                np.arange(
                    max(first, int(coarse_candidates[item]) - coarse_step),
                    min(last, int(coarse_candidates[item]) + coarse_step) + 1,
                    dtype=np.int64,
                )
                for item in coarse_minima
            ]
        )
    )
    (
        scores,
        pre_residuals,
        component_residuals,
        constant_residuals,
        measured_prologue,
    ) = evaluate(fine_candidates)
    candidates = fine_candidates

    best = int(np.argmin(scores))
    separated = _separated_score_minima(
        candidates, scores, separation=max(2, component_samples)
    )[:4]
    alternatives = []
    for rank, item in enumerate(separated, 1):
        alternatives.append(
            {
                "rank": rank,
                "first_raster_input_sample": int(candidates[item]),
                "score": float(scores[item]),
                "constant_tone_residual": float(pre_residuals[item]),
                "component_process_residual": float(
                    component_residuals[item]
                ),
                "following_constant_tone_residual": float(
                    constant_residuals[item]
                ),
                "measured_prologue_frequency_hz": float(
                    measured_prologue[item]
                ),
                "offset_from_protocol_prediction_input_samples": int(
                    candidates[item] - predicted_raster
                ),
                "selected": int(item) == best,
            }
        )
    return (
        int(candidates[best]),
        float(measured_prologue[best]),
        float(scores[best]),
        alternatives,
    )


def _phase_advance_frequency(samples: np.ndarray, sample_rate: float) -> float:
    if len(samples) < 2:
        return 0.0
    products = samples[1:] * np.conj(samples[:-1])
    return float(np.angle(np.sum(products)) * sample_rate / (2.0 * np.pi))


def _tone_fit_residual(
    samples: np.ndarray, sample_rate: float, frequency_hz: float
) -> float:
    if len(samples) < 2:
        return 1.0
    time = np.arange(len(samples), dtype=np.float64) / sample_rate
    oscillator = np.exp(2j * np.pi * frequency_hz * time)
    energy = float(np.vdot(samples, samples).real)
    if energy <= np.finfo(np.float64).tiny:
        return 1.0
    projection = abs(np.vdot(oscillator, samples)) ** 2
    return float(np.clip(1.0 - projection / (len(samples) * energy), 0.0, 1.0))


def _separated_score_minima(
    candidates: np.ndarray, scores: np.ndarray, *, separation: int
) -> list[int]:
    local = [
        index
        for index in range(len(scores))
        if (index == 0 or scores[index] <= scores[index - 1])
        and (index == len(scores) - 1 or scores[index] <= scores[index + 1])
    ]
    ranked = sorted(local, key=lambda index: (scores[index], candidates[index]))
    selected: list[int] = []
    for index in ranked:
        if all(
            abs(int(candidates[index]) - int(candidates[other])) >= separation
            for other in selected
        ):
            selected.append(index)
    if not selected:
        selected.append(int(np.argmin(scores)))
    return selected


def _picture_end_alternatives(
    input_start: int, raster_stop: int, clock: ComponentClock
) -> list[dict[str, Any]]:
    uncertainty = max(1, int(np.ceil(clock.uncertainty_samples)))
    return [
        {
            "rank": rank,
            "input_sample": input_start + raster_stop + offset,
            "offset_input_samples": offset,
            "selected": offset == 0,
            "source": "component_count_and_fractional_clock",
        }
        for rank, offset in enumerate((0, -uncertainty, uncertainty), 1)
    ]


def _fractional_component_frequencies(
    samples: np.ndarray,
    count: int,
    sample_rate: float,
    *,
    component_clock: ComponentClock,
    center_hz: float | None = None,
    bandwidth_hz: float = 937.5,
    estimator: str = "fft_peak",
    component_window: str = "center_crop",
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int]]]:
    """Measure components on rounded affine boundaries without clock drift."""
    intervals = [component_clock.interval(index) for index in range(count)]
    if intervals and len({stop - start for start, stop in intervals}) == 1:
        width = intervals[0][1] - intervals[0][0]
        estimates, quality = _component_frequencies(
            samples,
            intervals[0][0],
            count,
            width,
            sample_rate,
            center_hz=center_hz,
            bandwidth_hz=bandwidth_hz,
            estimator=estimator,
            component_window=component_window,
        )
        return estimates, quality, intervals
    estimates = np.empty(count, dtype=np.float64)
    quality = np.empty(count, dtype=np.float64)
    first = 0
    while first < count:
        run_start, run_first_stop = intervals[first]
        width = run_first_stop - run_start
        run_stop = first + 1
        while (
            run_stop < count
            and intervals[run_stop][0] == intervals[run_stop - 1][1]
            and intervals[run_stop][1] - intervals[run_stop][0] == width
        ):
            run_stop += 1
        run_estimates, run_quality = _component_frequencies(
            samples,
            run_start,
            run_stop - first,
            width,
            sample_rate,
            center_hz=center_hz,
            bandwidth_hz=bandwidth_hz,
            estimator=estimator,
            component_window=component_window,
        )
        estimates[first:run_stop] = run_estimates
        quality[first:run_stop] = run_quality
        first = run_stop
    return estimates, quality, intervals


def _component_frequencies(
    samples: np.ndarray,
    start: int,
    count: int,
    samples_per_component: int,
    sample_rate: float,
    center_hz: float | None = None,
    bandwidth_hz: float = 937.5,
    estimator: str = "fft_peak",
    component_window: str = "center_crop",
) -> tuple[np.ndarray, np.ndarray]:
    if count <= 0:
        return np.empty(0), np.empty(0)
    blocks = samples[
        start : start + count * samples_per_component
    ].reshape(count, samples_per_component)
    if component_window not in {
        "center_crop", "full", "full_hann", "trim_1", "trim_2", "trim_4"
    }:
        raise ValueError(f"unsupported picture component window: {component_window}")
    if component_window == "center_crop" or component_window.startswith("trim_"):
        margin = (
            max(1, samples_per_component // 6)
            if component_window == "center_crop"
            else int(component_window.removeprefix("trim_"))
        )
        core = (
            blocks[:, margin:-margin]
            if samples_per_component > 2 * margin
            else blocks
        )
        measurement_weights = np.ones(core.shape[1], dtype=np.float32)
    else:
        core = blocks
        measurement_weights = (
            np.hanning(core.shape[1]).astype(np.float32)
            if component_window == "full_hann"
            else np.ones(core.shape[1], dtype=np.float32)
        )
    if estimator not in {"fft_peak", "phase_difference", "bounded_correlation"}:
        raise ValueError(f"unsupported picture component estimator: {estimator}")
    if center_hz is None or estimator == "phase_difference":
        products = core[:, 1:] * np.conj(core[:, :-1])
        products = products * measurement_weights[1:]
        sums = np.sum(products, axis=1)
        estimates = np.angle(sums) * sample_rate / (2.0 * np.pi)
        coherence = np.abs(sums) / np.maximum(
            np.sum(np.abs(products), axis=1), np.finfo(np.float32).tiny
        )
        quality = (1.0 - np.clip(coherence, 0.0, 1.0)) * sample_rate / (2.0 * np.pi)
        return estimates, quality
    if estimator == "bounded_correlation":
        # Estimate the phase advance by fitting the complex samples to a
        # bounded bank of tones.  The fine grid is deliberately limited to
        # the picture band; chunks keep the temporary correlation matrix
        # independent of raster size.
        step_hz = bandwidth_hz / (256.0 * 4.0)
        frequencies = np.arange(
            center_hz - bandwidth_hz * 0.505,
            center_hz + bandwidth_hz * 0.505 + step_hz / 2.0,
            step_hz,
            dtype=np.float64,
        )
        time = np.arange(core.shape[1], dtype=np.float64) / sample_rate
        oscillators = np.exp(-2j * np.pi * frequencies[:, None] * time)
        estimates = np.empty(count, dtype=np.float64)
        quality = np.empty(count, dtype=np.float64)
        for first in range(0, count, 1024):
            stop = min(count, first + 1024)
            scores = np.abs(
                (core[first:stop] * measurement_weights) @ oscillators.T
            ) ** 2
            winners = np.argmax(scores, axis=1)
            row = np.arange(stop - first)
            left_index = np.maximum(0, winners - 1)
            right_index = np.minimum(scores.shape[1] - 1, winners + 1)
            left = scores[row, left_index]
            middle = scores[row, winners]
            right = scores[row, right_index]
            denominator = left - 2.0 * middle + right
            delta = np.divide(
                0.5 * (left - right),
                denominator,
                out=np.zeros_like(middle),
                where=np.abs(denominator) > np.finfo(np.float64).tiny,
            )
            estimates[first:stop] = frequencies[winners] + np.clip(
                delta, -0.5, 0.5
            ) * step_hz
            ordered = np.partition(scores, -2, axis=1)
            peak = ordered[:, -1]
            runner_up = ordered[:, -2]
            quality[first:stop] = bandwidth_hz / np.maximum(
                peak / np.maximum(runner_up, np.finfo(np.float64).tiny) - 1.0,
                0.01,
            )
        return estimates, quality
    fft_size = 1024
    bins = np.fft.fftfreq(fft_size, d=1.0 / sample_rate)
    mask = np.flatnonzero(
        (bins >= center_hz - bandwidth_hz * 0.65)
        & (bins <= center_hz + bandwidth_hz * 0.65)
    )
    window = np.hanning(core.shape[1]).astype(np.float32) * measurement_weights
    estimates = np.empty(count, dtype=np.float64)
    quality = np.empty(count, dtype=np.float64)
    for first in range(0, count, 4096):
        stop = min(count, first + 4096)
        spectra = np.abs(
            np.fft.fft(core[first:stop] * window, n=fft_size, axis=1)
        )[:, mask]
        winners = np.argmax(spectra, axis=1)
        peak_bins = mask[winners]
        row = np.arange(stop - first)
        left_index = np.maximum(0, winners - 1)
        right_index = np.minimum(spectra.shape[1] - 1, winners + 1)
        left = spectra[row, left_index]
        middle = spectra[row, winners]
        right = spectra[row, right_index]
        denominator = left - 2.0 * middle + right
        delta = np.divide(
            0.5 * (left - right),
            denominator,
            out=np.zeros_like(middle),
            where=np.abs(denominator) > np.finfo(np.float32).tiny,
        )
        estimates[first:stop] = (
            peak_bins + np.clip(delta, -0.5, 0.5)
        ) * (sample_rate / fft_size)
        ordered = np.partition(spectra, -2, axis=1)
        peak = ordered[:, -1]
        runner_up = ordered[:, -2]
        quality[first:stop] = bandwidth_hz / np.maximum(
            peak / np.maximum(runner_up, np.finfo(np.float32).tiny) - 1.0,
            0.01,
        )
    return estimates, quality


def _coherent_frequency(
    samples: np.ndarray, sample_rate: float, expected_frequency: float
) -> tuple[float, float]:
    if len(samples) < 2:
        return expected_frequency, float("inf")
    products = samples[1:] * np.conj(samples[:-1])
    instantaneous = np.angle(products) * sample_rate / (2.0 * np.pi)
    estimate = float(np.median(instantaneous))
    # The mean residual deliberately exposes short contamination at either
    # plateau edge; a median-only score cannot distinguish equal-length
    # shifted windows around a long coherent prologue.
    quality = float(np.mean(np.abs(instantaneous - expected_frequency)))
    return estimate, quality


def _assemble_raster(
    values: np.ndarray, width: int, height: int, color: bool
) -> np.ndarray:
    if not color:
        result = np.zeros((height, width), dtype=np.uint8)
        result.reshape(-1)[: len(values)] = values
        return result
    result = np.zeros((height, width, 3), dtype=np.uint8)
    offset = 0
    for row in range(height):
        for component in range(3):
            available = min(width, len(values) - offset)
            if available > 0:
                result[row, :available, component] = values[offset : offset + available]
            offset += width
    return result
