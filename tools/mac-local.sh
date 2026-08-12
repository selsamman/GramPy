#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command_file="${1:-$root/.local/mac-command.sh}"
. "$root/tools/managed-run.sh"

log() { printf '[mac-local] %s\n' "$*"; }

if [ ! -x "$root/.venv/bin/python" ]; then
    printf 'missing repository Python: %s\n' "$root/.venv/bin/python" >&2
    exit 69
fi
if [ ! -f "$command_file" ]; then
    printf 'missing local command file: %s\n' "$command_file" >&2
    exit 66
fi
log "repository: $root"
log "command file: $command_file"
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$root/.venv/bin:$PATH"
export GRAMPY_REPOSITORY_ROOT="$root"
cd "$root"
managed_run mac-local /bin/sh "$command_file"
