#!/bin/sh
# Receive a frozen large-image bundle; invoke through tools/pi-remote.sh.
set -eu
bundle=${1:?usage: pi-qualify-mfsk-broadcast.sh BUNDLE OUTPUT ADAPTER BINARY PYTHON}
output=${2:?}
adapter=${3:?}
binary=${4:?}
python=${5:?}
test ! -e "$output"
test -x "$python"
test "$(sha256sum "$binary" | cut -d ' ' -f 1)" = dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3
test "$(sha256sum "$adapter" | cut -d ' ' -f 1)" = 89087547c53147702dd702705510f054d2adc3eb95d7fbed5fd48c46dd8ae418
mkdir -p "$output"
"$python" "$bundle/session9_broadcast_receive.py" "$bundle" "$output" "$adapter" "$binary"
