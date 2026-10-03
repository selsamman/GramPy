#!/bin/sh
# Sidecar investigation only; invoke through tools/pi-remote.sh.
set -eu
bundle=${1:?usage: pi-investigate-mfsk-pictures.sh BUNDLE OUTPUT}
output=${2:?usage: pi-investigate-mfsk-pictures.sh BUNDLE OUTPUT}
test ! -e "$output"
mkdir -p "$output"
python3 -m venv --system-site-packages "$output/venv"
"$output/venv/bin/python" -m pip install --no-deps --no-index "$bundle"/distribution/*.whl
unset PYTHONPATH
"$output/venv/bin/python" "$bundle/session9_probe.py" "$bundle" "$output"
