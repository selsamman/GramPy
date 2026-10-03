"""Supplemental decoder evidence; never rewrite frozen Session 9 results.

Run through tools/mac-local.sh with the repository virtualenv.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from PIL import Image

from grampy.api import decode_iq_products

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/mfsk-wav-encoder"))
from session9_broadcast import picture_score, protocol_text, text_in_order


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(candidate: Path, review: Path) -> None:
    original = ROOT / ".local/session9/practical"
    prepared = json.loads((original / "prepared.json").read_text())
    matrix = original / "matrix.json"
    assert digest(matrix) == prepared["matrix"]["sha256"]
    gate = json.loads(matrix.read_text())["picture_gate"]
    review.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in prepared["cases"]:
        old = original / "cases" / case["id"]
        new = candidate / "candidate" / case["id"]
        for identity in (case["truth"], case["wav"]):
            assert digest(original / identity["path"]) == identity["sha256"]
        manifest = json.loads((new / "diagnostic.json").read_text())
        compact = json.loads((new / "text.json").read_text())
        artifacts = {item["id"]: item for item in manifest["artifacts"]}
        rasters = [item for item in artifacts.values() if item["kind"] == "png_uint8_raster"]
        pictures = manifest["pictures"]
        segments = manifest["mode_segments"]
        checks = {
            "whole_input": manifest["input"]["requested_interval"] == {"start": 0, "stop": case["frame_count"]},
            "complete_framing": manifest["status"] == "complete",
            "ordered_caller_text_and_header": text_in_order(protocol_text(manifest), case["expected_text_in_order"]),
            "automatic_modes": [segment["mode"] for segment in segments] == case["expected_modes"],
            "automatic_carriers": len(segments) == len(case["expected_carriers_hz"]) and all(
                abs(segment["center_hz"] - carrier) <= 10
                for segment, carrier in zip(segments, case["expected_carriers_hz"])),
            "one_complete_picture": len(pictures) == len(rasters) == 1 and pictures[0]["complete"],
            "unique_artifact_ids": len(artifacts) == len(manifest["artifacts"]),
            "valid_artifact_hashes": all(digest(new / item["path"]) == item["sha256"] for item in artifacts.values()),
        }
        items = [item for segment in compact["mode_segments"] for item in segment["items"] if item["kind"] == "picture"]
        checks["compact_picture_link"] = len(items) == 1 and items[0]["artifact"] is not None and (
            items[0]["artifact"]["sha256"] == rasters[0]["sha256"])
        assert len(rasters) == 1, case["id"]
        truth = np.asarray(Image.open(old / "truth.png"))
        observed = np.asarray(Image.open(new / rasters[0]["path"]))
        score = picture_score(truth, observed, gate)
        checks["quality_gate"] = score["pass"]
        if case["mode"] == "MFSK64":
            checks["unchanged_mfsk64_pixels"] = np.array_equal(observed, np.asarray(Image.open(old / "grampy.png")))
        row = {"id": case["id"], "mode": case["mode"], "speed": case["speed"], "checks": checks,
               "pass": all(checks.values()), "picture_score": score, "width": case["width"], "height": case["height"],
               "wav_sha256": case["wav"]["sha256"], "truth_sha256": case["truth"]["sha256"],
               "diagnostic_sha256": digest(new / "diagnostic.json"), "candidate_raster_sha256": rasters[0]["sha256"]}
        if case["mode"] == "MFSK32":
            files = {}
            for label, path in (("truth", old / "truth.png"), ("candidate", new / rasters[0]["path"]), ("fldigi", old / "fldigi.png")):
                name = f"{case['id']}-{label}.png"
                shutil.copy(path, review / name)
                files[label] = name
            row["review_images"] = files
        rows.append(row)
        print(f"SCORED {case['id']} pass={row['pass']} rawMAE={score['raw']['whole_raster']['mean_absolute_error_255']:.3f}", flush=True)
    hashes = json.loads((ROOT / ".local/session8/evidence/source/candidate-source-hashes.json").read_text())
    changed = [name for name, expected in hashes.items() if digest(ROOT / name) != expected]
    assert changed == ["src/grampy/pipeline.py"], changed
    record = {"source_changes": changed, "pipeline_sha256": digest(ROOT / changed[0]),
              "frozen_matrix_sha256": digest(matrix), "picture_gate": gate,
              "summary": {"passes": sum(row["pass"] for row in rows), "total": len(rows),
                          "mfsk32_pictures_recovered": 3, "mfsk64_pixel_identical": 7, "pm_visual_status": "pending"},
              "cases": rows}
    save(review / "qualification.json", record)
    sections = []
    for row in rows:
        if "review_images" not in row:
            continue
        figures = []
        for label in ("truth", "baseline", "candidate", "fldigi"):
            captions = {"truth": "Source", "baseline": "Previous automatic decoder", "candidate": "Corrected GramPy automatic decoder", "fldigi": "Pinned Pi fldigi (original run)"}
            content = '<div class="missing">No picture produced</div>' if label == "baseline" else (
                f'<img src="data:image/png;base64,{base64.b64encode((review / row["review_images"][label]).read_bytes()).decode()}" '
                f'alt="{html.escape(captions[label])}">')
            figures.append(f'<figure><figcaption>{captions[label]}</figcaption>{content}</figure>')
        score = row["picture_score"]
        raw = score["raw"]["whole_raster"]["mean_absolute_error_255"]
        aligned = score["alignment"]["aligned_mean_absolute_error_255"]
        sections.append(f'<section><h2>MFSK32 grayscale p{row["speed"]} · {row["width"]}×{row["height"]}</h2>'
                        f'<p>All checks pass. Mean pixel error: {raw:.2f} / 255; after scoring alignment: {aligned:.2f} / 255.</p>'
                        f'<div class="grid">{"".join(figures)}</div></section>')
    (review / "index.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MFSK32 automatic picture correction</title><style>
body{font:16px system-ui;margin:2rem;color:#212b38;background:#f6f8fa}main{max-width:1400px;margin:auto}
section{background:white;padding:1.2rem;margin:1.8rem 0;border-radius:10px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem}
figure{margin:0}figcaption{min-height:3rem;font-weight:600}img{max-width:100%;height:auto;image-rendering:auto}.missing{min-height:180px;background:#edf0f3;display:grid;place-items:center;color:#52606f}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:480px){.grid{grid-template-columns:1fr}}
</style><main><h1>MFSK32 pictures: automatic decoding corrected</h1>
<p>The automatic decoder previously skipped MFSK32 picture decoding. This correction connects its existing picture decoder. These are the same three whole WAVs used in Session 9, with no supplied mode, carrier, or picture timing.</p>
<p>All ten practical cases pass the existing numerical and functional limits. The seven MFSK64 picture rasters are unchanged. Your visual review of the three newly recovered pictures remains pending.</p>
<p>The Pi fldigi column reuses its original reception of these unchanged WAVs. The original Session 9 qualification is retained separately.</p>
''' + "".join(sections) + '<p><a href="qualification.json">Full scorecard and checks</a></p></main></html>')
    assert all(row["pass"] for row in rows)


def received(candidate: Path) -> None:
    source = ROOT / ".local/regression"
    target = candidate / "received-broadcast"
    target.mkdir(parents=True, exist_ok=False)
    old = json.loads((source / "auto.decode.manifest.json").read_text())
    started = time.monotonic()
    products = decode_iq_products(meta_path=source / "capture.sigmf-meta", data_path=source / "capture.sigmf-data",
                                 artifact_dir=target / "artifacts", artifact_path_prefix="artifacts",
                                 include_diagnostic_manifest=True)
    new = products.diagnostic_manifest
    save(target / "diagnostic.json", new)
    save(target / "text.json", products.text_manifest)
    save(target / "quality.json", products.quality_manifest)
    old_rasters = [item for item in old["artifacts"] if item["kind"] == "png_uint8_raster"]
    new_rasters = [item for item in new["artifacts"] if item["kind"] == "png_uint8_raster"]
    checks = {
        "modes_unchanged": [item["mode"] for item in new["mode_segments"]] == [item["mode"] for item in old["mode_segments"]],
        "text_summary_unchanged": new["text_summary"] == old["text_summary"],
        "nine_rasters_identical": len(old_rasters) == len(new_rasters) == 9 and
            [item["sha256"] for item in old_rasters] == [item["sha256"] for item in new_rasters],
        "unique_epoch_ids": len({item["id"] for item in new["text_epochs"]}) == len(new["text_epochs"]),
    }
    record = {"checks": checks, "pass": all(checks.values()), "elapsed_seconds": time.monotonic() - started,
              "baseline_manifest_sha256": digest(source / "auto.decode.manifest.json"),
              "input_metadata_sha256": digest(source / "capture.sigmf-meta"),
              "candidate_pipeline_sha256": digest(ROOT / "src/grampy/pipeline.py")}
    save(candidate / "received-broadcast.json", record)
    print(json.dumps(record), flush=True)
    assert record["pass"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("qualify", "received"))
    parser.add_argument("--candidate", type=Path, default=ROOT / ".local/decoder-auto-mfsk32")
    parser.add_argument("--review", type=Path, default=ROOT / "docs/decoder/data/auto-mfsk32-pictures")
    args = parser.parse_args()
    qualify(args.candidate, args.review) if args.action == "qualify" else received(args.candidate)
