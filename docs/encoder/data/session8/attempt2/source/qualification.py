"""Run the frozen v2 matrix on the Pi; preserve raw evidence before scoring.

Invoked by tools/pi-qualify-mfsk-encoder.sh, never directly over SSH.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone

from grampy.api import (AudioPart, ImagePart, MfskSegment, SilencePart,
                        TextPart, encode_mfsk_wav)


def artifact(path: Path, root: Path) -> dict:
    return {"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main(bundle: Path, output: Path) -> None:
    started = datetime.now(timezone.utc).isoformat()
    source = output / "source"
    shutil.copytree(bundle, source)
    matrix = json.loads((source / "matrix.json").read_text())
    old = json.loads((source / "matrix-v1.json").read_text())
    inputs = output / "inputs"
    inputs.mkdir()
    shutil.copy(source / "primary-color-8x4.png", inputs)
    audio = inputs / "audio-marker.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        wav.writeframes(struct.pack("<6h", 0, 8192, -8192, 16384, -16384, 0) * 8000)
    paths = {"primary_rgb_png": inputs / "primary-color-8x4.png", "audio_marker": audio}
    binary = Path("/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64/install/bin/fldigi")
    adapter = Path("/opt/radiogram/current/tools/fldigi-decode-wav")
    if hashlib.sha256(binary.read_bytes()).hexdigest() != "dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3":
        raise RuntimeError("qualified receiver binary hash mismatch")
    shutil.copy(binary, output / "receiver-binary")
    shutil.copy(adapter, output / "receiver-adapter.sh")
    env = dict(os.environ, PATH=str(binary.parent) + ":" + os.environ["PATH"])
    version = subprocess.check_output([str(binary), "--version"], text=True).splitlines()[0]
    config = matrix["receiver"]
    results = []
    for case in matrix["cases"]:
        compositions = [(case["id"], case["composition"])] if "composition" in case else [
            (name, next(c["composition"] for c in old["cases"] if c["id"] == name))
            for name in case["composition_from_v1_cases"]]
        for name, composition in compositions:
            directory = output / "cases" / name
            directory.mkdir(parents=True)
            parts = []
            for part in composition:
                if part["kind"] == "mfsk":
                    contents = [TextPart.from_text(c["utf8"]) if c["kind"] == "text" else
                                ImagePart(paths[c["source"]], color=c["color"],
                                          samples_per_pixel=c["samples_per_pixel"])
                                for c in part["contents"]]
                    parts.append(MfskSegment(contents, mode=part["mode"], carrier_hz=part["carrier_hz"]))
                elif part["kind"] == "audio":
                    parts.append(AudioPart(paths[part["source"]]))
                else:
                    parts.append(SilencePart(part["duration_seconds"]))
            wav_path = directory / "generated.wav"
            encode_started = time.monotonic()
            result = encode_mfsk_wav(parts=parts, output_path=wav_path)
            encode_elapsed = time.monotonic() - encode_started
            with wave.open(str(wav_path)) as wav:
                frames = wav.getnframes()
                assert wav.getparams()[:3] == (1, 2, 48000)
                assert result.duration_seconds == frames / 48000
            record = dataclasses.asdict(result)
            record["output_path"] = str(wav_path.relative_to(output))
            record["frame_count"] = frames
            record["encode_elapsed_seconds"] = encode_elapsed
            record["segments_frames"] = [
                {"input_index": s.input_index, "start_frame": round(s.start_seconds * 48000),
                 "contents": [{"content_index": c.content_index, "start_frame": round(c.start_seconds * 48000)}
                              for c in s.contents]} for s in result.segments]
            (directory / "encoder-result.json").write_text(json.dumps(record, indent=2) + "\n")
            (directory / "composition.json").write_text(json.dumps(composition, indent=2) + "\n")
            cfg = directory / "config"
            cfg.mkdir()
            # Names verified in the qualified receiver's configuration.h.
            settings = {"AUDIOIO": 1, "PORTINDEVICE": "default", "PORTININDEX": -1,
                        "PORTOUTDEVICE": "default", "PORTOUTINDEX": -1,
                        "XMLRPC_ADDRESS": "127.0.0.1", "XMLRPC_PORT": 7362,
                        "CHECK_FOR_UPDATES": 0, "STARTATSWEETSPOT": 0, "RETAINFREQLOCK": 0,
                        "SQLCH_BY_MODE": 0, "AFC_BY_MODE": 0, "RSIDWIDESEARCH": 1,
                        "RECEIVERSID": 1, "RSIDNOTIFYONLY": 0, "RSIDAUTODISABLE": 0,
                        "RSIDRXMODESEXCLUDE": "", "DISABLERSIDFREQCHANGE": 0,
                        "DISABLE_RSID_WARNING_DIALOG_BOX": 1}
            (cfg / "fldigi_def.xml").write_text("<FLDIGI_DEFS>\n" + "".join(
                f"<{key}>{value}</{key}>\n" for key, value in settings.items()) + "</FLDIGI_DEFS>\n")
            command = [str(adapter), "--input", str(wav_path), "--output", str(directory / "decode.tar"),
                       "--mode", "BPSK31", "--rxid", "on", "--afc", "off", "--audio-frequency-hz", "1500",
                       "--config-dir", str(cfg), "--work-dir", str(directory / "work"),
                       "--debug-bundle", "full", "--nice", "0", "--post-playback-sec", "15",
                       "--status-interval-sec", "0.25", "--audio-backend", "alsa-loopback",
                       "--alsa-capture-plugin", "plug"]
            (directory / "command.json").write_text(json.dumps(command, indent=2) + "\n")
            print(f"START {name} frames={frames} duration={frames / 48000:.3f}", flush=True)
            with (directory / "adapter.stdout").open("w") as stdout, (directory / "adapter.stderr").open("w") as stderr:
                run = subprocess.run(command, env=env, stdout=stdout, stderr=stderr)
            results.append({"id": name, "matrix_id": case["id"], "exit_code": run.returncode,
                            "input_interval": {"start_frame": 0, "end_frame": frames},
                            "manual_mode_changes": 0})
            print(f"END {name} exit={run.returncode}", flush=True)
            (output / "raw-runs.json").write_text(json.dumps(results, indent=2) + "\n")
    identity = {"started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
                "target": {"hostname": platform.node(), "platform": platform.platform(),
                           "architecture": platform.machine(), "python_version": platform.python_version()},
                "receiver_version": version, "receiver_configuration": config}
    (output / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
