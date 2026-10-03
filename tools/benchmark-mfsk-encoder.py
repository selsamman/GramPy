"""Encoder-only timing; fresh process per sample, no receiver or audio device.

Run through the managed Mac/Pi wrapper. The bundle's matrix declares the
workload before execution. Only generated benchmark WAVs are removed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time
import wave

from grampy.api import (
    AudioPart, EncodeConfig, ImagePart, MfskSegment, SilencePart, TextFilePart,
    TextPart, encode_mfsk_wav,
)
import grampy.api


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def read_optional(path: str) -> str | None:
    try:
        return Path(path).read_text().strip().strip("\x00")
    except OSError:
        return None


def identity(bundle: Path) -> dict:
    package = Path(grampy.api.__file__).parent
    return {
        "architecture": platform.machine(), "platform": platform.platform(),
        "python": platform.python_version(),
        "device_model": read_optional("/proc/device-tree/model"),
        "dependencies": {name: metadata.version(name) for name in
                         ("radiogrampy", "numpy", "scipy", "Pillow", "jsonschema")},
        "package_source_hashes": {path.name: digest(path) for path in
                                  sorted(package.glob("*.py"))},
        "wheel_sha256": digest(next((bundle / "distribution").glob("*.whl"))),
        "matrix_sha256": digest(bundle / "matrix.json"),
        "inputs": {path.name: {"bytes": path.stat().st_size, "sha256": digest(path)}
                   for path in sorted((bundle / "inputs").iterdir()) if path.is_file()},
        "thread_environment": {name: os.environ.get(name) for name in
                               ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")},
    }


def thermal() -> dict:
    return {"temperature_millidegrees_c": read_optional(
                "/sys/class/thermal/thermal_zone0/temp"),
            "cpu0_frequency_khz": read_optional(
                "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")}


def parts_for(case: dict, inputs: Path) -> tuple:
    parts = []
    for spec in case["composition"]:
        if spec["kind"] == "mfsk":
            contents = []
            for content in spec["contents"]:
                if content["kind"] == "text":
                    contents.append(TextPart.from_text(content["utf8"]))
                elif content["kind"] == "text_file":
                    contents.append(TextFilePart(inputs / content["source"]))
                elif content["kind"] == "image":
                    contents.append(ImagePart(inputs / content["source"],
                        color=content["color"], samples_per_pixel=content["speed"]))
                else:
                    raise ValueError("unknown benchmark MFSK content")
            parts.append(MfskSegment(tuple(contents), spec["mode"], spec["carrier_hz"]))
        elif spec["kind"] == "audio":
            parts.append(AudioPart(inputs / spec["source"]))
        elif spec["kind"] == "silence":
            parts.append(SilencePart(spec["duration_seconds"]))
        else:
            raise ValueError("unknown benchmark part")
    return tuple(parts)


def worker(bundle: Path, output: Path, case_id: str, repeat: int) -> None:
    matrix = json.loads((bundle / "matrix.json").read_text())
    case = next(case for case in matrix["cases"] if case["id"] == case_id)
    parts = parts_for(case, bundle / "inputs")
    wav_path = output / f"{case_id}-{repeat}.wav"
    if wav_path.exists():
        raise FileExistsError(wav_path)
    before_thermal = thermal()
    before = resource.getrusage(resource.RUSAGE_SELF)
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    result = encode_mfsk_wav(parts=parts, output_path=wav_path,
                             config=EncodeConfig(sample_rate_hz=48000))
    wall_seconds = time.perf_counter() - wall_start
    cpu_seconds = time.process_time() - cpu_start
    after = resource.getrusage(resource.RUSAGE_SELF)
    after_thermal = thermal()
    # Capture peak RSS before validation; includes imports and encoder input.
    peak_bytes = after.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    with wave.open(str(wav_path), "rb") as wav:
        assert wav.getparams()[:3] == (1, 2, 48000)
        frames = wav.getnframes()
        assert result.duration_seconds == frames / 48000
        assert wav_path.stat().st_size == 44 + 2 * frames
        assert len(result.segments) == len(parts)
        for index, part in enumerate(parts):
            segment = result.segments[index]
            assert segment.input_index == index
            start = round(segment.start_seconds * 48000)
            stop = (round(result.segments[index + 1].start_seconds * 48000)
                    if index + 1 < len(parts) else frames)
            if isinstance(part, MfskSegment):
                assert [c.content_index for c in segment.contents] == list(range(len(part.parts)))
            elif isinstance(part, AudioPart):
                wav.setpos(start)
                with wave.open(str(part.path), "rb") as source:
                    assert stop - start == source.getnframes()
                    remaining = stop - start
                    while remaining:
                        count = min(32768, remaining)
                        assert wav.readframes(count) == source.readframes(count)
                        remaining -= count
            elif isinstance(part, SilencePart):
                assert stop - start == round(part.duration_seconds * 48000)
                wav.setpos(start)
                remaining = stop - start
                while remaining:
                    count = min(32768, remaining)
                    assert wav.readframes(count) == bytes(count * 2)
                    remaining -= count
    record = {
        "id": case_id, "repeat": repeat, "cpu_seconds": cpu_seconds,
        "user_cpu_seconds": after.ru_utime - before.ru_utime,
        "system_cpu_seconds": after.ru_stime - before.ru_stime,
        "wall_seconds": wall_seconds, "broadcast_seconds": result.duration_seconds,
        "cpu_to_broadcast_ratio": cpu_seconds / result.duration_seconds,
        "wall_to_broadcast_ratio": wall_seconds / result.duration_seconds,
        "peak_process_rss_bytes": peak_bytes, "wav_bytes": wav_path.stat().st_size,
        "wav_frames": frames, "wav_sha256": digest(wav_path),
        "temperature_frequency_before": before_thermal,
        "temperature_frequency_after": after_thermal,
        "wav_audio_silence_timestamps": "pass",
    }
    write_json(output / f"{case_id}-{repeat}.json", record)
    wav_path.unlink()  # Only this freshly generated, validated benchmark WAV.


def main(bundle: Path, output: Path, repeats: int) -> None:
    output.mkdir(parents=True, exist_ok=False)
    matrix = json.loads((bundle / "matrix.json").read_text())
    assert matrix["sample_rate_hz"] == 48000
    started = datetime.now(timezone.utc).isoformat()
    write_json(output / "identity.json", identity(bundle))
    samples, summaries = [], []
    for case in matrix["cases"]:
        records = []
        for repeat in range(1, repeats + 1):
            subprocess.run([sys.executable, str(Path(__file__).resolve()), str(bundle),
                str(output), "--worker", case["id"], "--repeat", str(repeat)], check=True)
            record = json.loads((output / f"{case['id']}-{repeat}.json").read_text())
            samples.append(record)
            records.append(record)
            print(f"{case['id']} sample={repeat} cpu={record['cpu_seconds']:.4f}s "
                  f"wall={record['wall_seconds']:.4f}s broadcast={record['broadcast_seconds']:.3f}s",
                  flush=True)
        summary = {"id": case["id"], "description": case["description"]}
        for key in ("cpu_seconds", "wall_seconds", "broadcast_seconds",
                    "cpu_to_broadcast_ratio", "wall_to_broadcast_ratio",
                    "peak_process_rss_bytes", "wav_bytes"):
            values = [row[key] for row in records]
            summary[key] = {"min": min(values), "median": statistics.median(values),
                            "max": max(values)}
        summaries.append(summary)
    write_json(output / "benchmark.json", {
        "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
        "repeats": repeats, "sample_rate_hz": 48000,
        "timing_scope": "encode_mfsk_wav only; process CPU (all threads) and elapsed wall; imports, setup and validation excluded",
        "rss_scope": "fresh worker process peak including imports, input inspection and encoding; before validation",
        "io_scope": "ordinary file writes through close; no fsync or cold-cache claim",
        "wav_retention": "validated benchmark WAVs removed; hashes, counts and metrics retained",
        "summaries": summaries, "samples": samples,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--worker")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.worker:
        worker(args.bundle.resolve(), args.output.resolve(), args.worker, args.repeat)
    else:
        main(args.bundle.resolve(), args.output.resolve(), args.repeats)
