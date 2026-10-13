#!/bin/sh
set -eu

# Remote command file: run through tools/pi-remote.sh, not directly on the Mac.

unit=grampy-fldigi-rpc
config_dir=/home/pi/.config/grampy-fldigi-rpc
fldigi_bin=/opt/radiogram/reference/fldigi-4.2.12/bin/fldigi

if ss -ltn '( sport = :7362 )' | grep -q ':7362'; then
    printf 'RPC port 7362 is already in use; leaving it untouched\n' >&2
    exit 1
fi

systemd-run --unit="$unit" \
    --property=User=pi \
    --property=Group=pi \
    --property=WorkingDirectory=/home/pi \
    --property=Restart=on-failure \
    --property=IPAddressDeny=any \
    --property=IPAddressAllow=localhost \
    /usr/bin/xvfb-run -a "$fldigi_bin" \
    --config-dir "$config_dir" \
    --xmlrpc-server-address 127.0.0.1 \
    --xmlrpc-server-port 7362 \
    --xmlrpc-allow '127\.0\.0\.1'

attempt=0
while [ "$attempt" -lt 30 ]; do
    if ss -ltn '( sport = :7362 )' | grep -q ':7362'; then
        break
    fi
    if ! systemctl is-active --quiet "$unit"; then
        systemctl status "$unit" --no-pager -l || true
        journalctl -u "$unit" -n 40 --no-pager || true
        exit 1
    fi
    sleep 1
    attempt=$((attempt + 1))
done

python3 - <<'PY'
import xmlrpc.client

rpc = xmlrpc.client.ServerProxy('http://127.0.0.1:7362/', allow_none=True)
print('fldigi version via RPC:', rpc.fldigi.version())
print('RPC methods:', len(rpc.system.listMethods()))
PY

systemctl show "$unit" -p ActiveState -p IPAddressAllow -p IPAddressDeny
ss -ltn '( sport = :7362 )'
