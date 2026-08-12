#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="${1:-${RADIOGRAM_TARGET:-}}"
target_file="${RADIOGRAM_TARGET_FILE:-$root/.local/pi-target.env}"
remote_reference=/opt/radiogram/reference
remote_primary="$remote_reference/fixtures/mfsk64-primary-color-8x4-4.2.12"
remote_matrix="$remote_reference/fixtures/wire-matrix-4.2.12"
local_fixture_root="${GRAM_PY_MFSK_FIXTURES:-$root/.local/fldigi-fixtures}"
local_matrix="$local_fixture_root/wire-matrix-4.2.12"
binary="$remote_reference/fldigi-4.2.12/bin/fldigi"
expected_commit=b0032cabb70dc670064ed7561b9a626010a5e4ae
rsync_ssh="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=2"

if [ "${target:-}" = "--help" ] || [ "${target:-}" = "-h" ]; then
    cat <<EOF
usage: $0 [user@host]

Generate the four controlled fldigi v4.2.12 MFSK fixtures on the Pi, fetch
them under GRAM_PY_MFSK_FIXTURES (default .local/fldigi-fixtures), convert
their WAVs to analytic SigMF, and verify them against checked-in evidence.
EOF
    exit 0
fi
if [ -z "$target" ] && [ -f "$target_file" ]; then
    # shellcheck disable=SC1090
    . "$target_file"
    target="${RADIOGRAM_TARGET:-}"
fi
if [ -z "$target" ]; then
    printf 'usage: %s user@host\n' "$0" >&2
    exit 64
fi

# The primary wrapper also proves the source-image hash and pinned build.
"$root/tools/pi-generate-primary-mfsk-fixture.sh" "$target"

command_file=$(mktemp "${TMPDIR:-/tmp}/radiogram-mfsk-fixtures.XXXXXX")
cleanup() {
    rm -f "$command_file"
}
trap cleanup EXIT HUP INT TERM

sed \
    -e "s|@BINARY@|$binary|g" \
    -e "s|@COMMIT@|$expected_commit|g" \
    -e "s|@PRIMARY@|$remote_primary|g" \
    -e "s|@MATRIX@|$remote_matrix|g" \
    >"$command_file" <<'REMOTE'
set -eu
binary=@BINARY@
expected_commit=@COMMIT@
primary=@PRIMARY@
root=@MATRIX@
generator="$primary/fldigi-generate-wav"
image="$primary/primary-color-8x4.ppm"
result=/opt/radiogram/reference/fldigi-4.2.12-build.result

test -f "$result"
grep -qx 'status=complete' "$result"
grep -qx "commit=$expected_commit" "$result"
test -x "$binary"
test -x "$generator"
test -f "$image"
install -d -m 0755 "$root"

run_fixture() {
    name=$1
    shift
    out="$root/$name"
    install -d -m 0755 "$out"
    "$generator" \
        --fldigi "$binary" \
        --output "$out/transmission.wav" \
        --metadata "$out/transmission.json" \
        --carrier-hz 1500 \
        --timeout-sec 120 \
        --guard-sec 1 \
        --work-dir "$out/work" \
        "$@"
    sha256sum "$binary" "$out/transmission.wav" >"$out/SHA256SUMS"
}

run_fixture mfsk32-text-printable \
    --mode MFSK32 \
    --text 'RG-MFSK32 AaZz 09 .,!?/+-=: END'
run_fixture mfsk64-text-printable \
    --mode MFSK64 \
    --text 'RG-MFSK64 AaZz 09 .,!?/+-=: END'
run_fixture mfsk64-gray-8x4-p8 \
    --mode MFSK64 \
    --text 'RG-MFSK64-GRAY-8X4-P8' \
    --image "$image" \
    --grayscale on

cp "$result" "$root/fldigi-build.result"
printf '%s\n' 'status=complete' >"$root/generation.result"
REMOTE

printf '%s\n' '[pi-controlled-mfsk-fixtures] generating text and grayscale fixtures'
ssh -o BatchMode=yes -o ConnectTimeout=10 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=2 \
    "$target" "sudo -n sh -s" <"$command_file"

printf '%s\n' '[pi-controlled-mfsk-fixtures] fetching text and grayscale fixtures'
mkdir -p "$local_matrix"
rsync -az -e "$rsync_ssh" --rsync-path='sudo -n rsync' \
    "$target:$remote_matrix/" "$local_matrix/"

for directory in \
    "$local_matrix/mfsk32-text-printable" \
    "$local_matrix/mfsk64-text-printable" \
    "$local_matrix/mfsk64-gray-8x4-p8" \
    "$local_fixture_root/mfsk64-primary-color-8x4-4.2.12"
do
    PATH="$root/.venv/bin:$PATH" "$root/.venv/bin/python" "$root/tools/wav-to-sigmf" \
        --input "$directory/transmission.wav" \
        --out-data "$directory/transmission.sigmf-data" \
        --out-meta "$directory/transmission.sigmf-meta"
done

PYTHONPATH="$root/src" PATH="$root/.venv/bin:$PATH" \
    "$root/.venv/bin/python" -m grampy.fixture_cli \
    --fixture-root "$local_fixture_root" \
    --require-all
