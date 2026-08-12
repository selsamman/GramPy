#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="${1:-${RADIOGRAM_TARGET:-}}"
target_file="${RADIOGRAM_TARGET_FILE:-$root/.local/pi-target.env}"
remote_root=/opt/radiogram/reference/fixtures/mfsk64-primary-color-8x4-4.2.12
fixture_root="${GRAM_PY_MFSK_FIXTURES:-$root/.local/fldigi-fixtures}"
local_root="$fixture_root/mfsk64-primary-color-8x4-4.2.12"
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

generator="$root/tools/fldigi-generate-wav"
image="$root/tests/fixtures/mfsk/primary-color-8x4.ppm"
test -x "$generator"
test -f "$image"

printf '%s\n' '[pi-primary-mfsk-fixture] staging generator and image'
ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" \
    "sudo -n install -d -m 0755 '$remote_root'"
rsync -az -e "$rsync_ssh" --rsync-path='sudo -n rsync' \
    "$generator" "$image" "$target:$remote_root/"

printf '%s\n' '[pi-primary-mfsk-fixture] generating pinned fldigi WAV'
ssh -o BatchMode=yes -o ConnectTimeout=10 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=2 \
    "$target" "sudo -n sh -s" <<REMOTE
set -eu
result=/opt/radiogram/reference/fldigi-4.2.12-build.result
test -f "\$result"
grep -qx 'status=complete' "\$result"
grep -qx 'commit=$expected_commit' "\$result"
test -x "$binary"
"$remote_root/fldigi-generate-wav" \
    --fldigi "$binary" \
    --output "$remote_root/transmission.wav" \
    --metadata "$remote_root/transmission.json" \
    --mode MFSK64 \
    --carrier-hz 1500 \
    --text "RG-PRIMARY-MFSK64-COLOR-8X4" \
    --image "$remote_root/primary-color-8x4.ppm" \
    --grayscale off \
    --timeout-sec 120 \
    --guard-sec 1 \
    --work-dir "$remote_root/work"
cp "\$result" "$remote_root/fldigi-build.result"
sha256sum \
    "$binary" \
    "$remote_root/primary-color-8x4.ppm" \
    "$remote_root/transmission.wav" \
    >"$remote_root/SHA256SUMS"
REMOTE

printf '%s\n' '[pi-primary-mfsk-fixture] fetching fixture artifacts'
mkdir -p "$local_root"
rsync -az -e "$rsync_ssh" --rsync-path='sudo -n rsync' \
    "$target:$remote_root/" "$local_root/"
printf '%s\n' "$local_root"
