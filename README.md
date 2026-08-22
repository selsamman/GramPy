# GramPy

GramPy is an importable Python library and command-line tooling for decoding
MFSK32 and MFSK64 transmissions from SigMF IQ recordings. It is maintained as
a standalone project after its extraction from Radiogram.

The PyPI distribution name is `radiogrampy`; its Python import name is
`grampy`.

Python 3.11 or newer is required.

## Use as a library

The supported Python interface is `grampy.api`. Decode a SigMF metadata/data
pair by passing `pathlib.Path` objects to `decode_iq`:

```python
from pathlib import Path

from grampy.api import DecodeConfig, decode_iq

manifest = decode_iq(
    meta_path=Path("recording.sigmf-meta"),
    data_path=Path("recording.sigmf-data"),
    config=DecodeConfig(mode="MFSK64"),
    artifact_dir=Path("results/decode.artifacts"),
    artifact_path_prefix="decode.artifacts",
)

print(manifest["status"])
print(manifest["text_summary"]["text"])
```

`decode_iq` returns a validated, JSON-compatible decode manifest; it does not
write that manifest to disk. The optional artifact arguments control where
large decoded-picture artifacts are written. See [the Python API guide](https://github.com/selsamman/GramPy/blob/master/docs/decoder/api.md)
for the supported arguments, configuration, result contract, errors, and
artifact behavior. The [manifest schema](https://github.com/selsamman/GramPy/blob/master/src/grampy/schemas/mfsk-decode-manifest-v1.json)
is the machine-readable format reference.

## Setup

Create a virtual environment and install GramPy with its runtime dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --editable . pillow
```

`Pillow` is used by the image-related test suite. The repository uses a `src/`
layout, so run Python work with both the virtual environment and source tree
selected:

```sh
PYTHONPATH="$PWD/src" PATH="$PWD/.venv/bin:$PATH" \
  .venv/bin/python -m unittest discover -s tests
```

For full-suite runs, experiments, corpus jobs, or other potentially long work,
follow the managed-execution contract in [AGENTS.md](https://github.com/selsamman/GramPy/blob/master/AGENTS.md). The normal Mac
entry point is `tools/mac-local.sh`; place a temporary command batch in the
ignored `.local/mac-command.sh` when needed.

## Tests and corpus

The normal regression suite runs without large external artifacts. Tests that
need received IQ or controlled generated fixtures skip cleanly when those
optional inputs are absent.

See [tests/README.md](https://github.com/selsamman/GramPy/blob/master/tests/README.md) to install an optional received-IQ
corpus, point tests at an existing corpus, or package one for controlled
distribution. Large samples are never committed to this repository.

## Decode a SigMF recording

GramPy includes a command-line adapter for reproducible decoder work on a
SigMF metadata/data pair:

```sh
tools/mfsk-iq-decode \
  --in-meta recording.sigmf-meta \
  --in-data recording.sigmf-data \
  --out-manifest results/decode.json \
  --mode MFSK64
```

The command writes a manifest containing the decoded text, diagnostics, and
artifact inventory. Large decoded pictures are written beside it in
`results/decode.artifacts/`; small rasters are embedded in the manifest. See
[the SigMF decode guide](https://github.com/selsamman/GramPy/blob/master/docs/decoder/cli.md) for the accepted metadata, input
formats, interval options, and complete output layout.

## Development

Use [docs/operations/change-management-v1.md](https://github.com/selsamman/GramPy/blob/master/docs/operations/change-management-v1.md)
for continuous-improvement work. It defines the request, baseline, candidate,
evaluation, acceptance, and closeout cycle. Decoder architecture, contracts,
validation guidance, and the accepted baseline are indexed in
[docs/decoder/README.md](https://github.com/selsamman/GramPy/blob/master/docs/decoder/README.md).

Reusable command-line tools are documented in [tools/README.md](https://github.com/selsamman/GramPy/blob/master/tools/README.md).
