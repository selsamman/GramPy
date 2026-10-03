"""Paired picture diagnostics; never substitutes for whole-WAV qualification.

Run on the Pi through tools/pi-investigate-mfsk-pictures.sh. The receiver
binary is unchanged. A sidecar adapter reads its settled GUI picture buffer
with gdb only after playback and the normal 15-second settling interval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image
from grampy.api import ImagePart, MfskSegment, TextPart, encode_mfsk_wav


RX_SHA256 = "dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(actual: bytes, expected: bytes) -> dict:
    if len(actual) != len(expected):
        return {"geometry_match": False, "actual_bytes": len(actual)}
    errors = [abs(a - b) for a, b in zip(actual, expected)]
    return {"geometry_match": True, "exact": not any(errors),
            "unequal_components": sum(e != 0 for e in errors),
            "max_error": max(errors), "mae": sum(errors) / len(errors),
            "pixel_sha256": hashlib.sha256(actual).hexdigest(),
            "values": list(actual)}


def main() -> None:
    bundle, root = map(Path, sys.argv[1:3])
    binary = Path("/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64/install/bin/fldigi")
    adapter = Path("/opt/radiogram/current/tools/fldigi-decode-wav")
    source = binary.parents[2] / "source/src"
    if digest(binary) != RX_SHA256:
        raise RuntimeError("pinned receiver hash changed")
    root.mkdir(exist_ok=True)
    src = root / "source"
    src.mkdir(exist_ok=True)
    for name in ("mfsk/mfsk.cxx", "mfsk/mfsk-pic.cxx", "include/picture.h",
                 "widgets/picture.cxx", "filters/filters.cxx", "include/filters.h"):
        dest = src / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source / name, dest)
    if (src / "session9_probe.py").exists():
        shutil.copy(src / "session9_probe.py", src / "session9_probe-attempt1.py")
    shutil.copy(bundle / "session9_probe.py", src / "session9_probe.py")
    shutil.copy(bundle / "pi-investigate-mfsk-pictures.sh", src)
    shutil.copy(adapter, src / "receiver-adapter-original.sh")
    text = adapter.read_text()
    anchor = 'end_utc=$(date -u'
    if text.count(anchor) != 1:
        raise RuntimeError("adapter snapshot insertion anchor changed")
    hook = '''python3 - "$config_dir" "$work_dir" <<'SNAPSHOT'
import pathlib, subprocess, sys
cfg, out = sys.argv[1:]
matches = []
for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit(): continue
    try:
        args = (proc / 'cmdline').read_bytes().split(b'\\0')
        if args and pathlib.Path(args[0].decode()).name == 'fldigi' and b'--config-dir' in args:
            if args[args.index(b'--config-dir') + 1].decode() == cfg: matches.append(proc.name)
    except (OSError, ValueError, UnicodeError): pass
if len(matches) != 1: raise SystemExit(f'expected one fldigi process, got {matches}')
commands = [
    'set pagination off',
    'printf "VIEW_GEOMETRY %d %d %d\\\\n", picRx->width, picRx->height, picRx->bufsize',
    f'dump binary memory {out}/viewer.rgb picRx->vidbuf picRx->vidbuf+picRx->bufsize',
    'detach',
]
argv = ['gdb', '-q', '-batch', '-p', matches[0]]
for cmd in commands: argv += ['-ex', cmd]
result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
pathlib.Path(out, 'viewer-gdb.log').write_text(result.stdout)
if result.returncode: raise SystemExit(result.returncode)
SNAPSHOT
'''
    sidecar = root / "receiver-adapter-snapshot.sh"
    sidecar.write_text(text.replace(anchor, hook + anchor))
    sidecar.chmod(0o755)
    shutil.copy(bundle / "primary-color-8x4.png", root)
    image = root / "primary-color-8x4.png"
    rgb = Image.open(image).convert("RGB").tobytes()
    ppm = Path("/opt/radiogram/reference/fixtures/mfsk64-primary-color-8x4-4.2.12/primary-color-8x4.ppm")
    if Image.open(ppm).convert("RGB").tobytes() != rgb:
        raise RuntimeError("controlled reference source image differs from candidate truth")
    gray = bytes((31*r + 61*g + 8*b)//100 for r, g, b in zip(rgb[::3], rgb[1::3], rgb[2::3]))
    gray_rgb = bytes(value for value in gray for _ in range(3))
    identity = {"receiver_sha256": digest(binary), "adapter_original_sha256": digest(adapter),
                "adapter_sidecar_sha256": digest(sidecar), "source_png_sha256": digest(image),
                "source_ppm_sha256": digest(ppm), "source_pixel_sha256": hashlib.sha256(rgb).hexdigest(),
                "wheel_sha256": digest(next((bundle / "distribution").glob("*.whl"))),
                "settings": {"rxid": "off", "afc": "off", "carrier_hz": 1500,
                             "status_interval_sec": 0.5, "post_playback_sec": 15},
                "snapshot": "read-only gdb dump after playback/settle, before receiver shutdown"}
    if (root / "identity.json").exists():
        if json.loads((root / "identity.json").read_text()) != identity:
            raise RuntimeError("resume would change experiment input identities/settings")
    (root / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    cases = [
        ("mfsk32-gray", "MFSK32", "grayscale", "RG-MFSK32-GRAY-8X4-P8",
         Path("/opt/radiogram/reference/fixtures/wire-matrix-4.2.12/mfsk32-gray-8x4-p8")),
        ("mfsk64-color", "MFSK64", "color", "RG-PRIMARY-MFSK64-COLOR-8X4",
         ppm.parent),
    ]
    rows = []
    for name, mode, color, payload, reference in cases:
        expected = rgb if color == "color" else gray_rgb
        for transmitter in ("fldigi", "native"):
            case = root / (name + "-" + transmitter)
            case.mkdir(exist_ok=True)
            wav = case / "transmission.wav"
            completed = (case / "work/viewer.rgb").exists() and (case / "decode.tar").exists()
            if transmitter == "fldigi" and not completed:
                shutil.copy(reference / "transmission.wav", wav)
                shutil.copy(reference / "transmission.json", case / "transmission.json")
                metadata = json.loads((case / "transmission.json").read_text())
                if digest(wav) != metadata["wav"]["sha256"]:
                    raise RuntimeError("controlled fixture hash mismatch")
            elif transmitter == "native" and not completed:
                result = encode_mfsk_wav(parts=[MfskSegment(mode=mode, parts=[
                    TextPart(data=payload.encode()), ImagePart(path=image, color=color, samples_per_pixel=8)
                ])], output_path=wav)
                (case / "encoder-result.json").write_text(json.dumps({
                    "duration_seconds": result.duration_seconds,
                    "segments": [{"start_seconds": s.start_seconds,
                                  "contents": [c.start_seconds for c in s.contents]} for s in result.segments]
                }, indent=2) + "\n")
            command = [str(sidecar), "--input", str(wav), "--output", str(case / "decode.tar"),
                       "--work-dir", str(case / "work"), "--config-dir", str(case / "config"),
                       "--mode", mode, "--rxid", "off", "--afc", "off",
                       "--audio-frequency-hz", "1500", "--status-interval-sec", "0.5",
                       "--post-playback-sec", "15", "--debug-bundle", "full"]
            (case / "command.json").write_text(json.dumps(command, indent=2) + "\n")
            env = dict(os.environ, PATH=str(binary.parent) + ":" + os.environ["PATH"])
            if not completed:
                with (case / "adapter.stdout").open("w") as stdout, (case / "adapter.stderr").open("w") as stderr:
                    result = subprocess.run(command, env=env, stdout=stdout, stderr=stderr, timeout=180)
                if result.returncode:
                    raise RuntimeError(f"adapter failed for {case.name}: {result.returncode}")
            gdb_log = (case / "work/viewer-gdb.log").read_text()
            match = re.search(r"VIEW_GEOMETRY (\d+) (\d+) (\d+)", gdb_log)
            if not match or tuple(map(int, match.groups())) != (8, 4, 96):
                raise RuntimeError("settled viewer has unexpected geometry")
            viewer = (case / "work/viewer.rgb").read_bytes()
            Image.frombytes("RGB", (8, 4), viewer).save(case / "viewer.png")
            images = sorted((case / "work/images").glob("*.png"))
            if len(images) != 1:
                raise RuntimeError(f"expected one autosaved picture, got {images}")
            shutil.copy(images[0], case / "autosave.png")
            try:
                autosave = Image.open(images[0]).convert("RGB")
                autosave_score = metrics(autosave.tobytes(), expected)
                equals_viewer = autosave.tobytes() == viewer
            except OSError as error:
                autosave_score = {"decode_error": str(error), "file_bytes": images[0].stat().st_size,
                                  "file_sha256": digest(images[0]), "header_hex": images[0].read_bytes()[:32].hex()}
                equals_viewer = False
            row = {"case": case.name, "mode": mode, "color": color, "speed": 8,
                   "wav_sha256": digest(wav), "autosave": autosave_score,
                   "viewer": metrics(viewer, expected),
                   "autosave_equals_viewer": equals_viewer}
            rows.append(row)
            (root / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
            print(json.dumps({k: v for k, v in row.items() if k not in ("autosave", "viewer")}), flush=True)
            print(json.dumps({"autosave": {k:v for k,v in row["autosave"].items() if k != "values"},
                              "viewer": {k:v for k,v in row["viewer"].items() if k != "values"}}), flush=True)


if __name__ == "__main__":
    main()
