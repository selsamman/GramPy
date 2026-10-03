"""Review original whole-WAV pictures and fit a diagnostic receiver model.

Viewer-selected timing is explanatory only; it is never an acceptance score.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tarfile
import wave

import numpy as np
from PIL import Image, ImageDraw

from session9_filter_model import receiver_filter
from session9_probe import metrics


def main():
    evidence, original, coordinates, output = map(Path, sys.argv[1:5])
    output.mkdir(parents=True, exist_ok=True)
    positions = {(row["case"], row["speed"]): row for row in json.loads(coordinates.read_text())}
    rows = json.loads((evidence / "results.json").read_text())
    source = Image.open(evidence / "primary-color-8x4.png").convert("RGB")
    rgb = np.asarray(source, dtype=np.uint16)
    gray = ((31*rgb[:, :, 0]+61*rgb[:, :, 1]+8*rgb[:, :, 2])//100).astype(np.uint8)
    gray_picture = Image.fromarray(gray).convert("RGB")
    canvas = Image.new("RGB", (1120, 1560), "white")
    draw = ImageDraw.Draw(canvas)
    for col, label in enumerate(("Source", "Session 8 autosave", "Replay autosave", "Replay settled viewer")):
        draw.text((col*280+8, 15), label, fill="black")
    results = []
    for index, row in enumerate(rows):
        name, speed = row["case"], row["speed"]
        case, old = evidence / name, original / "cases" / name
        truth_image = source if row["color"] == "color" else gray_picture
        truth = rgb.transpose(0, 2, 1).reshape(-1) if row["color"] == "color" else gray.reshape(-1)
        viewer_path = case / "work/viewer-captures" / row["capture"]["path"]
        viewer = np.asarray(Image.open(viewer_path).convert("RGB"), dtype=np.int16)
        observed = viewer.transpose(0, 2, 1).reshape(-1) if row["color"] == "color" else viewer[:, :, 0].reshape(-1)
        image_index = (8, 4, 2).index(speed) if "speeds" in name else 0
        new_images = sorted((case / "work/images").glob("*.png"))
        old_images = sorted((old / "received/images").glob("*.png"))
        assert len(new_images) == len(old_images) == (3 if "speeds" in name else 1)
        scored = {}
        y = 50+index*210
        draw.text((8, y), f"{name} / p{speed}", fill="black")
        for col, path in ((0, None), (1, old_images[image_index]), (2, new_images[image_index]), (3, viewer_path)):
            key = ("source", "session8_autosave", "replay_autosave", "viewer")[col]
            try:
                picture = truth_image if path is None else Image.open(path).convert("RGB")
                if picture.size != (8, 4): raise ValueError(f"geometry {picture.size}")
                score = metrics(picture.tobytes(), truth_image.tobytes())
                scored[key] = {k: v for k, v in score.items() if k != "values"}
                canvas.paste(picture.resize((240, 120), Image.Resampling.NEAREST), (col*280+8, y+25))
                draw.text((col*280+8, y+150), f"MAE {score['mae']:.3f}; max {score['max_error']}", fill="black")
            except (OSError, ValueError) as error:
                scored[key] = {"decode_error": str(error)}
                draw.text((col*280+8, y+45), "Unreadable or wrong geometry", fill="red")
        with wave.open(str(old / "generated.wav")) as wav:
            assert wav.getframerate() == 48000
            raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(float)/32768
        coordinate = positions[name, speed]
        start = coordinate["raster_start_frame"]
        band = 468.75 if coordinate["mode"] == "MFSK32" else 937.5
        carrier = 1600 if name == "rsid-mixed-audio-silence-picture" else 1500
        candidates = []
        for phase in range(6):
            interval = raw[start-2112+phase:start+len(truth)*speed*6+6144+phase:6]
            z = receiver_filter(interval, carrier, band)
            frequency = np.angle(z[1:]*np.conj(z[:-1]))*8000/(2*np.pi)
            for offset in range(-128, 769):
                origin = 352+offset
                means = frequency[origin:origin+(len(truth)-1)*speed].reshape(-1, speed).mean(axis=1)
                predicted = np.clip(256*(means-1000)/band, 0, 255).astype(np.uint8)
                delta = np.abs(predicted[1:].astype(float)-observed[1:-1])
                candidates.append((float(delta.mean()), phase, offset, float(delta.max())))
        best = min(candidates)
        result = {"case": name, "speed": speed, "raster_start_frame": start, **scored,
                  "viewer_selected_model_fit": {"interior_mae": best[0], "interior_max_error": best[3],
                      "resample_phase": best[1], "offset_internal_samples": best[2],
                      "offset_from_filter_group_delay": best[2]-83,
                      "excludes_first_and_last_component": True, "acceptance_evidence": False},
                  "last_component": {"expected": int(truth[-1]), "viewer": int(observed[-1])}}
        results.append(result)
        print(json.dumps(result), flush=True)
    # Caller text and picture announcements must still be recovered in order.
    text_results = []
    for name in dict.fromkeys(row["case"] for row in rows):
        case = evidence / name
        with tarfile.open(case / "decode.tar") as archive:
            received = archive.extractfile("./decoded.txt").read().decode("utf-8")
        cursor, expected = 0, []
        for segment in json.loads((case / "composition.json").read_text()):
            if segment["kind"] != "mfsk": continue
            for item in segment["contents"]:
                if item["kind"] == "text":
                    text = item["utf8"]
                else:
                    color_marker = "C" if item["color"] == "color" else ""
                    speed_marker = "" if item["samples_per_pixel"] == 8 else f"p{item['samples_per_pixel']}"
                    text = f"Pic:8x4{color_marker}{speed_marker};"
                location = received.find(text, cursor)
                assert location >= 0, (name, text, received)
                cursor = location+len(text)
                expected.append(text)
        text_results.append({"case": name, "text_and_announcements_in_order": True, "expected": expected})
    draw.text((8, 1535), "Raw coordinates. Sidecar diagnostics; no acceptance threshold changed. Every replay viewer remains unequal to the source.", fill="black")
    canvas.save(output / "wholewav-review.png")
    (output / "wholewav-comparison.json").write_text(json.dumps(results, indent=2)+"\n")
    (output / "wholewav-text.json").write_text(json.dumps(text_results, indent=2)+"\n")


if __name__ == "__main__":
    main()
