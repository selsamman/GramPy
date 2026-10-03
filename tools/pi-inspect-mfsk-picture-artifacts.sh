#!/bin/sh
# Whole-WAV diagnostic only. Invoke through tools/pi-remote.sh.
set -eu
if [ "$#" -ne 5 ]; then
    printf 'usage: pi-inspect-mfsk-picture-artifacts.sh BUNDLE PYTHON SOURCE PAIRED OUTPUT\n' >&2
    exit 64
fi
bundle=$1
python=$2
source=$3
paired=$4
output=$5
test ! -e "$output"
unset PYTHONPATH
"$python" "$bundle/session9_wholewav.py" "$bundle" "$source" "$paired" "$output"
