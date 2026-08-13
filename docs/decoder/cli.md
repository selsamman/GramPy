# SigMF decode command

`tools/mfsk-iq-decode` is GramPy’s command-line adapter for reproducibly
decoding a SigMF IQ recording. It is primarily a development, validation, and
benchmark tool. The future public Python-library consumption guide will be
added with the PyPI release.

## Input

Supply the SigMF metadata JSON and its matching binary IQ data explicitly:

```sh
tools/mfsk-iq-decode \
  --in-meta recording.sigmf-meta \
  --in-data recording.sigmf-data \
  --out-manifest results/decode.json \
  --mode MFSK64
```

GramPy currently accepts interleaved little-endian I/Q samples in either of
these SigMF datatypes:

- `ci16_le`: signed 16-bit integer I and Q values;
- `cf32_le`: 32-bit floating-point I and Q values.

The metadata must be JSON with:

```json
{
  "global": {
    "core:datatype": "ci16_le",
    "core:sample_rate": 48000
  },
  "captures": [
    {"core:sample_start": 0}
  ]
}
```

`core:sample_rate` must be finite and positive. At least one capture must have
a valid non-negative `core:sample_start` that establishes the requested input
interval. The binary data size must be aligned to the declared datatype.
`core:datetime` and `core:frequency` are recommended capture fields; their
absence is recorded as a warning, not an input failure.

Use `--start-sample` and `--stop-sample` to decode a half-open interval. Omit
them to decode the whole input. `--block-samples` controls bounded input
inspection and conversion work.

Select the expected modulation with `--mode MFSK32` or `--mode MFSK64`.
`MFSK32` is the current default. `--mode auto` records acquisition evidence,
but segmented payload decoding is not yet implemented, so it is not the choice
when decoded text or pictures are required.

Run `tools/mfsk-iq-decode --help` for the documented picture-estimation and
resource-bound controls. Those controls are decoder evaluation settings, not
general user preferences.

## Outputs

The command atomically writes the requested manifest path. A successful
manifest contains the input hashes and interval, configuration, diagnostics,
decoded text summaries and events, picture descriptions, timing/resource
measurements, warnings, and artifact inventory. It is validated against
[`mfsk-decode-manifest-v1.json`](../../src/grampy/schemas/mfsk-decode-manifest-v1.json).

Decoded text is represented in the manifest; no separate text file is created.

Pictures have two storage forms:

- Small rasters are embedded as `inline_uint8_raster` values in the manifest.
- Large rasters are written beside the manifest under
  `<manifest-stem>.artifacts/`, for example:

  ```text
  results/
    decode.json
    decode.artifacts/
      raster-0001.png
      component-evidence-0001.npz
  ```

  The manifest’s `artifacts` list records each PNG or NumPy `.npz` evidence
  file by stable ID, relative path, SHA-256, size, and relevant shape/type
  information. The `.npz` file is diagnostic component evidence; the PNG is
  the rendered decoded raster.

If no large picture is decoded, the artifact directory may not be created. No
persistent IQ intermediates are written.

If input validation or decode startup fails, the requested manifest path still
receives an atomic terminal-failure document. The process exits with a nonzero
status and the document records the input request, configuration, error kind,
message, and exit status.
