# Python API

`grampy.api` is GramPy's supported callable interface. Import decoder entry
points from this module, rather than from pipeline, signal-processing, or
protocol modules. The command-line tool is an adapter around the same decode
operation.

## Decode a recording

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

if manifest["status"] == "complete":
    print(manifest["text_summary"]["text"])
else:
    for warning in manifest["warnings"]:
        print(f"{warning['code']}: {warning['message']}")
```

`meta_path` and `data_path` are the matching SigMF metadata JSON and binary IQ
files. GramPy accepts `ci16_le` and `cf32_le` interleaved little-endian I/Q
data. The input requirements are described in [the CLI guide](cli.md#input)
and apply equally to the Python API.

`start_sample` and `stop_sample`, when supplied, select a half-open interval:
the start is included and the stop is excluded. Omit both to process the whole
recording.

`artifact_dir` is the directory in which large decoded-picture artifacts may
be written. If it is omitted, a decode result can still contain inline small
rasters; a large picture instead makes the picture stage partial and adds a
warning. `artifact_path_prefix` is the path prefix recorded in artifact
entries; use a value relative to the manifest you plan to write, such as
`"decode.artifacts"`. GramPy does not write the returned manifest.
Applications choose whether and how to serialize it.

## Configuration

Pass `None` for `config` to use `DecodeConfig()` defaults. For normal use,
select the expected `mode`; all other defaults are the supported decoder
configuration.

| Option | Default | Meaning |
| --- | --- | --- |
| `mode` | `"MFSK32"` | Expected modulation: `"MFSK32"`, `"MFSK64"`, or `"auto"`. Automatic mode records acquisition evidence but does not yet decode segmented payloads. |
| `orientation` | `"unknown"` | Transmitted orientation hint: `"normal"`, `"reverse"`, or `"unknown"`. |
| `center_hz` | `None` | Optional positive center-frequency hint in Hz. |
| `block_samples` | `262_144` | Positive input-inspection block size. |
| `trace_level` | `"none"` | Diagnostic detail: `"none"`, `"summary"`, `"events"`, or `"full"`. |

`DecodeConfig` also exposes picture-estimation, persistent-tone, pipeline, and
resource-bound controls. They support decoder evaluation and benchmarking and
are not general tuning preferences. Their accepted values and defaults are
defined by the versioned [configuration schema](../../src/grampy/schemas/mfsk-decode-config-v1.json).
Use the defaults unless evaluating a specific decoder configuration.

## Result and status

`decode_iq` returns a JSON-compatible dictionary with
`schema == "grampy-decode-manifest.v1"`. It is validated before return against
the versioned [manifest schema](../../src/grampy/schemas/mfsk-decode-manifest-v1.json).

Consumer-facing fields are:

| Field | Meaning |
| --- | --- |
| `status` | `"complete"` when text framing contains both STX and a later EOT; otherwise `"partial"`. |
| `text_summary.text` | The decoded display text. It may be empty for a partial result. |
| `text_summary.octets` | Decoded byte values, in order. |
| `text_summary.framing` | Whether STX and EOT were found. |
| `pictures` | Decoded picture descriptors. A descriptor identifies either an inline raster or an artifact. |
| `artifacts` | Persisted picture artifacts, including relative path, SHA-256, size, and type/shape information. |
| `warnings` | Non-terminal decode conditions, each with a machine-readable `code` and human-readable `message`. |
| `recoverable_errors` | Per-result non-terminal errors. |
| `input` | Input identity, hashes, recording details, and requested interval. |
| `decoder.configuration` | The exact configuration used for this decode. |

The full schema also records acquisition evidence, text events, transitions,
diagnostics, and timing. It is useful for inspection and reproducibility, but
diagnostic substructures should not be treated as a stable application data
model unless a later schema revision documents them as such.

## Exceptions

Invalid SigMF metadata, unsupported formats, invalid intervals, and invalid
configuration values raise `ValueError`. Missing or unreadable input and
artifact paths raise `OSError`. Decode-stage problems that can be represented
in a result produce a partial manifest and an entry in `warnings` rather than
raising.

The CLI adds a separate operational behavior: when startup fails, it writes a
terminal-failure document to its requested output path. That file-writing
behavior is not part of `decode_iq`.
