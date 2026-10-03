"""Measure retained Session 8 PCM independently of production raster code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import py_compile
import sys
import wave

import numpy as np
from PIL import Image
from scipy import signal

from grampy.mfsk_segment_encode import ImageSource, plan_mfsk_segment
from grampy.picture_decode import _component_frequencies, decode_pictures
from grampy.text_decode import decode_mfsk_text


def error_metrics(actual: np.ndarray, expected: np.ndarray) -> dict:
    delta = np.abs(actual.astype(float) - expected.astype(float))
    return {"unequal_components": int(np.count_nonzero(delta)),
            "mae": float(delta.mean()), "max_error": float(delta.max())}


def pcm_model_error(actual: np.ndarray, frequencies: np.ndarray, widths: np.ndarray) -> dict:
    # Two fitted quadratures permit any initial oscillator phase, but every
    # component's subsequent phase advance is fixed by the independent recipe.
    steps = np.repeat(2 * np.pi * frequencies / 48000, widths)
    phase = np.concatenate(([0.0], np.cumsum(steps[:-1])))
    basis = np.column_stack((np.cos(phase), np.sin(phase)))
    coefficients, *_ = np.linalg.lstsq(basis, actual, rcond=None)
    residual = actual - basis @ coefficients
    return {"rms_lsb": float(np.sqrt(np.mean(residual**2))),
            "max_abs_lsb": float(np.max(np.abs(residual))),
            "fitted_amplitude": float(np.linalg.norm(coefficients))}


def main() -> None:
    evidence = Path(sys.argv[1])
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    py_compile.compile("experiments/mfsk-wav-encoder/session9_probe.py", doraise=True)
    rgb = np.asarray(Image.open(evidence / "inputs/primary-color-8x4.png"), dtype=np.uint16)
    gray = ((31 * rgb[:, :, 0] + 61 * rgb[:, :, 1] + 8 * rgb[:, :, 2]) // 100).astype(np.uint8)
    rows = []
    for name in ("rsid-mixed-audio-silence-picture", "mfsk32-grayscale-speeds", "mfsk64-color-speeds"):
        case = evidence / "cases" / name
        composition = json.loads((case / "composition.json").read_text())
        record = json.loads((case / "encoder-result.json").read_text())
        with wave.open(str(case / "generated.wav")) as wav:
            assert wav.getframerate() == 48000 and wav.getnchannels() == 1
            raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(float)
        for index, part in enumerate(composition):
            if part["kind"] != "mfsk" or not any(c["kind"] == "image" for c in part["contents"]):
                continue
            mode = part["mode"]
            carrier = part["carrier_hz"]
            bandwidth = 468.75 if mode == "MFSK32" else 937.5
            frames_per_symbol = 1536 if mode == "MFSK32" else 768
            post_flush_symbols = 54 if mode == "MFSK32" else 90
            prefix_frames = 111450 if mode == "MFSK32" else 222900
            segment_start = record["segments_frames"][index]["start_frame"] + prefix_frames
            contents = [c["utf8"].encode() if c["kind"] == "text" else ImageSource(
                evidence / "inputs/primary-color-8x4.png", c["color"], c["samples_per_pixel"]
            ) for c in part["contents"]]
            plan = plan_mfsk_segment(contents=contents, mode=mode, carrier_hz=carrier, sample_rate_hz=48000)
            analytic = signal.hilbert(raw[segment_start:segment_start + plan.frame_count] / 16384).astype(np.complex64)
            prefix_start = 0
            image_parts = [(i, c) for i, c in enumerate(part["contents"]) if c["kind"] == "image"]
            for transition, (content_index, content) in zip(plan.picture_transitions, image_parts):
                speed = content["samples_per_pixel"]
                truth_raster = rgb.astype(np.uint8) if content["color"] == "color" else gray
                # Derive component order directly from the retained source image.
                wire = rgb.transpose(0, 2, 1).reshape(-1) if content["color"] == "color" else gray.reshape(-1)
                width = speed * 6
                # Derive the raster coordinates from the public next-item start,
                # the frozen post-picture flush, and known component duration.
                after_start = record["segments_frames"][index]["contents"][content_index + 1]["start_frame"]
                raster_start = after_start - post_flush_symbols * frames_per_symbol - len(wire) * width
                assert raster_start == segment_start + transition.raster_start_frame
                count = 2112 + len(wire) * width
                actual = raw[raster_start - 2112:raster_start - 2112 + count]
                frequencies = np.concatenate(([carrier - bandwidth / 2], carrier + bandwidth * (wire.astype(float) - 128) / 256))
                widths = np.concatenate(([2112], np.full(len(wire), width)))
                model = pcm_model_error(actual, frequencies, widths)
                # Deliberate wrong mapping/order/duration must fail this check.
                frequency_mutation = pcm_model_error(actual, frequencies + 20, widths)
                order_mutation = pcm_model_error(actual, np.concatenate((frequencies[:1], frequencies[1:][::-1])), widths)
                changed_widths = widths.copy()
                changed_widths[1] += 1
                changed_widths[-1] -= 1
                timing_mutation = pcm_model_error(actual, frequencies, changed_widths)
                assert model["max_abs_lsb"] < 0.55
                assert all(m["rms_lsb"] > 10 for m in (frequency_mutation, order_mutation, timing_mutation))
                prefix = decode_mfsk_text(analytic[prefix_start:transition.prologue_start_frame],
                    input_start=prefix_start, sample_rate=48000., orientation_hint="normal",
                    trace_level="events", mode=mode, center_hint_hz=carrier)
                decoded = decode_pictures(analytic, input_start=0, sample_rate=48000, mode=mode,
                    orientation="normal", center_hz=carrier, text_events=prefix.text_events)
                picture = decoded.pictures[0]
                frequencies_measured, _ = _component_frequencies(analytic, transition.raster_start_frame,
                    len(wire), width, 48000, center_hz=carrier, bandwidth_hz=bandwidth)
                boundary_values = np.clip(np.rint(128 + 256 * (frequencies_measured - carrier) / bandwidth), 0, 255).astype(np.uint8)
                artifact = next(a for a in decoded.artifacts if "values" in a)
                recovered = np.asarray(artifact["values"], dtype=np.uint8).reshape(artifact["shape"])
                row = {"case": name, "mode": mode, "color": content["color"], "speed": speed,
                    "wav_sha256": hashlib.sha256((case / "generated.wav").read_bytes()).hexdigest(),
                    "raster_start_frame": raster_start, "pcm_model": model,
                    "mutation_rms_lsb": {"frequency": frequency_mutation["rms_lsb"],
                        "order": order_mutation["rms_lsb"], "timing": timing_mutation["rms_lsb"]},
                    "grampy_boundary_error_frames": picture["first_raster_input_sample"] - transition.raster_start_frame,
                    "grampy_default": error_metrics(recovered, truth_raster),
                    "grampy_estimator_at_exact_boundary": error_metrics(boundary_values, wire)}
                rows.append(row)
                print(json.dumps(row), flush=True)
                prefix_start = transition.post_picture_flush_start_frame
    (output / "local-waveform.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
