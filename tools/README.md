# GramPy tools

This directory contains stable development, decoding, corpus, fixture, and
analysis commands. Run a tool from the repository root after creating the
repository virtual environment. The wrapper scripts select `.venv` and the
`src/` tree automatically; Python modules run directly should use the
environment shown in the root [README](../README.md).

For long-running work, use the managed Mac wrapper described in
[AGENTS.md](../AGENTS.md). Put a changing local batch under the change's
`.local/wip/<change-id>/` directory, then run:

```sh
tools/mac-local.sh .local/wip/CHANGE-ID/mac-command.sh
```

The wrapper records status and output under `.local/agent-runs/`. Consume
`result.md` after completion and remove only that completed run directory; do
not poll an active run.

Keep generated outputs in the same owned work directory and machine-private
configuration outside it. Follow the
[maintenance and closeout policy](../docs/operations/test-maintenance.md)
before promoting durable material and deleting owned scratch. The wrapper's
existing default batch path remains supported.

## Decode and analysis

Decode a SigMF IQ pair to a schema-validated manifest:

```sh
tools/mfsk-iq-decode \
  --in-meta capture.sigmf-meta \
  --in-data capture.sigmf-data \
  --out-manifest decode-manifest.json
```

This defaults to automatic mixed-mode decoding: RSID-derived MFSK32 and
MFSK64 segments are decoded in one run, including pictures in both modes.
Pass `--mode MFSK32` or `--mode MFSK64` only for a mode-constrained run.

Use `--start-sample` and `--stop-sample` for a half-open interval,
`--block-samples` to bound conversion memory, and
`--orientation normal|reverse|unknown` to state an orientation constraint.
The detailed input contract and manifest/artifact layout are in
[the SigMF decode guide](../docs/decoder/cli.md).

`tools/mfsk-accuracy` evaluates text and picture output against established
truth. For example:

```sh
tools/mfsk-accuracy text \
  --truth reviewed.txt \
  --decoded decoded.txt \
  --decoded-framing stx-eot \
  --output text-score.json

tools/mfsk-accuracy picture \
  --truth broadcaster.png \
  --decoded received.png \
  --output picture-score.json
```

`tools/wav-to-sigmf` converts a suitable WAV source into a SigMF pair.
`tools/analyze-mfsk-color-fixture` and `tools/mfsk-image-review` support
controlled fixture and image-review work. See each command’s `--help` output
for its full interface.

`tools/broadcast-regression` is the maintained full-broadcast quality gate.
Run it with the repository virtualenv through the managed wrapper and give
`--output` a new directory. It decodes the whole selected broadcasts, scores
GramPy and retained qualified fldigi output, rejects regression or incomplete
evidence and produces a portable HTML comparison page. The versioned policy
and baseline live under `tests/fixtures/`; see the
[broadcast workflow](../docs/operations/broadcast-regression.md).

## Fixtures

`tools/verify-sidecar` verifies required installed external data against the
committed inventory and rejects changed, missing or unclassified files. Add
`--include-history` to require and verify the optional archive. Run it with the
repository virtualenv through the managed wrapper. The
[sidecar guide](../docs/operations/sidecar-maintenance.md) covers provenance,
native fixture size budgets and the versioned S3 handoff.

`tools/test-suite --suite unit|controlled|received|all` selects an explicit
validation tier using the repository virtualenv. CI uses `unit`; `controlled`
and `all` perform a strict maintained-fixture preflight. Selected missing or
skipped data tests fail the run. See [test suite instructions](../tests/README.md)
for the versioned sidecar package and required inputs. Invoke through the
managed Mac wrapper, for example with `.venv/bin/python tools/test-suite --suite all`
in the local batch.

`tools/mfsk-fixture-inventory` reports the availability and hashes of optional
historical wire-spec fldigi-derived fixtures. Its default fixture root is
`.local/fldigi-fixtures`; set `GRAM_PY_MFSK_FIXTURES` or pass
`--fixture-root` to use another location. Missing optional artifacts are
reported but fail only with `--require-all`; hash mismatches always fail.

The existing fixture-generation `pi-*` scripts are retained helpers for
maintainers who already have a compatible environment. They are not the native
encoder's final receive-qualification workflow. The accepted practical
workflow uses `docs/encoder/data/mfsk_encoder_pi_matrix_v3.json` and
`tools/pi-qualify-mfsk-broadcast.sh`, invoked through `tools/pi-remote.sh`.
Its frozen numerical and PM visual acceptance are indexed in the
[encoder validation guide](../docs/encoder/validation.md).

