"""Measure the repeated gray ramps in the Session 9 160x120 control chart.

This is a waveform timing diagnostic, not an image quality acceptance test.
The source's 24 gray rows each contain three 160-component ramps. At p8,
48 kHz, their nominal reset spacing is 160 * 8 * 6 = 7680 frames.
"""

import argparse
import hashlib
import json
from pathlib import Path
import wave

import numpy as np
from scipy.signal import find_peaks, hilbert


def measure(path):
    with wave.open(str(path)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 48000)
        frames = wav.getnframes()
        samples = np.frombuffer(wav.readframes(frames), dtype="<i2").astype(float)
    analytic = hilbert(samples)
    frequency = np.angle(analytic[1:] * analytic[:-1].conj()) * 48000 / (2 * np.pi)
    smooth = np.convolve(frequency, np.ones(32) / 32, mode="same")
    jumps = smooth[64:] - smooth[:-64]
    peaks, _ = find_peaks(-jumps, height=700, distance=6500)
    best = []
    for start in range(len(peaks)):
        sequence = [int(peaks[start] + 32)]
        for peak in peaks[start + 1:]:
            frame = int(peak + 32)
            if not 7200 < frame - sequence[-1] < 8000:
                break
            sequence.append(frame)
        if len(sequence) > len(best):
            best = sequence
    assert len(best) >= 50, "No sufficiently long control-chart ramp sequence"
    indices = np.arange(len(best))
    slope, intercept = np.polyfit(indices, best, 1)
    residual = np.asarray(best) - (intercept + slope * indices)
    return {
        "wav_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "frames": frames,
        "duration_seconds": frames / 48000,
        "sample_rate_hz": 48000,
        "reset_count": len(best),
        "reset_frames": best,
        "nominal_ramp_interval_frames": 7680,
        "fitted_ramp_interval_frames": float(slope),
        "fitted_frames_per_component": float(slope / 160),
        "time_scale": float(slope / 7680),
        "duration_error_ppm": float((slope / 7680 - 1) * 1e6),
        "fit_residual_max_frames": float(np.max(np.abs(residual))),
        "method": "analytic phase frequency; smoothed ramp resets; linear fit",
        "scope": "p8 MFSK64 160x120 Session 9 chart; waveform timing only",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("wavs", type=Path, nargs="+")
    args = parser.parse_args()
    results = {path.name: measure(path) for path in args.wavs}
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    for name, result in results.items():
        print(name, "reset spacing", round(result["fitted_ramp_interval_frames"], 4),
              "frames; error", round(result["duration_error_ppm"], 2), "ppm")


if __name__ == "__main__":
    main()
