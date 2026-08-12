#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="${RADIOGRAM_TARGET:-}"
target_file="${RADIOGRAM_TARGET_FILE:-$root/.local/pi-target.env}"
local_meta=
local_data=
mode=MFSK32
output_dir="$root/.local/r5/pi"

usage() {
    cat <<'EOF'
usage: tools/pi-test-mfsk-r5.sh --meta FILE --data FILE [options]

Options:
  --target USER@HOST
  --mode MFSK32|MFSK64
  --output-dir DIR
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --target) target=$2; shift 2 ;;
        --meta) local_meta=$2; shift 2 ;;
        --data) local_data=$2; shift 2 ;;
        --mode) mode=$2; shift 2 ;;
        --output-dir) output_dir=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'pi-test-mfsk-r5: unknown argument: %s\n' "$1" >&2; usage >&2; exit 64 ;;
    esac
done

if [ -z "$target" ] && [ -f "$target_file" ]; then
    # shellcheck disable=SC1090
    . "$target_file"
    target="${RADIOGRAM_TARGET:-}"
fi
test -n "$target" || { printf 'pi-test-mfsk-r5: missing target\n' >&2; exit 64; }
test -f "$local_meta" || { printf 'pi-test-mfsk-r5: missing metadata: %s\n' "$local_meta" >&2; exit 66; }
test -f "$local_data" || { printf 'pi-test-mfsk-r5: missing data: %s\n' "$local_data" >&2; exit 66; }
case "$mode" in MFSK32|MFSK64) ;; *) printf 'pi-test-mfsk-r5: invalid mode\n' >&2; exit 64 ;; esac

case_id=$(basename "$(dirname "$local_meta")")
remote_root="/var/tmp/radiogram-r5-$case_id"
remote_meta="$remote_root/capture.sigmf-meta"
remote_data="$remote_root/capture.sigmf-data"
remote_manifest="$remote_root/decode-$mode.json"
remote_resource="$remote_root/resource-$mode.txt"
ssh_options='ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=4'

mkdir -p "$output_dir"
printf '[pi-test-mfsk-r5] staging %s %s on %s\n' "$case_id" "$mode" "$target"
ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" \
    "mkdir -p '$remote_root' && df -h '$remote_root' && free -h"
rsync -a --progress -e "$ssh_options" "$local_meta" "$target:$remote_meta"
rsync -a --progress -e "$ssh_options" "$local_data" "$target:$remote_data"

printf '[pi-test-mfsk-r5] running deployed bounded decoder\n'
ssh -o BatchMode=yes -o ConnectTimeout=10 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=4 "$target" \
    "set -eu
     {
       echo '== before =='
       date -u
       free -h
       vcgencmd measure_temp 2>/dev/null || true
       vcgencmd get_throttled 2>/dev/null || true
       /usr/bin/time -v env PYTHONPATH=/opt/radiogram/current/src \
         python3 -m grampy.cli \
         --in-meta '$remote_meta' \
         --in-data '$remote_data' \
         --out-manifest '$remote_manifest' \
         --mode '$mode' \
         --trace-level summary
       echo '== after =='
       date -u
       free -h
       vcgencmd measure_temp 2>/dev/null || true
       vcgencmd get_throttled 2>/dev/null || true
     } >'$remote_resource' 2>&1"

rsync -a -e "$ssh_options" "$target:$remote_manifest" \
    "$output_dir/$case_id-$mode.json"
rsync -a -e "$ssh_options" "$target:$remote_resource" \
    "$output_dir/$case_id-$mode.resource.txt"
printf '[pi-test-mfsk-r5] fetched results to %s\n' "$output_dir"
