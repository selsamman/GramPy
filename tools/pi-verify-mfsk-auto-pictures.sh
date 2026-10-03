#!/bin/sh
# Staged decoder subset; invoke through tools/pi-remote.sh.
set -eu
bundle=${1:?usage: pi-verify-mfsk-auto-pictures.sh BUNDLE WAV_ROOT OUTPUT PYTHON}
wav_root=${2:?}
output=${3:?}
python=${4:?}
test -x "$python"
test ! -e "$output"
PYTHONPATH="$bundle/src" "$python" "$bundle/pi_decode.py" "$bundle/prepared.json" "$wav_root" "$output"
