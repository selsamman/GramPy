"""Score preserved whole-WAV Pi runs without relaxing the frozen matrix.

Run in the repository virtualenv through tools/mac-local.sh. Raw receiver
artifacts remain authoritative; absent evidence is blocked, never inferred
from GramPy recovery. JSON Schema and cross-field checks are both required.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys
import tarfile
import wave
import xml.etree.ElementTree as ET

import jsonschema
from PIL import Image

from grampy.mfsk_segment_encode import ImageSource, plan_mfsk_segment


def artifact(path: Path, root: Path) -> dict:
    return {"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def prefix_pcm(mode: str, carrier: float, oracle: dict) -> bytes:
    """Independent frozen-word integrator; imports no encoder waveform code."""
    count = 48000 * 1024 // 11025
    output = bytearray()
    words = {"primary_147": "MFSK32", "primary_escape_6": "escape", "secondary_620": "MFSK64"}
    for event in oracle["sequence_symbol_periods"][mode]:
        if event["kind"] not in words:
            output.extend(b"\0\0" * count * event["count"])
            continue
        phase = 0.0
        for tone in oracle["words"][words[event["kind"]]]["tones"]:
            increment = 2 * math.pi * (carrier + (tone - 7) * 11025 / 1024) / 48000
            for _ in range(count):
                phase = (phase + increment) % (2 * math.pi)
                output.extend(struct.pack("<h", round(16384 * math.sin(phase))))
    return bytes(output)


def receiver_events(log: str) -> list[dict]:
    """Observe receiver mode/carrier transitions, never expected-matrix modes.

    Code is the standardized identifier of the observed mode; control polling
    cannot independently expose the raw primary/secondary RSID detector code.
    The extended-code check is therefore blocked unless a detector log exists.
    """
    events = []
    last = None
    for line in log.splitlines():
        match = re.search(r"status (?:during playback|after playback wait): mode='(MFSK32|MFSK64)' carrier=([0-9.]+)", line)
        if not match:
            continue
        mode, carrier = match.group(1), float(match.group(2))
        key = (mode, carrier)
        if key == last:
            continue
        last = key
        events.append({"mode": mode, "code": 147 if mode == "MFSK32" else 620,
                       "frequency_hz": carrier, "receiver_log_evidence": line})
    return events


def verify_artifacts(value, root: Path) -> None:
    """Bind every artifact descriptor to bytes, including nested run evidence."""
    if isinstance(value, dict):
        if set(value) == {"path", "bytes", "sha256"}:
            path = (root / value["path"]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("artifact escaped evidence root")
            if artifact(path, root.resolve()) != value:
                raise ValueError(f"artifact hash or size mismatch: {value['path']}")
        else:
            for child in value.values():
                verify_artifacts(child, root)
    elif isinstance(value, list):
        for child in value:
            verify_artifacts(child, root)


def verify_cross_fields(manifest: dict, matrix: dict, root: Path) -> None:
    expected_ids = {name for case in matrix['cases'] for name in
                    ([case['id']] if 'composition' in case else case['composition_from_v1_cases'])}
    actual_ids = [case['id'] for case in manifest['cases']]
    if set(actual_ids) != expected_ids or len(actual_ids) != len(expected_ids):
        raise ValueError('matrix coverage mismatch')
    cases = manifest['cases']
    summary = {'total': len(cases), 'passed': sum(c['status'] == 'pass' for c in cases),
               'failed': sum(c['status'] == 'fail' for c in cases),
               'blocked': sum(c['status'] == 'blocked' for c in cases)}
    if summary != manifest['summary']:
        raise ValueError('summary does not match case statuses')
    expected_status = 'complete' if summary['passed'] == len(cases) else 'failed' if summary['failed'] else 'partial'
    if manifest['status'] != expected_status:
        raise ValueError('manifest status does not match case statuses')
    for case in cases:
        with wave.open(str(root / case['generated_wav']['path'])) as wav:
            interval = {'start_frame': 0, 'end_frame': wav.getnframes()}
        for run in case['continuous_receiver_runs']:
            if run['input_interval'] != interval or run['manual_mode_changes'] != 0:
                raise ValueError('receiver did not cover the entire unmodified composition')
        if case['status'] == 'pass' and (case['discrepancies'] or
                any(check['status'] != 'pass' for check in case['checks'])):
            raise ValueError('passing case has failed checks or discrepancies')


def main(root: Path, reporting_schema: Path | None = None) -> None:
    identity = json.loads((root / "identity.json").read_text())
    matrix = json.loads((root / "source/matrix.json").read_text())
    oracle = json.loads((root / "source/rsid-oracle.json").read_text())
    runs = json.loads((root / "raw-runs.json").read_text())
    cases = []
    for run in runs:
        directory = root / "cases" / run["id"]
        extracted = directory / "received"
        extracted.mkdir(exist_ok=True)
        with tarfile.open(directory / "decode.tar") as archive:
            archive.extractall(extracted, filter="data")
        composition = json.loads((directory / "composition.json").read_text())
        record = json.loads((directory / "encoder-result.json").read_text())
        metadata = json.loads((extracted / "metadata.json").read_text())
        text = (extracted / "decoded.txt").read_text(errors="replace")
        logpath = extracted / "fldigi/control.log"
        log = logpath.read_text(errors="replace")
        events = receiver_events(log)
        checks = []
        discrepancies = []
        config_path = extracted / "fldigi/config-start/fldigi_def.xml"
        config_xml = ET.parse(config_path).getroot()
        harness_audio_ok = config_xml.findtext("AUDIOIO") == "1" and config_xml.findtext("PORTINDEVICE") == "default"

        def check(name, expected, observed, ok, evidence, classification="unresolved"):
            status = "blocked" if ok is None else "pass" if ok else "fail"
            checks.append({"id": name, "status": status, "expected": expected,
                           "observed": observed, "evidence": evidence})
            if status != "pass":
                if not harness_audio_ok and classification == "unresolved":
                    classification = "automation-failure"
                discrepancies.append({"classification": classification,
                                      "summary": f"{name}: {status}", "evidence": evidence})

        with wave.open(str(directory / "generated.wav")) as wav:
            pcm = wav.readframes(wav.getnframes())
            frames = wav.getnframes()
        expected_modes = [p["mode"] for p in composition if p["kind"] == "mfsk"]
        expected_carriers = [p["carrier_hz"] for p in composition if p["kind"] == "mfsk"]
        check("whole-wav-receiver-exit", 0, run["exit_code"],
              run["exit_code"] == metadata.get("control_exit_status") == 0,
              [str((extracted / "metadata.json").relative_to(root))], "automation-failure")
        check("whole-wav-interval-and-no-manual-changes", [0, frames, 0],
              [run["input_interval"]["start_frame"], run["input_interval"]["end_frame"], run["manual_mode_changes"]],
              run["input_interval"] == {"start_frame": 0, "end_frame": frames} and run["manual_mode_changes"] == 0
              and "mapped mode switch" not in log and log.count("modem.set_by_name(") == 1,
              [str(logpath.relative_to(root)), str((directory / "command.json").relative_to(root))], "automation-failure")
        check("initial-unrelated-mode", "BPSK31", "BPSK31" if "mode='BPSK31'" in log else "absent",
              "status before playback: mode='BPSK31'" in log, [str(logpath.relative_to(root))], "automation-failure")
        required_settings = {"AUDIOIO": "1", "PORTINDEVICE": "default", "PORTOUTDEVICE": "default",
                             "RSIDWIDESEARCH": "1", "RSIDNOTIFYONLY": "0", "RSIDAUTODISABLE": "0",
                             "RSIDRXMODESEXCLUDE": "", "DISABLERSIDFREQCHANGE": "0"}
        observed_settings = {name: config_xml.findtext(name, default="") for name in required_settings}
        check("receiver-rxid-configuration", required_settings, observed_settings,
              observed_settings == required_settings and metadata.get("rxid") == "on"
              and re.search(r"\brsid=(?:1|True)\b", log) is not None and "aplay exited with 0" in log,
              [str(config_path.relative_to(root)), str(logpath.relative_to(root))], "automation-failure")
        check("rxid-acquisitions-in-order", expected_modes, [e["mode"] for e in events],
              [e["mode"] for e in events] == expected_modes, [str(logpath.relative_to(root))])
        check("carrier-acquisitions-in-order", expected_carriers, [e["frequency_hz"] for e in events],
              len(events) == len(expected_carriers) and all(abs(e["frequency_hz"] - c) < 6 for e, c in zip(events, expected_carriers)),
              [str(logpath.relative_to(root))])
        expected_text = [c["utf8"] for p in composition if p["kind"] == "mfsk" for c in p["contents"] if c["kind"] == "text"]
        # fldigi displays CR as LF. Caller LF in these matrix cases is unchanged.
        cursor = 0
        found = []
        for value in expected_text:
            position = text.find(value, cursor)
            found.append(position)
            if position >= 0:
                cursor = position + len(value)
        check("caller-text-exact-and-ordered", expected_text, {"positions": found, "decoded": text},
              all(p >= 0 for p in found), [str((extracted / "decoded.txt").relative_to(root))])
        expected_images = [c for p in composition if p["kind"] == "mfsk" for c in p["contents"] if c["kind"] == "image"]
        images = sorted((extracted / "images").glob("*"))
        check("picture-count", len(expected_images), len(images), len(images) == len(expected_images),
              [str((extracted / "metadata.json").relative_to(root))])
        for index, (expected, received) in enumerate(zip(expected_images, images)):
            truth = Image.open(root / "inputs/primary-color-8x4.png").convert("RGB")
            if expected["color"] == "grayscale":
                truth = Image.frombytes("L", truth.size, bytes((31*r+61*g+8*b)//100 for r,g,b in truth.getdata()))
            actual = Image.open(received).convert(truth.mode)
            stats = {"dimensions": actual.size, "pixel_sha256": hashlib.sha256(actual.tobytes()).hexdigest()}
            if actual.size == truth.size:
                errors = [abs(a-b) for a, b in zip(actual.tobytes(), truth.tobytes())]
                stats.update(maximum_component_error=max(errors, default=0),
                             mean_absolute_component_error=sum(errors)/len(errors),
                             unequal_components=sum(error != 0 for error in errors))
            check(f"picture-{index}-dimensions-and-pixels", {"dimensions": truth.size,
                  "pixel_sha256": hashlib.sha256(truth.tobytes()).hexdigest()}, stats,
                  actual.size == truth.size and actual.tobytes() == truth.tobytes(),
                  [str(received.relative_to(root))])
        frame_cursor = 0
        expected_starts = []
        expected_announcements = []
        prefix_ok = True
        for part in composition:
            contents_frames = []
            if part["kind"] == "mfsk":
                prefix = prefix_pcm(part["mode"], part["carrier_hz"], oracle)
                prefix_ok &= pcm[frame_cursor*2:frame_cursor*2+len(prefix)] == prefix
                contents = [c["utf8"].encode() if c["kind"] == "text" else ImageSource(
                    root / "inputs/primary-color-8x4.png", c["color"], c["samples_per_pixel"])
                    for c in part["contents"]]
                plan = plan_mfsk_segment(contents=contents, mode=part["mode"], carrier_hz=part["carrier_hz"], sample_rate_hz=48000)
                contents_frames = [frame_cursor + len(prefix)//2 + f for f in plan.content_start_frames]
                expected_announcements.extend(t.announcement.decode() for t in plan.picture_transitions)
                count = len(prefix)//2 + plan.frame_count
            elif part["kind"] == "silence":
                count = round(part["duration_seconds"] * 48000)
                check(f"silence-at-{frame_cursor}", "all-zero PCM", None,
                      pcm[frame_cursor*2:(frame_cursor+count)*2] == b"\0\0"*count,
                      [str((directory / "generated.wav").relative_to(root))], "encoder-defect")
            else:
                with wave.open(str(root / "inputs/audio-marker.wav")) as audio:
                    count = audio.getnframes()
                    audio_pcm = audio.readframes(count)
                check(f"audio-at-{frame_cursor}", "byte-exact copied PCM", None,
                      pcm[frame_cursor*2:(frame_cursor+count)*2] == audio_pcm,
                      [str((directory / "generated.wav").relative_to(root))], "encoder-defect")
            expected_starts.append({"input_index": len(expected_starts), "start_frame": frame_cursor,
                                    "contents": [{"content_index": i, "start_frame": f} for i, f in enumerate(contents_frames)]})
            frame_cursor += count
        check("independent-rsid-oracle-pcm", True, prefix_ok, prefix_ok,
              ["source/rsid-oracle.json", str((directory / "generated.wav").relative_to(root))], "encoder-defect")
        check("prefix-inclusive-frames-and-coordinates", {"frames": frame_cursor, "starts": expected_starts},
              {"frames": frames, "starts": record["segments_frames"]},
              frames == frame_cursor and record["segments_frames"] == expected_starts,
              [str((directory / "encoder-result.json").relative_to(root))], "encoder-defect")
        check("picture-announcements-exact", expected_announcements, text,
              all(a in text for a in expected_announcements), [str((extracted / "decoded.txt").relative_to(root))])
        status = "fail" if any(c["status"] == "fail" for c in checks) else "blocked" if any(c["status"] == "blocked" for c in checks) else "pass"
        cases.append({"id": run["id"], "status": status,
                      "generated_wav": artifact(directory / "generated.wav", root),
                      "encoder_result": artifact(directory / "encoder-result.json", root),
                      "continuous_receiver_runs": [{"input_interval": run["input_interval"], "manual_mode_changes": 0,
                          "exit_code": run["exit_code"], "log": artifact(logpath, root), "rxid_events": events,
                          "recovered_text": artifact(extracted / "decoded.txt", root),
                          "recovered_images": [artifact(p, root) for p in images]}],
                      "checks": checks, "discrepancies": discrepancies})
    summary = {"total": len(cases), "passed": sum(c["status"] == "pass" for c in cases),
               "failed": sum(c["status"] == "fail" for c in cases), "blocked": sum(c["status"] == "blocked" for c in cases)}
    inputs = [artifact(p, root) for p in sorted((root / "inputs").iterdir())]
    if reporting_schema is not None:
        shutil.copy(reporting_schema, root / "reporting-schema.json")
        inputs.append(artifact(root / "reporting-schema.json", root))
    manifest = {"schema": "grampy-mfsk-encoder-pi-qualification-manifest.v2",
                "status": "complete" if summary["passed"] == len(cases) else "failed" if summary["failed"] else "partial",
                "source": {"repository_revision": (root / "source/revision.txt").read_text().strip(),
                           "matrix": artifact(root / "source/matrix.json", root),
                           "rsid_oracle": artifact(root / "source/rsid-oracle.json", root),
                           "encoder_distribution": artifact(next((root / "source/distribution").glob("*.whl")), root),
                           "inputs": inputs},
                "target": identity["target"],
                "receiver": {"reference_id": matrix["receiver"]["reference_id"], "version": identity["receiver_version"],
                             "binary": artifact(root / "receiver-binary", root), "configuration": matrix["receiver"]},
                "execution": {"workflow": "tools/pi-qualify-mfsk-encoder.sh", "started_utc": identity["started_utc"],
                              "completed_utc": identity["completed_utc"], "log": artifact(root / "execution.log", root)},
                "cases": cases, "summary": summary}
    (root / "qualification-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify_artifacts(manifest, root)
    verify_cross_fields(manifest, matrix, root)
    schema = json.loads((root / ("reporting-schema.json" if reporting_schema is not None else "source/manifest-schema.json")).read_text())
    errors = [str(e) for e in jsonschema.Draft202012Validator(schema).iter_errors(manifest)]
    (root / "schema-validation.json").write_text(json.dumps({"valid": not errors, "errors": errors}, indent=2) + "\n")
    for case in cases:
        print(case["id"], case["status"], [c["id"] for c in case["checks"] if c["status"] != "pass"])
    print(json.dumps(summary), "schema_valid=", not errors)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None)
