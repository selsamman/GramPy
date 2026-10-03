#!/bin/sh
# Pi-side workflow; stage and invoke through tools/pi-remote.sh.
set -eu
bundle=${1:?usage: pi-benchmark-mfsk-encoder.sh BUNDLE OUTPUT}
output=${2:?usage: pi-benchmark-mfsk-encoder.sh BUNDLE OUTPUT}
runtime=${GRAMPY_BENCHMARK_PYTHON:?set an explicit Python runtime with dependencies}
test ! -e "$output"
site="$bundle/installed-wheel"
test ! -e "$site"
"$runtime" -m pip install --no-deps --no-index --target "$site" "$bundle"/distribution/*.whl
export PYTHONPATH="$site"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
"$runtime" "$bundle/benchmark-mfsk-encoder.py" "$bundle" "$output" --repeats 2
