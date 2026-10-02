#!/bin/sh
# Pi-side workflow. Stage the candidate bundle via tools/pi-remote.sh first.
set -eu
bundle=${1:?usage: pi-qualify-mfsk-encoder.sh BUNDLE OUTPUT}
output=${2:?usage: pi-qualify-mfsk-encoder.sh BUNDLE OUTPUT}
test ! -e "$output"
mkdir -p "$output"
python3 -m venv --system-site-packages "$output/venv"
"$output/venv/bin/python" -m pip install --no-deps --no-index "$bundle"/distribution/*.whl
unset PYTHONPATH
"$output/venv/bin/python" "$bundle/qualification.py" "$bundle" "$output"
