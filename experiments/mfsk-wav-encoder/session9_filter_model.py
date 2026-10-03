"""Source-derived receiver-filter diagnostic, excluding text acquisition/ALSA.

This model is intentionally test-only. It uses fldigi's frozen 37-tap
Hilbert and 127-tap bandpass formulas, including the one-sample delay in
C_FIR_filter::run, and its phase-difference pixel estimator. Truth-selected
offsets are diagnostic lower bounds, not receiver acceptance results.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import wave

import numpy as np
from PIL import Image
from scipy import signal


def taps(length: int, low: float, high: float, hilbert: bool = False) -> np.ndarray:
    time = np.arange(length) - (length - 1) / 2
    window = np.hamming(length)
    if not hilbert:
        return (2 * high * np.sinc(2 * high * time) - 2 * low * np.sinc(2 * low * time)) * window
    def cosc(x):
        return np.divide(1 - np.cos(np.pi * x), np.pi * x, out=np.zeros_like(x), where=np.abs(x) > 1e-10)
    return -(2 * high * cosc(2 * high * time) - 2 * low * cosc(2 * low * time)) * window


def run_filter(values, coefficients):
    return signal.lfilter(np.concatenate(([0.0], coefficients[::-1])), [1.0], values)


def receiver_filter(real, carrier, band):
    analytic = run_filter(real, taps(37, .05, .45)) + 1j * run_filter(real, taps(37, .05, .45, True))
    mixer_hz = carrier - (1000 + band / 2)
    mixed = analytic * np.exp(-2j * np.pi * mixer_hz * np.arange(len(analytic)) / 8000)
    spacing = band / 15
    return run_filter(mixed, taps(127, (1000 - 2 * spacing) / 8000,
                                 (1000 + band + 2 * spacing) / 8000))


def main():
    evidence, measurements, output = map(Path, sys.argv[1:4])
    rows = json.loads(measurements.read_text())
    rgb = np.asarray(Image.open(evidence / "inputs/primary-color-8x4.png"), dtype=np.uint16)
    gray = ((31 * rgb[:, :, 0] + 61 * rgb[:, :, 1] + 8 * rgb[:, :, 2]) // 100).reshape(-1)
    calibration = []
    for band in (468.75, 937.5):
        for value in (0, 128, 255):
            frequency = 1500 + band * (value - 128) / 256
            steady = np.cos(2 * np.pi * frequency * np.arange(8192) / 8000)
            filtered = receiver_filter(steady, 1500, band)
            measured = np.angle(filtered[1:] * np.conj(filtered[:-1])) * 8000 / (2 * np.pi)
            recovered = 256 * (measured[-2048:].mean() - 1000) / band
            assert abs(recovered - value) < 0.01
            calibration.append({"bandwidth_hz": band, "value": value, "recovered": float(recovered)})
    results = []
    for row in rows:
        with wave.open(str(evidence / "cases" / row["case"] / "generated.wav")) as wav:
            real = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(float) / 16384
        # Source WAV rates are integral; this bypasses the live ALSA/resampler
        # to isolate the source-derived modem filters from the transport.
        start = row["raster_start_frame"]
        interval = real[start - 2112:start + 96 * 48 + 2112:6]
        expected = rgb.transpose(0, 2, 1).reshape(-1) if row["color"] == "color" else gray
        band = 468.75 if row["mode"] == "MFSK32" else 937.5
        carrier = 1600 if row["case"] == "rsid-mixed-audio-silence-picture" else 1500
        filtered = receiver_filter(interval, carrier, band)
        advances = np.angle(filtered[1:] * np.conj(filtered[:-1])) * 8000 / (2 * np.pi)
        speed = row["speed"]
        candidates = []
        for offset in range(-128, 257):
            origin = 352 + offset
            freq = advances[origin:origin + len(expected) * speed].reshape(-1, speed).mean(axis=1)
            values = np.clip(256 * (freq - 1000) / band, 0, 255).astype(np.uint8)
            delta = np.abs(values.astype(float) - expected)
            candidates.append((float(delta.mean()), offset, float(delta.max()), values))
        best = min(candidates, key=lambda item: item[:2])
        nominal = next(item for item in candidates if item[1] == 83)
        result = {"case": row["case"], "mode": row["mode"], "speed": speed,
                  "filter_group_delay_internal_samples": 83,
                  "truth_selected_best_offset_internal_samples": best[1],
                  "best_offset_mae": best[0], "best_offset_max_error": best[2],
                  "group_delay_offset_mae": nominal[0], "group_delay_offset_max_error": nominal[2],
                  "group_delay_offset_values": nominal[3].tolist(),
                  "best_offset_values": best[3].tolist()}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if not k.endswith('values')}), flush=True)
    output.write_text(json.dumps({"steady_tone_calibration": calibration, "cases": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
