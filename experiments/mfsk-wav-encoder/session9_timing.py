"""Fit diagnostic receiver-filter timing to unaligned settled viewer pixels."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import wave

import numpy as np
from PIL import Image
from scipy import signal

from session9_filter_model import receiver_filter


def main():
    root = Path(sys.argv[1])
    output = Path(sys.argv[2])
    spec = importlib.util.spec_from_file_location("fixture_measurement", "tools/analyze-mfsk-color-fixture")
    # The executable has no .py suffix, so use an explicit source loader.
    from importlib.machinery import SourceFileLoader
    module = SourceFileLoader("fixture_measurement", "tools/analyze-mfsk-color-fixture").load_module()
    rgb = np.asarray(Image.open(root / "primary-color-8x4.png"), dtype=np.uint16)
    gray = ((31*rgb[:, :, 0]+61*rgb[:, :, 1]+8*rgb[:, :, 2])//100).reshape(-1)
    results = []
    for row in json.loads((root / "results.json").read_text()):
        case = root / row["case"]
        with wave.open(str(case / "transmission.wav")) as wav:
            raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(float) / 32768
        band = 468.75 if row["mode"] == "MFSK32" else 937.5
        truth = rgb.transpose(0, 2, 1).reshape(-1) if row["color"] == "color" else gray
        expected = 1500 + band * (truth.astype(float)-128)/256
        analytic = signal.hilbert(raw)
        frequency = np.angle(analytic[1:]*np.conj(analytic[:-1])) * 48000 / (2*np.pi)
        raster_start, measured = module.locate_sequence(frequency, expected, 48)
        observed = np.asarray(row["viewer"]["values"], dtype=np.int16).reshape(4, 8, 3)
        observed_wire = observed.transpose(0, 2, 1).reshape(-1) if row["color"] == "color" else observed[:, :, 0].reshape(-1)
        candidates = []
        for phase in range(6):
            interval = raw[raster_start-2112+phase:raster_start+len(truth)*48+6144+phase:6]
            z = receiver_filter(interval, 1500, band)
            f = np.angle(z[1:]*np.conj(z[:-1]))*8000/(2*np.pi)
            for offset in range(-128, 769):
                origin = 352+offset
                estimated = f[origin:origin+(len(truth)-1)*8].reshape(-1, 8).mean(axis=1)
                values = np.clip(256*(estimated-1000)/band, 0, 255).astype(np.uint8)
                # The source stops before emitting component K-1. Ignore the
                # first component too, because prevz/picf are not reset there.
                delta = np.abs(values[1:].astype(float)-observed_wire[1:-1])
                candidates.append((float(delta.mean()), phase, offset, values))
        best = min(candidates, key=lambda candidate: candidate[:3])
        result = {"case": row["case"], "located_raster_start_frame": int(raster_start),
                  "measured_wire_frequency_rmse_hz": float(np.sqrt(np.mean((measured-expected)**2))),
                  "truth_selected_model_fit_to_viewer": {"mae": best[0], "resample_phase": best[1],
                      "offset_internal_samples": best[2], "offset_from_filter_group_delay": best[2]-83,
                      "values": best[3].tolist()},
                  "last_component": {"expected": int(truth[-1]), "viewer": int(observed_wire[-1])}}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k != "truth_selected_model_fit_to_viewer"}, indent=2))
        print({k:v for k,v in result["truth_selected_model_fit_to_viewer"].items() if k != "values"})
    output.write_text(json.dumps(results, indent=2)+"\n")


if __name__ == "__main__":
    main()
