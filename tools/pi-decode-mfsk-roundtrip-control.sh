#!/bin/sh
# Fixed-mode receive control; invoke through tools/pi-remote.sh.
set -eu
adapter=${1:?usage: pi-decode-mfsk-roundtrip-control.sh ADAPTER INPUT OUTPUT}
input=${2:?usage: pi-decode-mfsk-roundtrip-control.sh ADAPTER INPUT OUTPUT}
output=${3:?usage: pi-decode-mfsk-roundtrip-control.sh ADAPTER INPUT OUTPUT}
binary=/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64/install/bin/fldigi
expected=dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3
test ! -e "$output"
test "$(sha256sum "$binary" | cut -d ' ' -f 1)" = "$expected"
test "$(sha256sum "$adapter" | cut -d ' ' -f 1)" = 89087547c53147702dd702705510f054d2adc3eb95d7fbed5fd48c46dd8ae418
mkdir -p "$output"
export PATH="$(dirname "$binary"):$PATH"
"$adapter" --input "$input" --output "$output/decode.tar" \
  --work-dir "$output/work" --config-dir "$output/config" \
  --mode MFSK64 --rxid off --afc off --audio-frequency-hz 1500 \
  --status-interval-sec 5 --post-playback-sec 15 --timeout-sec 180 \
  --debug-bundle full --nice 0 --audio-backend alsa-loopback \
  --alsa-capture-plugin plug
cp "$output/work/viewer.rgb" "$output/viewer.rgb"
cp "$output/work/viewer-gdb.log" "$output/viewer-gdb.log"
sha256sum "$binary" "$adapter" "$input" "$output/decode.tar" \
  >"$output/SHA256SUMS"
