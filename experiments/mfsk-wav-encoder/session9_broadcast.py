"""Versioned practical qualification, using unchanged public encoder/decoder.

Run prepare/decode/evaluate through tools/mac-local.sh. Pi reception is separate
so one managed command is active at a time. Historical qualification is immutable.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tarfile
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy.signal import hilbert

from grampy.api import (AudioPart, ImagePart, MfskSegment, SilencePart, TextPart,
                        decode_iq_products, encode_mfsk_wav)
from grampy.accuracy import (align_component_streams, image_to_wire_components,
                            score_raw_rasters, score_mode_sequence)
from evaluate import prefix_pcm, receiver_events


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def artifact(path: Path, root: Path) -> dict:
    return {"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def check_production(root: Path) -> dict:
    hashes = json.loads((root / ".local/session8/evidence/source/candidate-source-hashes.json").read_text())
    changed = [name for name, digest in hashes.items()
               if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest]
    if changed:
        raise ValueError(f"Production source changed: {changed}")
    return {"unchanged_production_files": len(hashes), "source_hashes": hashes}


def independent_wave_check(pcm: np.ndarray, raster_start: int, raster: np.ndarray,
                           mode: str, speed: int, carrier: float) -> dict:
    # Coordinates from the public *following* item, not picture-estimator truth.
    wire = image_to_wire_components(raster)
    band = 468.75 if mode == "MFSK32" else 937.5
    frequency = np.concatenate(([carrier - band / 2], carrier + band * (wire.astype(float) - 128) / 256))
    widths = np.concatenate(([2112], np.full(len(wire), speed * 6)))
    actual = pcm[raster_start - 2112:raster_start + len(wire) * speed * 6].astype(float)

    def fit(freq: np.ndarray, lengths: np.ndarray) -> dict:
        steps = np.repeat(2 * np.pi * freq / 48000, lengths)
        phase = np.concatenate(([0.0], np.cumsum(steps[:-1])))
        # Only initial phase is unknown. The amplitude is specified, not fitted.
        cosine, sine = np.cos(phase), np.sin(phase)
        basis = np.array([[cosine @ cosine, cosine @ sine], [cosine @ sine, sine @ sine]])
        coeff = np.linalg.solve(basis, np.array([cosine @ actual, sine @ actual]))
        coeff *= 16384 / np.linalg.norm(coeff)
        residual = actual - coeff[0] * cosine - coeff[1] * sine
        return {"rms_pcm_lsb": float(np.sqrt(np.mean(residual ** 2))),
                "max_pcm_lsb": float(np.max(np.abs(residual)))}

    nominal = fit(frequency, widths)
    wrong_frequency = fit(frequency + 20, widths)
    # A frequency mutation demonstrates that the independent check rejects a
    # plausible wrong waveform. Prior Session 9 checks also cover order/time.
    if nominal["max_pcm_lsb"] >= 0.56 or wrong_frequency["rms_pcm_lsb"] <= 10:
        raise ValueError("Independent picture waveform check failed")
    return {"nominal": nominal, "frequency_mutation": wrong_frequency,
            "raster_start_frame": raster_start, "component_count": len(wire)}


def prepare(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "production-identity.json", check_production(root))
    matrix_path = root / "docs/encoder/data/mfsk_encoder_pi_matrix_v3.json"
    matrix = json.loads(matrix_path.read_text())
    shutil.copy(matrix_path, output / "matrix.json")
    inputs = output / "inputs"
    inputs.mkdir()
    sources = {}
    for key, spec in matrix["sources"].items():
        source_path = root / spec["path"]
        with Image.open(source_path) as original:
            picture = original.convert("RGB")
            original_size = list(picture.size)
            if list(picture.size) != spec["output_size"]:
                picture = ImageOps.pad(picture, tuple(spec["output_size"]),
                                       method=Image.Resampling.LANCZOS, color="white")
            picture.save(inputs / f"{key}.png")
        sources[key] = {"original": artifact(source_path, root), "original_size": original_size,
                        "prepared": artifact(inputs / f"{key}.png", output), **spec}
    audio = inputs / "audio-marker.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        t = np.arange(24000) / 48000
        wav.writeframes(np.rint(4000 * np.sin(2 * np.pi * 800 * t)).astype("<i2").tobytes())
    oracle = json.loads((root / "docs/encoder/data/mfsk_encoder_rsid_oracle_v1.json").read_text())
    rows = []
    for spec in matrix["cases"]:
        directory = output / "cases" / spec["id"]
        directory.mkdir(parents=True)
        rgb = np.asarray(Image.open(inputs / f"{spec['source']}.png").convert("RGB"), dtype=np.uint16)
        truth = rgb.astype(np.uint8) if spec["color"] == "color" else (
            (31 * rgb[:, :, 0] + 61 * rgb[:, :, 1] + 8 * rgb[:, :, 2]) // 100).astype(np.uint8)
        Image.fromarray(truth).save(directory / "truth.png")
        width, height = truth.shape[1], truth.shape[0]
        color = "C" if spec["color"] == "color" else ""
        speed = "" if spec["speed"] == 8 else f"p{spec['speed']}"
        label = spec["id"].upper().replace("-", " ")
        opening = f"\x02\nGRAM PY PRACTICAL BROADCAST {label}\n"
        ending = f"\nGRAM PY {label} END\n\x04"
        carrier = 1600.0 if spec.get("mixed") else 1500.0
        image_parts = [TextPart.from_text(opening), ImagePart(inputs / f"{spec['source']}.png",
                        color=spec["color"], samples_per_pixel=spec["speed"]), TextPart.from_text(ending)]
        parts = [MfskSegment(image_parts, mode=spec["mode"], carrier_hz=carrier)]
        expected = [opening, f"Pic:{width}x{height}{color}{speed};", ending]
        modes, carriers = [spec["mode"]], [carrier]
        if spec.get("mixed"):
            intro = "\x02\nGRAM PY BROADCAST MFSK32 NEWS BEGIN\nTODAY WE TEST TEXT AUDIO SILENCE AND A PICTURE.\nNEWS END\n\x04"
            parts = [MfskSegment([TextPart.from_text(intro)], mode="MFSK32", carrier_hz=1400),
                     SilencePart(0.25), AudioPart(audio), SilencePart(0.25)] + parts
            expected = [intro] + expected
            modes, carriers = ["MFSK32", "MFSK64"], [1400, carrier]
        wav_path = directory / "generated.wav"
        started = time.monotonic()
        encoded = encode_mfsk_wav(parts=parts, output_path=wav_path)
        encode_seconds = time.monotonic() - started
        record = dataclasses.asdict(encoded)
        write_json(directory / "encoder-result.json", record)
        with wave.open(str(wav_path)) as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 48000)
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        assert len(pcm) == round(encoded.duration_seconds * 48000)
        assert len(encoded.segments) == len(parts)
        for index, part in enumerate(parts):
            start = round(encoded.segments[index].start_seconds * 48000)
            stop = round(encoded.segments[index + 1].start_seconds * 48000) if index + 1 < len(parts) else len(pcm)
            if isinstance(part, MfskSegment):
                rsid = prefix_pcm(part.mode, part.carrier_hz, oracle)
                assert pcm[start:start + len(rsid) // 2].tobytes() == rsid
            elif isinstance(part, SilencePart):
                assert stop - start == round(part.duration_seconds * 48000) and not np.any(pcm[start:stop])
            else:
                with wave.open(str(part.path)) as wav:
                    assert pcm[start:stop].tobytes() == wav.readframes(wav.getnframes())
        segment = encoded.segments[-1]
        after = round(segment.contents[2].start_seconds * 48000)
        flush_frames = 54 * 1536 if spec["mode"] == "MFSK32" else 90 * 768
        raster_start = after - flush_frames - truth.size * spec["speed"] * 6
        check = independent_wave_check(pcm, raster_start, truth, spec["mode"], spec["speed"], carrier)
        row = {**spec, "expected_text_in_order": expected, "expected_modes": modes,
               "expected_carriers_hz": carriers, "width": width, "height": height,
               "frame_count": len(pcm), "duration_seconds": encoded.duration_seconds,
               "encode_seconds": encode_seconds, "wav": artifact(wav_path, output),
               "truth": artifact(directory / "truth.png", output), "independent_waveform": check,
               "exact_rsid_audio_silence_frame_checks": "pass"}
        rows.append(row)
        write_json(output / "prepared.json", {"matrix": artifact(output / "matrix.json", output),
                    "sources": sources, "cases": rows})
        print(f"PREPARED {row['id']} {width}x{height} duration={encoded.duration_seconds:.3f} waveform_max={check['nominal']['max_pcm_lsb']:.3f}", flush=True)
    for name in ("session9_broadcast_receive.py",):
        shutil.copy(Path(__file__).parent / name, output / name)
    shutil.copy(root / "tools/pi-qualify-mfsk-broadcast.sh", output)
    write_json(output / "production-identity-after-prepare.json", check_production(root))


def decode(root: Path, output: Path) -> None:
    prepared = json.loads((output / "prepared.json").read_text())
    for case in prepared["cases"]:
        directory = output / "cases" / case["id"]
        target = directory / "grampy"
        target.mkdir(exist_ok=False)
        with wave.open(str(output / case["wav"]["path"])) as wav:
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
        iq = hilbert(pcm).astype("<c8")
        data, meta = target / "input.sigmf-data", target / "input.sigmf-meta"
        iq.tofile(data)
        write_json(meta, {"global": {"core:datatype": "cf32_le", "core:sample_rate": 48000},
                          "captures": [{"core:sample_start": 0, "core:frequency": 0}], "annotations": []})
        print(f"DECODE START {case['id']}", flush=True)
        started = time.monotonic()
        try:
            products = decode_iq_products(meta_path=meta, data_path=data, artifact_dir=target / "artifacts",
                       artifact_path_prefix="artifacts", include_diagnostic_manifest=True)
            write_json(target / "text.json", products.text_manifest)
            write_json(target / "quality.json", products.quality_manifest)
            write_json(target / "diagnostic.json", products.diagnostic_manifest)
            write_json(target / "run.json", {"elapsed_seconds": time.monotonic() - started,
                                             "status": "completed", "iq_conversion": "Full untrimmed PCM Hilbert analytic signal, cf32_le; no supplied mode, carrier, picture start or encoder coordinates"})
        except Exception as error:
            write_json(target / "run.json", {"elapsed_seconds": time.monotonic() - started,
                                             "status": "error", "error": repr(error)})
            print(f"DECODE ERROR {case['id']} {error!r}", flush=True)
        print(f"DECODE END {case['id']} elapsed={time.monotonic() - started:.1f}s", flush=True)
    write_json(output / "production-identity-after-decode.json", check_production(root))


def text_in_order(text: str, pieces: list[str]) -> bool:
    cursor = 0
    for piece in pieces:
        found = text.find(piece, cursor)
        if found < 0:
            return False
        cursor = found + len(piece)
    return True


def protocol_text(manifest: dict) -> str:
    """Use canonical receive events, including controls omitted by summaries."""
    return bytes(event["octet"] for event in manifest["text_events"]
                 if event["octet"] is not None).decode("latin1")


def picture_score(truth: np.ndarray, observed: np.ndarray, gate: dict) -> dict:
    if observed.shape != truth.shape:
        return {"pass": False, "error": f"Wrong shape {observed.shape}; expected {truth.shape}"}
    raw = score_raw_rasters(truth, observed)
    aligned = align_component_streams(image_to_wire_components(truth), image_to_wire_components(observed),
                                      **gate["alignment_parameters"])
    checks = {
        "raw_mae": raw["whole_raster"]["mean_absolute_error_255"] <= gate["raw_mae_255_max"],
        "aligned_mae": aligned["aligned_mean_absolute_error_255"] <= gate["aligned_mae_255_max"],
        "channel_bias": all(abs(channel["signed_bias_255"]) <= gate["absolute_channel_bias_255_max"]
                            for channel in raw["channels"].values()),
        "alignment_offset": aligned["maximum_absolute_offset_components"] <= gate["alignment_max_offset_components"],
        "alignment_changes": aligned["offset_change_count"] <= gate["alignment_max_changes"]}
    return {"pass": all(checks.values()), "checks": checks, "raw": raw, "alignment": aligned}


def evaluate(root: Path, output: Path) -> None:
    prepared = json.loads((output / "prepared.json").read_text())
    matrix = json.loads((output / "matrix.json").read_text())
    if artifact(output / "matrix.json", output) != prepared["matrix"]:
        raise ValueError("Frozen matrix identity changed")
    gate = matrix["picture_gate"]
    pi = output / "pi"
    runs = {row["id"]: row for row in json.loads((pi / "runs.json").read_text())}
    rows = []
    review = root / "docs/encoder/data/session9/practical-review"
    review.mkdir(exist_ok=False)
    for case in prepared["cases"]:
        for descriptor in (case["wav"], case["truth"]):
            if artifact(output / descriptor["path"], output) != descriptor:
                raise ValueError("Prepared WAV or source truth changed")
        if runs[case["id"]]["input_sha256"] != case["wav"]["sha256"]:
            raise ValueError("Pi received another WAV")
        directory = output / "cases" / case["id"]
        truth = np.asarray(Image.open(output / case["truth"]["path"]))
        received = pi / case["id"] / "received"
        received.mkdir(exist_ok=True)
        archive_path = pi / case["id"] / "decode.tar"
        if archive_path.exists():
            with tarfile.open(archive_path) as archive:
                archive.extractall(received, filter="data")
        pngs = sorted((received / "images").glob("*.png"))
        pi_text = (received / "decoded.txt").read_text(errors="replace") if (received / "decoded.txt").exists() else ""
        log = (received / "fldigi/control.log").read_text(errors="replace") if (received / "fldigi/control.log").exists() else ""
        events = receiver_events(log)
        modes = score_mode_sequence(case["expected_modes"], events)
        frequencies_ok = len(events) == len(case["expected_carriers_hz"]) and all(
            abs(event["frequency_hz"] - expected) <= 10 for event, expected in zip(events, case["expected_carriers_hz"]))
        checks = {"receiver_exit": runs[case["id"]]["exit_code"] == 0,
                  "whole_wav": runs[case["id"]]["input_interval"] == {"start_frame": 0, "end_frame": case["frame_count"]},
                  "text_and_header_in_order": text_in_order(pi_text, case["expected_text_in_order"]),
                  "automatic_modes": modes["exact"], "automatic_carriers": frequencies_ok,
                  "initial_unrelated_mode": "status before playback: mode='BPSK31'" in log,
                  "no_manual_changes": log.count("modem.set_by_name(") == 1 and "mapped mode switch" not in log,
                  "one_saved_image": len(pngs) == 1}
        pi_result = {"checks": checks, "mode_events": modes}
        viewer_log = pi / case["id"] / "viewer-gdb.log"
        viewer_raw = pi / case["id"] / "viewer.rgb"
        viewer_match = re.search(r"VIEW_GEOMETRY (\d+) (\d+) (\d+)", viewer_log.read_text()) if viewer_log.exists() else None
        if viewer_match and viewer_raw.exists():
            width, height, count = map(int, viewer_match.groups())
            data = viewer_raw.read_bytes()
            if len(data) == count == width * height * 3:
                viewer = np.frombuffer(data, np.uint8).reshape(height, width, 3)
                checks["grayscale_channels_equal"] = truth.ndim == 3 or (
                    np.array_equal(viewer[:, :, 0], viewer[:, :, 1]) and np.array_equal(viewer[:, :, 0], viewer[:, :, 2]))
                scored_viewer = viewer if truth.ndim == 3 else viewer[:, :, 0]
                Image.fromarray(scored_viewer).save(directory / "fldigi.png")
                pi_result["picture"] = picture_score(truth, scored_viewer, gate)
        if "picture" not in pi_result:
            pi_result["picture"] = {"pass": False, "error": "Completed viewer absent or invalid"}
        if len(pngs) == 1:
            with Image.open(pngs[0]) as saved:
                autosave = np.asarray(saved.convert("RGB" if truth.ndim == 3 else "L"))
                pi_result["autosave"] = picture_score(truth, autosave, gate)
                if (directory / "fldigi.png").exists():
                    pi_result["autosave_equals_viewer"] = np.array_equal(autosave, np.asarray(Image.open(directory / "fldigi.png")))
        checks["saved_picture_quality"] = pi_result.get("autosave", {}).get("pass", False)
        pi_result["pass"] = all(checks.values()) and pi_result["picture"]["pass"]
        diagnostic = directory / "grampy/diagnostic.json"
        own = {"picture_support": "supported" if case["grampy_picture_required"] else "MFSK32 production picture decoding outside accepted decoder scope"}
        if diagnostic.exists():
            manifest = json.loads(diagnostic.read_text())
            own["status"] = manifest["status"]
            own["warnings"] = manifest["warnings"]
            own["configuration"] = manifest["decoder"]["configuration"]
            own["whole_input_interval"] = manifest["input"]["requested_interval"] == {
                "start": 0, "stop": case["frame_count"]}
            # Both summary.text and summary.octets remove controls. The
            # canonical text_events preserve the actual receive octets.
            own_octets = protocol_text(manifest)
            own["text_and_header_in_order"] = text_in_order(own_octets, case["expected_text_in_order"])
            own["mode_segments"] = manifest.get("mode_segments", [])
            detected_modes = [segment["mode"] for segment in own["mode_segments"]]
            own["automatic_modes"] = detected_modes == case["expected_modes"]
            own["automatic_carriers"] = len(own["mode_segments"]) == len(case["expected_carriers_hz"]) and all(
                abs(segment["center_hz"] - carrier) <= 10
                for segment, carrier in zip(own["mode_segments"], case["expected_carriers_hz"]))
            own["complete_framing"] = manifest["status"] == "complete"
            artifacts = [item for item in manifest["artifacts"] if item["kind"] == "png_uint8_raster"]
            own["picture_count"] = len(artifacts)
            own["complete_picture"] = len(manifest["pictures"]) == 1 and manifest["pictures"][0]["complete"]
            if case["grampy_picture_required"] and len(artifacts) == 1:
                raster_path = directory / "grampy" / artifacts[0]["path"]
                observed = np.asarray(Image.open(raster_path).convert("RGB" if truth.ndim == 3 else "L"))
                own["picture"] = picture_score(truth, observed, gate)
                Image.fromarray(observed).save(directory / "grampy.png")
            own["pass"] = own["text_and_header_in_order"] and own["automatic_modes"] and own["automatic_carriers"] and own["complete_framing"] and own["whole_input_interval"] and (
                own.get("picture", {}).get("pass", False) and own["complete_picture"] if case["grampy_picture_required"] else True)
        else:
            own["pass"] = False
            own["error"] = json.loads((directory / "grampy/run.json").read_text())
        row = {**case, "fldigi": pi_result, "grampy": own,
               "numerical_pass": pi_result["pass"] and own["pass"], "pm_visual_status": "pending"}
        evidence_paths = [archive_path, viewer_raw, viewer_log, directory / "grampy/diagnostic.json",
                          directory / "grampy/text.json", directory / "grampy/quality.json",
                          directory / "grampy/input.sigmf-meta", directory / "grampy/input.sigmf-data",
                          directory / "encoder-result.json", pi / case["id"] / "command.json",
                          received / "metadata.json", received / "decoded.txt",
                          received / "fldigi/control.log"]
        row["evidence"] = [artifact(path, output) for path in evidence_paths if path.exists()]
        rows.append(row)
        for name in ("truth.png", "grampy.png", "fldigi.png"):
            path = directory / name
            if path.exists():
                shutil.copy(path, review / f"{case['id']}-{name}")
        print(f"SCORED {case['id']} fldigi={pi_result['pass']} grampy={own['pass']} piMAE={pi_result['picture'].get('raw',{}).get('whole_raster',{}).get('mean_absolute_error_255')}", flush=True)
    result = {"schema": matrix["schema"], "matrix": prepared["matrix"], "picture_gate": gate,
              "receiver": json.loads((pi / "identity.json").read_text()),
              "production": check_production(root), "cases": rows,
              "sources": prepared["sources"],
              "experiment_identity": [artifact(Path(__file__), root),
                    artifact(Path(__file__).parent / "session9_broadcast_receive.py", root),
                    artifact(root / "tools/pi-qualify-mfsk-broadcast.sh", root)],
              "summary": {"total": len(rows), "numerical_passes": sum(row["numerical_pass"] for row in rows),
                          "fldigi_passes": sum(row["fldigi"]["pass"] for row in rows),
                          "grampy_required_picture_cases": sum(row["grampy_picture_required"] for row in rows),
                          "pm_visual_status": "pending"}}
    write_json(output / "qualification.json", result)
    write_json(review / "qualification.json", result)
    build_review(review, rows, gate)


def build_review(review: Path, rows: list[dict], gate: dict) -> None:
    canvas = Image.new("RGB", (1080, 250 * len(rows) + 70), "white")
    draw = ImageDraw.Draw(canvas)
    for i, label in enumerate(("SOURCE", "GRAM PY PUBLIC DECODER", "PINNED PI FLDIGI")):
        draw.text((i * 360 + 12, 15), label, fill="black")
    sections = []
    for index, row in enumerate(rows):
        y = 55 + 250 * index
        draw.text((12, y), row["id"], fill="black")
        cells = []
        for column, name in enumerate(("truth", "grampy", "fldigi")):
            path = review / f"{row['id']}-{name}.png"
            score = row.get(name, {}).get("picture", {})
            mae = score.get("raw", {}).get("whole_raster", {}).get("mean_absolute_error_255")
            caption = "Source" if name == "truth" else f"MAE {mae:.2f}" if mae is not None else "Picture outside production decoder scope" if name == "grampy" and not row["grampy_picture_required"] else "Missing picture"
            if path.exists():
                picture = Image.open(path).convert("RGB")
                picture.thumbnail((320, 190))
                canvas.paste(picture, (column * 360 + 12, y + 22))
                encoded = base64.b64encode(path.read_bytes()).decode()
                cells.append(f'<figure><figcaption>{name.upper()} · {html.escape(caption)}</figcaption><img src="data:image/png;base64,{encoded}" alt="{name} {row["id"]}"></figure>')
            else:
                cells.append(f'<figure><figcaption>{html.escape(caption)}</figcaption></figure>')
            draw.text((column * 360 + 12, y + 218), caption, fill="black")
        pi_ok, own_ok = row["fldigi"]["pass"], row["grampy"]["pass"]
        details = html.escape(json.dumps({"fldigi_checks": row["fldigi"]["checks"], "fldigi_score": row["fldigi"]["picture"],
                         "grampy_text": row["grampy"].get("text_and_header_in_order"), "grampy_score": row["grampy"].get("picture")}, indent=2))
        source_label = {"card": "station portrait", "photo": "sunset photograph", "chart": "diagnostic chart"}[row["source"]]
        title = f'{row["mode"]} · {"RGB" if row["color"] == "color" else "grayscale"} · p{row["speed"]} · {source_label}'
        if row.get("mixed"):
            title = "Mixed broadcast: MFSK32 news → audio/silence → MFSK64 RGB p4 photograph"
        sections.append(f'<section><h2>{title} · {row["width"]}×{row["height"]}</h2><p>{row["id"]} · {row["duration_seconds"]:.1f}s complete WAV · Numerical screen: fldigi {"PASS" if pi_ok else "FAIL"}; GramPy {"PASS" if own_ok else "FAIL"}. Visual decision pending.</p><div class="row">{"".join(cells)}</div><p><label><input type="checkbox"> I have reviewed this row visually</label></p><details><summary>Scorecard and functional checks</summary><pre>{details}</pre></details></section>')
    canvas.save(review / "comparison.png")
    with (review / "scores.md").open("w") as table:
        table.write("# Practical numerical screening\n\nMAE is average component error on the 0–255 intensity scale. PM visual review remains pending.\n\n| Case | GramPy raw MAE | Pi fldigi raw MAE | Pi aligned MAE | Functional / numerical screen |\n| --- | ---: | ---: | ---: | --- |\n")
        for row in rows:
            def value(receiver, metric):
                score = row[receiver].get("picture", {})
                number = score.get("raw", {}).get("whole_raster", {}).get("mean_absolute_error_255") if metric == "raw" else score.get("alignment", {}).get("aligned_mean_absolute_error_255")
                return f"{number:.2f}" if number is not None else "outside picture scope" if receiver == "grampy" and not row["grampy_picture_required"] else "missing"
            table.write(f"| {row['id']} | {value('grampy','raw')} | {value('fldigi','raw')} | {value('fldigi','aligned')} | {'PASS' if row['numerical_pass'] else 'FAIL'} |\n")
    passed = sum(row["numerical_pass"] for row in rows)
    page = '''<!doctype html><html><head><meta charset="utf-8">
<title>GramPy practical encoder qualification</title>
<style>
body{font:16px system-ui;max-width:1200px;margin:30px auto;padding:0 20px;background:#f5f5f5;color:#202020}
section{background:white;padding:20px;margin:24px 0;border:1px solid #bbb}h2{font-size:20px}
.row{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;overflow-x:auto}
.expanded .row{grid-template-columns:repeat(3,minmax(500px,1fr))}
figure{margin:0;min-height:190px}img{max-width:100%;width:auto;height:auto;border:1px solid #888}
figcaption{margin-bottom:10px}pre{overflow:auto;font-size:12px}button{padding:7px;margin-right:10px}
</style></head><body><h1>Practical encoder qualification</h1>
<p>The same unchanged-encoder WAV is decoded independently by the public GramPy
decoder and pinned Pi fldigi 4.2.13. Both receive the complete broadcast using
automatic mode acquisition. Pictures appear at native size; use 2× to inspect blur.</p>
<p>Frozen screen: raw MAE ≤25/255; aligned MAE ≤20/255; channel bias ≤15/255;
alignment offset ≤12 components and ≤12 changes. Correct text, headers, picture
geometry and mode acquisition are required. Exact pixels are diagnostic.</p>
<p>MFSK32 pictures are outside the accepted GramPy production decoder scope;
those three rows test fldigi picture compatibility and GramPy text only.
MFSK64 rows test both picture decoders.</p>
<button onclick="document.body.classList.add('expanded');document.querySelectorAll('img').forEach(i=>{i.style.width=(i.naturalWidth*2)+'px';i.style.maxWidth='none'})">2× images</button>
<button onclick="document.body.classList.remove('expanded');document.querySelectorAll('img').forEach(i=>{i.style.width='auto';i.style.maxWidth='100%'})">Native size</button>
'''
    (review / "index.html").write_text(page + f"<p><strong>{passed}/{len(rows)} cases pass the numerical and functional screen. PM visual review remains pending.</strong></p>" + "".join(sections) + '</body></html>')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "decode", "evaluate"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    globals()[args.action](Path.cwd(), args.output.resolve())
