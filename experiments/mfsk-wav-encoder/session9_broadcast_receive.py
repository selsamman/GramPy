"""Pinned Pi whole-WAV reception; independent of encoder/decoder imports."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


def main(bundle: Path, output: Path, adapter: Path, binary: Path) -> None:
    manifest = json.loads((bundle / "prepared.json").read_text())
    env = dict(os.environ, PATH=str(binary.parent) + ":" + os.environ["PATH"])
    identity = {"platform": platform.platform(), "architecture": platform.machine(),
                "receiver_version": subprocess.check_output([str(binary), "--version"], text=True).splitlines()[0],
                "receiver_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest()}
    (output / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    runs = []
    for case in manifest["cases"]:
        directory = output / case["id"]
        directory.mkdir()
        cfg = directory / "config"
        cfg.mkdir()
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
        wav = bundle / case["wav"]["path"]
        if hashlib.sha256(wav.read_bytes()).hexdigest() != case["wav"]["sha256"]:
            raise ValueError("WAV transfer hash mismatch")
        timeout = math.ceil(case["duration_seconds"]) + 90
        command = [str(adapter), "--input", str(wav), "--output", str(directory / "decode.tar"),
                   "--work-dir", str(directory / "work"), "--config-dir", str(cfg),
                   "--mode", "BPSK31", "--rxid", "on", "--afc", "off", "--audio-frequency-hz", "1500",
                   "--status-interval-sec", "5", "--post-playback-sec", "15", "--timeout-sec", str(timeout),
                   "--debug-bundle", "full", "--nice", "0", "--audio-backend", "alsa-loopback",
                   "--alsa-capture-plugin", "plug"]
        (directory / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        print(f"START {case['id']} duration={case['duration_seconds']:.3f}s", flush=True)
        started = time.monotonic()
        with (directory / "adapter.stdout").open("w") as stdout, (directory / "adapter.stderr").open("w") as stderr:
            try:
                result = subprocess.run(command, env=env, stdout=stdout, stderr=stderr, timeout=timeout + 60)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        for filename in ("viewer.rgb", "viewer-gdb.log"):
            path = directory / "work" / filename
            if path.exists():
                shutil.copy(path, directory / filename)
        runs.append({"id": case["id"], "exit_code": code, "elapsed_seconds": time.monotonic() - started,
                     "input_interval": {"start_frame": 0, "end_frame": case["frame_count"]},
                     "manual_mode_changes": 0, "input_sha256": case["wav"]["sha256"]})
        (output / "runs.json").write_text(json.dumps(runs, indent=2) + "\n")
        print(f"END {case['id']} exit={code}", flush=True)


if __name__ == "__main__":
    main(*(Path(arg).resolve() for arg in sys.argv[1:]))
