#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_file="${GRAMPY_TARGET_FILE:-$root/.local/pi-target.env}"
command_file="${1:-$root/.local/pi-command.sh}"
. "$root/tools/managed-run.sh"

log() { printf '[pi-remote] %s\n' "$*"; }

if [ ! -f "$target_file" ]; then
    printf 'missing Pi target file: %s\n' "$target_file" >&2
    exit 66
fi
. "$target_file"
target="${GRAMPY_TARGET:-}"
if [ -z "$target" ]; then
    printf 'GRAMPY_TARGET is not set in %s\n' "$target_file" >&2
    exit 65
fi
if [ ! -f "$command_file" ]; then
    printf 'missing remote command file: %s\n' "$command_file" >&2
    exit 66
fi
log "target: $target"
log "command file: $command_file"
run_remote() {
    ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=2 "$target" 'sudo -n sh -s' <"$command_file"
}
managed_run pi-remote run_remote