`tools/pi-benchmark-mfsk-encoder.sh BUNDLE OUTPUT` installs a supplied wheel
into an isolated target using an explicitly supplied
`GRAMPY_BENCHMARK_PYTHON` runtime with the required dependencies. Run it through
the managed Pi wrapper. `tools/benchmark-mfsk-encoder.py` measures only the
public encoder call, in a fresh process per sample, and records CPU time,
wall time, emitted duration, peak process RSS and WAV bytes. Its bundle needs
`matrix.json`, `inputs/`, the benchmark script and a `distribution/` wheel.
Machine addresses and staging commands belong in `.local/`. The
[recorded performance procedure](../docs/encoder/validation.md) explains the
measurement boundaries and retained evidence.

The permanent encoder workflows have these roles:

| Role | Scripts |
| --- | --- |
| Practical receive qualification | `pi-qualify-mfsk-broadcast.sh` |
| Encoder performance measurements | `benchmark-mfsk-encoder.py`, `pi-benchmark-mfsk-encoder.sh` |
| Decoder picture regression on Pi | `pi-verify-mfsk-auto-pictures.sh` |
| Historical v2 qualification reproduction | `pi-qualify-mfsk-encoder.sh` |
| Historical picture/harness diagnosis | `pi-investigate-mfsk-pictures.sh`, `pi-inspect-mfsk-picture-artifacts.sh`, `pi-generate-mfsk-roundtrip-control.sh`, `pi-decode-mfsk-roundtrip-control.sh` |

Historical scripts remain useful provenance and reproduction aids. They are
not runtime dependencies or the normal accepted qualification route. One-off
transport commands, machine paths and installation targets stay in `.local/`.
The [post-project cleanup record](../docs/encoder/data/session10/cleanup.md)
describes retained evidence, archives and disposable caches.

## Received-IQ corpus

The optional received-IQ corpus is a local, self-contained directory at:

```text
tests/samples/received-corpus/
```

Use `tools/mfsk-corpus` to inventory source material, promote a reviewed
selection into a durable corpus, and verify a corpus. Its selection seed is
`docs/decoder/corpus/received_corpus_seed.json`; policy is in
`docs/decoder/mfsk_received_corpus.md`.

```sh
tools/mfsk-corpus verify --corpus tests/samples/received-corpus
```

To package the complete `tests/samples` sidecar, run `tools/package-corpus`.
It defaults to `.local/samples-<UTC-timestamp>.tar.zst` under this checkout.
`--encrypt` adds `.enc`. The timestamp is a snapshot label, separate from the
GramPy software version; hashes identify the actual contents. Both `--version`
and `--output` remain optional overrides, for example:

```sh
tools/package-corpus \
  --version 1.0 \
  --output /path/to/samples-1.0.tar.zst
```

Default filenames use the label with path separators replaced by underscores.
Existing output files are never overwritten. After publishing and verifying a
release, remove its exact local export file when no longer needed; exports are
not permanent machine configuration.

The command includes all installed sidecar directories, including optional
`archive/` history when present, verifies the committed inventory, and prints
the archive SHA-256. It puts the supplied release version and inventory
identity in `samples/sidecar-release.json` inside the archive without changing
source files or `received-corpus/version.json`. Add `--encrypt` for a
password-protected archive; no password is retained.

Install the whole sidecar with an explicitly supplied URL and checksum:

```sh
tools/fetch-corpus \
  --url 'https://example.invalid/samples-1.0.tar.zst' \
  --sha256 SHA256_FROM_PACKAGE_COMMAND
```

Add `--encrypted` to prompt for its password. Fetching verifies the downloaded
bytes, validates archive paths and contents before extraction, and atomically
replaces the entire installed `tests/samples` only after the extracted
release metadata and every included inventory file validate. Failure leaves the
previous installation intact. Successful replacement removes local-only files.
It does not retain a URL, checksum or password.

Use `--samples-root PATH` to select a different sidecar root; the existing
`--corpus-root` spelling remains an alias. Both commands accept `--manifest PATH`
for the matching inventory of another release. Older archives containing only
`received-corpus/` require `--received-only`, which uses the previous received-only
format and installation scope. They are never installed over the whole sidecar.

Packaging and fetching require `zstd`; encrypted archives also require
`openssl`.
