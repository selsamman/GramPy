#!/bin/sh
set -eu

# Remote command file: run through tools/pi-remote.sh, not directly on the Mac.

if systemctl is-active --quiet grampy-fldigi-rpc.service; then
    systemctl stop grampy-fldigi-rpc.service
    printf '%s\n' 'Stopped temporary fldigi RPC service.'
else
    printf '%s\n' 'Temporary fldigi RPC service was not active.'
fi
ss -ltn '( sport = :7362 )'
