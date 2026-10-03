"""Representative staged-source Pi check of unchanged whole Session 9 WAVs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import wave

import numpy as np
from scipy.signal import hilbert

from grampy.api import decode_iq_products


def save(path: Path, document: object) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n")


def ordered(text: str, pieces: list[str]) -> bool:
    cursor = 0
    for piece in pieces:
        found = text.find(piece, cursor)
        if found < 0:
            return False
        cursor = found + len(piece)
    return True


def decode(case: dict, wav_root: Path, output: Path) -> None:
    started = time.monotonic()
    directory = output / case["id"]
    directory.mkdir()
    wav_path = wav_root / case["wav"]["path"]
    assert hashlib.sha256(wav_path.read_bytes()).hexdigest() == case["wav"]["sha256"]
    with wave.open(str(wav_path)) as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        rate = wav.getframerate()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
    meta, data = directory / "input.sigmf-meta", directory / "input.sigmf-data"
    hilbert(pcm).astype("<c8").tofile(data)
    save(meta, {"global": {"core:datatype": "cf32_le", "core:sample_rate": rate},
                "captures": [{"core:sample_start": 0}], "annotations": []})
    products = decode_iq_products(meta_path=meta, data_path=data, artifact_dir=directory / "artifacts",
                                 artifact_path_prefix="artifacts", include_diagnostic_manifest=True)
    manifest = products.diagnostic_manifest
    save(directory / "diagnostic.json", manifest)
    save(directory / "text.json", products.text_manifest)
    received = bytes(event["octet"] for event in manifest["text_events"] if event["octet"] is not None).decode("latin1")
    checks = {"whole_input": manifest["input"]["requested_interval"] == {"start": 0, "stop": case["frame_count"]},
              "ordered_text_and_header": ordered(received, case["expected_text_in_order"]),
              "automatic_modes": [segment["mode"] for segment in manifest["mode_segments"]] == case["expected_modes"],
              "complete_framing": manifest["status"] == "complete",
              "complete_picture": len(manifest["pictures"]) == 1 and manifest["pictures"][0]["complete"]}
    pipeline_path = Path(__import__("grampy.pipeline", fromlist=["__file__"]).__file__)
    result = {"id": case["id"], "checks": checks, "pass": all(checks.values()),
              "wav_sha256": case["wav"]["sha256"],
              "pipeline_sha256": hashlib.sha256(pipeline_path.read_bytes()).hexdigest(),
              "elapsed_seconds": time.monotonic() - started,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)}
    save(directory / "result.json", result)
    print(json.dumps(result), flush=True)
    # Keep authoritative WAV hash and decode artifacts, without duplicating IQ.
    data.unlink()
    assert result["pass"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prepared", type=Path)
    parser.add_argument("wav_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case")
    args = parser.parse_args()
    cases = json.loads(args.prepared.read_text())["cases"]
    if args.case:
        decode(next(case for case in cases if case["id"] == args.case), args.wav_root, args.output)
    else:
        args.output.mkdir()
        selected = ["gray32-p8-card", "gray32-p2-chart", "mixed-broadcast-photo"]
        for identifier in selected:
            subprocess.run([sys.executable, __file__, str(args.prepared), str(args.wav_root), str(args.output),
                            "--case", identifier], check=True)
        save(args.output / "summary.json", [json.loads((args.output / identifier / "result.json").read_text())
                                           for identifier in selected])
