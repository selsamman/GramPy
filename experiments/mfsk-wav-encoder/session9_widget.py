"""Read stable picture-widget buffers without stopping receiver playback.

Layout comes from the pinned binary's own debug symbols. The final sample
must independently equal a post-playback gdb dump before evidence is used.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from PIL import Image


def main():
    binary, config, work = map(Path, sys.argv[1:4])
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == "dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3"
    expression = ('printf "LAYOUT %llu %llu %llu %llu %llu\\n", '
                  '(unsigned long)&picRx, (unsigned long)&((picture*)0)->vidbuf, '
                  '(unsigned long)&((picture*)0)->width, (unsigned long)&((picture*)0)->height, '
                  '(unsigned long)&((picture*)0)->bufsize')
    layout_run = subprocess.run(["gdb", "-q", "-nx", "-batch", str(binary), "-ex", expression],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
    (work / "viewer-layout.log").write_text(layout_run.stdout)
    match = re.search(r"LAYOUT (\d+) (\d+) (\d+) (\d+) (\d+)", layout_run.stdout)
    assert layout_run.returncode == 0 and match, layout_run.stdout
    symbol, buffer_offset, width_offset, height_offset, size_offset = map(int, match.groups())
    started, pid = time.monotonic(), None
    while time.monotonic() < started+40 and pid is None:
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit(): continue
            try:
                args = (proc / "cmdline").read_bytes().split(b"\0")
                if not args or Path(args[0].decode()).name != "fldigi" or b"--config-dir" not in args: continue
                if args[args.index(b"--config-dir")+1].decode() == str(config): pid = int(proc.name)
            except (OSError, ValueError, UnicodeError): pass
        if pid is None: time.sleep(.1)
    assert pid is not None, "receiver process unavailable"
    header = binary.read_bytes()[:20]
    assert header[:6] == b"\x7fELF\x02\x01", "requires pinned little-endian ELF64 binary"
    elf_type = int.from_bytes(header[16:18], "little")
    assert elf_type in (2, 3)
    mappings = []
    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 6 and fields[-1] == str(binary):
            mappings.append(int(fields[0].split("-")[0], 16)-int(fields[2], 16))
    assert mappings, "receiver binary mapping unavailable"
    global_address = symbol + (min(mappings) if elf_type == 3 else 0)
    out = work / "viewer-captures"
    out.mkdir()
    descriptor = os.open(f"/proc/{pid}/mem", os.O_RDONLY)
    previous, last_saved, captures = None, None, []
    changed_at = time.monotonic()
    def integer(address, length):
        data = os.pread(descriptor, length, address)
        assert len(data) == length
        return int.from_bytes(data, "little")
    try:
        while not (work / "viewer-capture.done").exists():
            picture, pixels = integer(global_address, 8), None
            if picture:
                geometry = tuple(integer(picture+offset, 4) for offset in (width_offset, height_offset, size_offset))
                if geometry == (8, 4, 96):
                    buffer = integer(picture+buffer_offset, 8)
                    pixels = os.pread(descriptor, 96, buffer)
                    assert len(pixels) == 96
            now = time.monotonic()
            if pixels != previous: previous, changed_at = pixels, now
            if pixels is not None and any(pixels) and now-changed_at >= 1 and pixels != last_saved:
                filename = f"viewer-{len(captures):02d}.png"
                Image.frombytes("RGB", (8, 4), pixels).save(out / filename)
                captures.append({"path": filename, "stable_for_seconds": now-changed_at,
                                 "elapsed_seconds": now-started, "pixel_sha256": hashlib.sha256(pixels).hexdigest()})
                last_saved = pixels
                (out / "captures.json").write_text(json.dumps(captures, indent=2)+"\n")
            time.sleep(.1)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    main()
