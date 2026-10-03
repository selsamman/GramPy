"""Render paired raw autosaves and settled viewer pixels without alignment."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw


def main():
    root = Path(sys.argv[1])
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    rows = json.loads((root / "results.json").read_text())
    rgb = Image.open(root / "primary-color-8x4.png").convert("RGB")
    values = np.asarray(rgb, dtype=np.uint16)
    gray = Image.fromarray(((31*values[:, :, 0]+61*values[:, :, 1]+8*values[:, :, 2])//100).astype(np.uint8)).convert("RGB")
    canvas = Image.new("RGB", (1680, 500), "white")
    draw = ImageDraw.Draw(canvas)
    labels = ("Truth", "Accepted encoder baseline", "Native: settled viewer",
              "Pinned transmitter: settled viewer", "Native: autosaved PNG", "Pinned transmitter: autosaved PNG")
    for col, label in enumerate(labels):
        draw.text((col*280+8, 20), label, fill="black")
    pairs = []
    for index, stem in enumerate(("mfsk32-gray", "mfsk64-color")):
        native = next(row for row in rows if row["case"] == stem + "-native")
        reference = next(row for row in rows if row["case"] == stem + "-fldigi")
        y = 70 + index * 205
        draw.text((8, y), stem + " / p8", fill="black")
        for col, name, artifact in ((0, None, None), (2, native["case"], "viewer.png"),
                                   (3, reference["case"], "viewer.png"),
                                   (4, native["case"], "autosave.png"), (5, reference["case"], "autosave.png")):
            try:
                picture = (gray if stem == "mfsk32-gray" else rgb) if name is None else Image.open(root/name/artifact).convert("RGB")
                if picture.size != (8, 4):
                    draw.text((col*280+8, y+45), f"Saved geometry: {picture.size}", fill="red")
                    continue
                canvas.paste(picture.resize((240, 120), Image.Resampling.NEAREST), (col*280+8, y+25))
            except OSError:
                draw.text((col*280+8, y+45), "Unreadable autosaved PNG", fill="red")
        draw.text((288, y+55), "No accepted encoder output baseline", fill="gray")
        for col, row in ((2, native), (3, reference)):
            score = row["viewer"]
            draw.text((col*280+8, y+150), f"MAE {score['mae']:.3f}; max {score['max_error']}", fill="black")
        native_values = np.array(native["viewer"]["values"], dtype=np.int16)
        reference_values = np.array(reference["viewer"]["values"], dtype=np.int16)
        delta = np.abs(native_values-reference_values)
        pairs.append({"case": stem, "native_source_mae": native["viewer"]["mae"],
                      "reference_source_mae": reference["viewer"]["mae"],
                      "native_vs_reference_mae": float(delta.mean()),
                      "native_vs_reference_max_error": int(delta.max()),
                      "native_autosave_equals_viewer": native["autosave_equals_viewer"],
                      "reference_autosave_equals_viewer": reference["autosave_equals_viewer"]})
    draw.text((8, 480), "Fixed-mode p8 diagnostics; raw coordinates; unchanged pinned receiver. Whole-WAV qualification remains unresolved.", fill="black")
    canvas.save(output / "paired-review.png")
    (output / "paired-comparison.json").write_text(json.dumps(pairs, indent=2) + "\n")
    print(json.dumps(pairs, indent=2))


if __name__ == "__main__":
    main()
