"""Sparse, read-only reception measurements from stored post-AGC SigMF IQ."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import jsonschema
import numpy as np

from .resources import load_json
from .sigmf import DATATYPES, SigmfRecording


SCHEMA = "grampy-quality-manifest.v1"
METHOD = "sparse-iq-band-power.v1"
FFT_SIZE = 4096
SEARCH_HZ = 125.0
GUARD_HZ = 100.0
SHOULDER_HZ = 500.0
_LN_2 = math.log(2.0)


@dataclass(frozen=True)
class _Bands:
    signal_starts: np.ndarray
    signal_stops: np.ndarray
    noise_bins: np.ndarray


def build_reception_quality_manifest(
    recording: SigmfRecording,
    source: Mapping[str, Any],
    *,
    snapshots_per_second: int = 4,
) -> dict[str, Any]:
    """Publish signal/noise values while decode confidence awaits stage 4.

    ``source`` supplies decode identity and mode/center hints, but its text,
    decoded-symbol confidence, and picture contents never enter measurements.
    """
    if snapshots_per_second not in (1, 2, 4):
        raise ValueError("snapshots_per_second must be 1, 2, or 4")
    source_input = source["input"]
    interval = source_input["requested_interval"]
    if (interval["start"], interval["stop"]) != (
        recording.requested_start, recording.requested_stop
    ) or not math.isclose(source_input["sample_rate_hz"], recording.sample_rate):
        raise ValueError("source and recording intervals or sample rates differ")

    sample_rate = recording.sample_rate
    start, stop = recording.requested_start, recording.requested_stop
    point_count = math.ceil((stop - start) / sample_rate)
    fft_size = min(FFT_SIZE, 1 << int(math.floor(math.log2(sample_rate / 2))))
    if fft_size < 256:
        raise ValueError("sample rate is too low for spectral measurement")
    window = np.hanning(fft_size).astype(np.float32)
    window_scale = fft_size * float(np.sum(window * window))
    frequencies = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0 / sample_rate))
    segments = sorted(source.get("mode_segments", []), key=lambda part: part["interval"]["start"])
    bands: dict[tuple[str, float], _Bands | None] = {}
    dtype, _, scale = DATATYPES[recording.datatype]
    raw = np.memmap(recording.data_path, mode="r", dtype=dtype)

    points: list[list[float | None]] = []
    exceptions: list[dict[str, Any]] = []
    snapshots_read = 0
    for index in range(point_count):
        second_start = start + math.floor(index * sample_rate)
        second_stop = min(stop, start + math.floor((index + 1) * sample_rate))
        midpoint = (second_start + second_stop) // 2
        reference = _nearest_segment(segments, midpoint)
        if reference is None or reference.get("mode") not in ("MFSK32", "MFSK64"):
            points.append([None, None, None])
            exceptions.append({"index": index, "reason": "no_mode_reference"})
            continue
        center = reference.get("center_hz")
        if center is None or not math.isfinite(center):
            points.append([None, None, None])
            exceptions.append({"index": index, "reason": "no_center_reference"})
            continue
        key = (reference["mode"], float(center))
        if key not in bands:
            bands[key] = _bands(frequencies, reference["mode"], float(center))
        selected_bands = bands[key]
        if selected_bands is None:
            points.append([None, None, None])
            exceptions.append({"index": index, "reason": "noise_band_unavailable"})
            continue
        if second_stop - second_start < fft_size:
            points.append([None, None, None])
            exceptions.append({"index": index, "reason": "insufficient_samples"})
            continue

        signal_excesses: list[float] = []
        signal_thresholds: list[float] = []
        noise_powers: list[float] = []
        for snapshot in range(snapshots_per_second):
            center_sample = second_start + int(
                (snapshot + 0.5) * (second_stop - second_start) / snapshots_per_second
            )
            read_start = min(
                max(second_start, center_sample - fft_size // 2), second_stop - fft_size
            )
            pairs = np.asarray(raw[read_start * 2:(read_start + fft_size) * 2]).reshape(-1, 2)
            samples = (pairs[:, 0] + 1j * pairs[:, 1]).astype(np.complex64) / scale
            snapshots_read += 1
            if not np.all(np.isfinite(samples)):
                continue
            spectrum = np.fft.fftshift(np.fft.fft(samples * window))
            power = np.abs(spectrum) ** 2 / window_scale
            noise_density = float(np.median(power[selected_bands.noise_bins])) / _LN_2
            if not math.isfinite(noise_density) or noise_density <= 0:
                continue
            cumulative = np.concatenate(([0.0], np.cumsum(power)))
            band_bins = selected_bands.signal_stops - selected_bands.signal_starts
            band_power = (
                cumulative[selected_bands.signal_stops]
                - cumulative[selected_bands.signal_starts]
            )
            excess = band_power - noise_density * band_bins
            best = int(np.argmax(excess))
            matched_noise = noise_density * int(band_bins[best])
            noise_powers.append(matched_noise)
            # A positive excess alone is common in noise; require a broad-band
            # deviation beyond periodogram variation before claiming a signal.
            threshold = 4.0 * noise_density * math.sqrt(int(band_bins[best]))
            signal_excesses.append(float(excess[best]))
            signal_thresholds.append(threshold)

        signal = None
        if signal_excesses:
            median_excess = float(np.median(signal_excesses))
            if median_excess > float(np.median(signal_thresholds)):
                signal = _dbfs(median_excess)
        noise = _dbfs(float(np.median(noise_powers))) if noise_powers else None
        points.append([signal, noise, None])
        if noise is None:
            exceptions.append({"index": index, "reason": "invalid_spectrum"})

    document = {
        "schema": SCHEMA,
        "run_id": source["run_id"],
        "status": "partial",
        "decoder": {
            "version": source["decoder"]["version"],
            "configuration": dict(source["decoder"]["configuration"]),
        },
        "input": {
            "metadata_sha256": source_input["metadata_sha256"],
            "data_sha256": source_input["data_sha256"],
            "sample_rate_hz": sample_rate,
            "requested_interval": dict(interval),
        },
        "grid": {
            "origin_sample": start,
            "interval_seconds": 1,
            "point_count": point_count,
        },
        "columns": ["signal_dbfs", "noise_dbfs", "decode_confidence"],
        "points": points,
        "methods": {
            "signal_noise": {
                "id": METHOD,
                "calibrated_rf_power": False,
                "fft_size": fft_size,
                "window": "hann",
                "snapshots_per_second": snapshots_per_second,
                "aggregation": "median_linear_power",
                "center_search_hz": SEARCH_HZ,
                "guard_hz": GUARD_HZ,
                "noise_shoulder_hz": SHOULDER_HZ,
                "signal_band_hz": {"MFSK32": 531.25, "MFSK64": 1062.5},
                "noise_estimator": "median_periodogram_divided_by_ln2",
                "logical_iq_bytes_read": snapshots_read * fft_size * recording.bytes_per_sample,
            },
            "decode_confidence": {
                "id": "pending-stage-4",
                "calibrated_error_probability": False,
            },
        },
        "exceptions": exceptions,
        "warnings": [{
            "code": "decode-confidence-pending",
            "message": "decode confidence will be populated in stage 4",
        }],
    }
    jsonschema.Draft202012Validator(
        load_json("schemas", "grampy-quality-manifest-v1.json")
    ).validate(document)
    return document


def _nearest_segment(
    segments: Sequence[Mapping[str, Any]], sample: int
) -> Mapping[str, Any] | None:
    if not segments:
        return None
    return min(
        segments,
        key=lambda part: max(
            part["interval"]["start"] - sample,
            sample - part["interval"]["stop"],
            0,
        ),
    )


def _bands(frequencies: np.ndarray, mode: str, center: float) -> _Bands | None:
    spacing = 31.25 if mode == "MFSK32" else 62.5
    halfwidth = 8.5 * spacing
    shifts = np.arange(-SEARCH_HZ, SEARCH_HZ + 0.1, spacing / 4)
    if center + shifts[0] - halfwidth < frequencies[0] or center + shifts[-1] + halfwidth > frequencies[-1]:
        return None
    starts = np.searchsorted(frequencies, center + shifts - halfwidth)
    stops = np.searchsorted(frequencies, center + shifts + halfwidth)
    if np.any(starts == stops):
        return None
    outer = halfwidth + SEARCH_HZ + GUARD_HZ
    noise = (
        ((frequencies >= center - outer - SHOULDER_HZ) & (frequencies < center - outer))
        | ((frequencies > center + outer) & (frequencies <= center + outer + SHOULDER_HZ))
    )
    if int(noise.sum()) < 32:
        return None
    return _Bands(starts, stops, np.flatnonzero(noise))


def _dbfs(power: float) -> float | None:
    return round(10.0 * math.log10(power), 3) if power > 0 else None
