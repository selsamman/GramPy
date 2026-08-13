# GramPy tools

This directory contains stable development, decoding, corpus, fixture, and
analysis commands. Run a tool from the repository root after creating the
repository virtual environment. The wrapper scripts select `.venv` and the
`src/` tree automatically; Python modules run directly should use the
environment shown in the root [README](../README.md).

For long-running work, use the managed Mac wrapper described in
[AGENTS.md](../AGENTS.md). Put a changing local batch in
`.local/mac-command.sh`, then run:

```sh
tools/mac-local.sh
```

The wrapper records status and output under `.local/agent-runs/`. Consume
`result.md` after completion and remove only that completed run directory; do
not poll an active run.

## Decode and analysis

Decode a SigMF IQ pair to a schema-validated manifest:

```sh
tools/mfsk-iq-decode \
  --in-meta capture.sigmf-meta \
  --in-data capture.sigmf-data \
  --out-manifest decode-manifest.json
```

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

## Fixtures

`tools/mfsk-fixture-inventory` reports the availability and hashes of optional
controlled fldigi-derived fixtures. Its default fixture root is
`.local/fldigi-fixtures`; set `GRAM_PY_MFSK_FIXTURES` or pass
`--fixture-root` to use another location. Missing optional artifacts are
reported but fail only with `--require-all`; hash mismatches always fail.

The `pi-*` scripts are retained fixture-generation helpers for maintainers who
already have a compatible environment. They are not part of GramPy’s supported
test or release process, and GramPy has no Pi acceptance-test requirement.

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

To share a corpus outside Git, package it explicitly:

```sh
tools/package-corpus \
  --version 1.0 \
  --output /path/to/received-corpus-1.0.tar.zst
```

The command writes the specified version to the local corpus’s `version.json`
and prints the archive SHA-256. Add `--encrypt` to create a password-protected
archive; no password is retained.

Install a corpus only with an explicitly supplied URL and checksum:

```sh
tools/fetch-corpus \
  --url 'https://example.invalid/received-corpus-1.0.tar.zst' \
  --sha256 SHA256_FROM_PACKAGE_COMMAND
```

Add `--encrypted` to prompt for its password. Fetching verifies the downloaded
bytes, validates archive paths and contents before extraction, and atomically
replaces the installed corpus only after validation succeeds. It deliberately
does not retain a URL, checksum, password, or automatic corpus-version policy.

Packaging and fetching require `zstd`; encrypted archives also require
`openssl`.
