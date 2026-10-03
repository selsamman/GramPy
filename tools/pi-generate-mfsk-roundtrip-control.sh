#!/bin/sh
# Fresh unchanged-fldigi control. Invoke through tools/pi-remote.sh.
set -eu
bundle=${1:?usage: pi-generate-mfsk-roundtrip-control.sh BUNDLE OUTPUT}
output=${2:?usage: pi-generate-mfsk-roundtrip-control.sh BUNDLE OUTPUT}
binary=/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64/install/bin/fldigi
expected=dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3
test ! -e "$output"
test ! -d /tmp/radiogram-fldigi.lock
test "$(sha256sum "$binary" | cut -d ' ' -f 1)" = "$expected"
mkdir -p "$output"
"$bundle/fldigi-generate-wav" --fldigi "$binary" \
  --output "$output/fldigi-mfsk64-rgb-p8.wav" \
  --metadata "$output/transmission.json" \
  --mode MFSK64 --carrier-hz 1500 \
  --text 'GRAM PY ROUNDTRIP CONTROL MFSK64 RGB P8' \
  --image "$bundle/source-160x120.png" --grayscale off \
  --timeout-sec 240 --guard-sec 3 --xmlrpc-port 7364 \
  --work-dir "$output/work" --config-dir "$output/config"
cp "$output/work/arecord.stderr" "$output/arecord.stderr"
cp "$output/work/fldigi.stderr" "$output/fldigi.stderr"
cp "$output/work/fldigi.stdout" "$output/fldigi.stdout"
cp "$output/work/control.json" "$output/control.json"
cp "$output/work/asound.conf" "$output/asound.conf"
sha256sum "$binary" "$bundle/fldigi-generate-wav" \
  "$bundle/source-160x120.png" "$output/fldigi-mfsk64-rgb-p8.wav" \
  >"$output/SHA256SUMS"
