#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="${1:-${RADIOGRAM_TARGET:-}}"
target_file="${RADIOGRAM_TARGET_FILE:-$root/.local/pi-target.env}"
remote_root=/opt/radiogram/reference/fixtures/session10f-matrix-4.2.12
local_root="${GRAM_PY_MFSK_FIXTURES:-$root/.local/fldigi-fixtures}/session10f-matrix-4.2.12"
source_root="$root/.local/session10f-fixture-sources"
source_ppm="$source_root/boundary-best-160x120.ppm"
binary=/opt/radiogram/reference/fldigi-4.2.12/bin/fldigi
expected_commit=b0032cabb70dc670064ed7561b9a626010a5e4ae
rsync_ssh="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=2"

if [ -z "$target" ] && [ -f "$target_file" ]; then
    # shellcheck disable=SC1090
    . "$target_file"
    target="${RADIOGRAM_TARGET:-}"
fi
if [ -z "$target" ]; then
    printf 'usage: %s user@host\n' "$0" >&2
    exit 64
fi

PYTHONPATH="$root/src" PATH="$root/.venv/bin:$PATH" \
    "$root/.venv/bin/python" \
    "$root/tests/fixtures/mfsk/generate_session10f_boundary_source.py" \
    --output "$source_ppm"

printf '%s\n' '[pi-session10f-fixtures] staging generator and source image'
ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" \
    "sudo -n install -d -m 0755 '$remote_root'"
rsync -az -e "$rsync_ssh" --rsync-path='sudo -n rsync' \
    "$root/tools/fldigi-generate-wav" "$source_ppm" \
    "$target:$remote_root/"

printf '%s\n' '[pi-session10f-fixtures] generating MFSK32 p8 boundary fixture'
ssh -o BatchMode=yes -o ConnectTimeout=10 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=2 \
    "$target" "sudo -n sh -s" <<REMOTE
set -eu
result=/opt/radiogram/reference/fldigi-4.2.12-build.result
out=$remote_root/mfsk32-boundary-best-160x120-p8
test -f "\$result"
grep -qx 'status=complete' "\$result"
grep -qx 'commit=$expected_commit' "\$result"
test -x "$binary"
install -d -m 0755 "\$out"
"$remote_root/fldigi-generate-wav" \
    --fldigi "$binary" \
    --output "\$out/transmission.wav" \
    --metadata "\$out/transmission.json" \
    --mode MFSK32 \
    --carrier-hz 1500 \
    --text 'RG-SESSION10F-MFSK32-BOUNDARY-BEST-160X120-P8' \
    --image "$remote_root/boundary-best-160x120.ppm" \
    --grayscale off \
    --timeout-sec 180 \
    --guard-sec 1 \
    --work-dir "\$out/work"
sha256sum "$binary" "$remote_root/boundary-best-160x120.ppm" \
    "\$out/transmission.wav" >"\$out/SHA256SUMS"

out=$remote_root/mfsk32-boundary-best-160x120-p8-8khz
install -d -m 0755 "\$out"
"$remote_root/fldigi-generate-wav" \
    --fldigi "$binary" \
    --output "\$out/transmission.wav" \
    --metadata "\$out/transmission.json" \
    --mode MFSK32 \
    --carrier-hz 1500 \
    --text 'RG-SESSION10F-MFSK32-BOUNDARY-BEST-160X120-P8-8KHZ' \
    --image "$remote_root/boundary-best-160x120.ppm" \
    --grayscale off \
    --wav-rate-hz 8000 \
    --timeout-sec 180 \
    --guard-sec 1 \
    --work-dir "\$out/work"
sha256sum "$binary" "$remote_root/boundary-best-160x120.ppm" \
    "\$out/transmission.wav" >"\$out/SHA256SUMS"
REMOTE

printf '%s\n' '[pi-session10f-fixtures] fetching fixture'
mkdir -p "$local_root"
rsync -az -e "$rsync_ssh" --rsync-path='sudo -n rsync' \
    "$target:$remote_root/" "$local_root/"

for fixture_name in \
    mfsk32-boundary-best-160x120-p8 \
    mfsk32-boundary-best-160x120-p8-8khz
do
    fixture="$local_root/$fixture_name"
    PATH="$root/.venv/bin:$PATH" "$root/.venv/bin/python" \
        "$root/tools/wav-to-sigmf" \
        --input "$fixture/transmission.wav" \
        --out-data "$fixture/transmission.sigmf-data" \
        --out-meta "$fixture/transmission.sigmf-meta"
    PYTHONPATH="$root/src" PATH="$root/.venv/bin:$PATH" \
        "$root/.venv/bin/python" "$root/tools/analyze-mfsk-color-fixture" \
        --wav "$fixture/transmission.wav" \
        --ppm "$source_ppm" \
        --output "$fixture/analysis.json" \
        --bandwidth-hz 468.75
    printf '%s\n' "$fixture"
done
