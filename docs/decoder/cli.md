# SigMF decode command

`tools/mfsk-iq-decode` is GramPy’s command-line adapter for reproducibly
decoding a SigMF IQ recording. The same decoder supplies compact application
products and optional diagnostic evidence.

## Input

Supply the SigMF metadata JSON and its matching binary IQ data explicitly:

```sh
tools/mfsk-iq-decode \
  --in-meta recording.sigmf-meta \
  --in-data recording.sigmf-data \
  --out-text-manifest results/text.manifest.json \
  --out-quality-manifest results/quality.manifest.json \
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

The default, `--mode auto`, detects RSID-governed MFSK32 and MFSK64 segments,
dispatches each segment to its matching text decoder, and decodes pictures from
the MFSK64 segments. Use `--mode MFSK32` or `--mode MFSK64` only to constrain a
diagnostic or compatibility run to one modulation.

Run `tools/mfsk-iq-decode --help` for the documented picture-estimation and
resource-bound controls. Those controls are decoder evaluation settings, not
general user preferences.

## Outputs

The two compact paths must be supplied together in one directory. The command
atomically writes each file. The text file contains readable ordered text and
picture items grouped by MFSK mode interval. The quality file contains
one-second rows of post-AGC signal, noise, and decode-confidence proxy values.
They share a run ID and input identity and are validated against their
[text](../../src/grampy/schemas/grampy-text-manifest-v1.json) and
[quality](../../src/grampy/schemas/grampy-quality-manifest-v1.json) schemas.

`--out-manifest results/decode.json` requests the large
[`grampy-decode-manifest.v1`](../../src/grampy/schemas/mfsk-decode-manifest-v1.json)
diagnostic file. It can be used alone for the prior CLI behavior, or with the
two compact paths; all three then come from one decode. The diagnostic file
is not assembled for a compact-only invocation.

Pictures have two storage forms:

- Small rasters are embedded as `inline_uint8_raster` values in the manifest.
- Large rasters are written beside the compact files under
  `<text-manifest-stem>.artifacts/`, for example:

  ```text
  results/
    text.manifest.json
    quality.manifest.json
    text.manifest.artifacts/
      raster-0001.png
      component-evidence-0001.npz
  ```

  The diagnostic manifest’s `artifacts` list records each PNG or NumPy `.npz` evidence
  file by stable ID, relative path, SHA-256, size, and relevant shape/type
  information. The `.npz` file is diagnostic component evidence; the PNG is
  the rendered decoded raster.

If no large picture is decoded, the artifact directory may not be created. No
persistent IQ intermediates are written.

If input validation or decode startup fails, each requested manifest path still
receives an atomic terminal-failure document. The process exits with a nonzero
status and the document records the input request, configuration, error kind,
message, and exit status.
