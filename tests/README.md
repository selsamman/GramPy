# Tests

Run from the repository root with the repository virtualenv and managed wrapper
required by [AGENTS.md](../AGENTS.md). Use the change's
`.local/wip/<change-id>/` directory for command files and temporary outputs.
The [maintenance policy](../docs/operations/test-maintenance.md) defines test
creation, replacement/retirement, validation selection and promotion of
required inputs before closeout cleanup. Put the selected command in a batch:

```sh
PYTHONPATH="$PWD/src" PATH="$PWD/.venv/bin:$PATH" \
  .venv/bin/python tools/test-suite --suite all
```

Choose the validation tier explicitly:

Repository fixtures and checkout-only tests must use independently authored
inputs and expectations. Do not copy content from `tests/samples` into a
committed test, fixture or expected value. Broadcast-origin and uncertain-origin
material, including excerpts, decoded text/images and transformed derivatives,
remains external regardless of size. External-data tests may reference that
material without embedding it. Sidecar-to-Git moves require a recorded
provenance review; see the [maintenance policy](../docs/operations/test-maintenance.md).

| Tier | Inputs | Missing data |
| --- | --- | --- |
| `--suite unit` | Checkout, dependencies and generated temporary inputs | No external corpus required; CI and generic package release use this tier. |
| `--suite controlled` | The versioned controlled fixture sidecar described below | Strict preflight fails before decoding if any required input is missing or changed. |
| `--suite received` | The received-IQ sidecar and saved-manifest compatibility case | Missing required inputs fail; unavailable independent image truth is handled separately by scoring policy. |
| `--suite all` | Both sidecars | Runs every selected check, with no accepted skips. |

The runner prints selected and explicitly excluded counts. Other-tier tests are
not reported as passes or skips. A selected test that skips makes the run fail.
Raw `unittest discover -s tests` is also a full-data run; its required-data tests
fail when inputs are absent. Unit CI is not a decoder-quality acceptance gate.

For the separate long-running quality acceptance, put this in a managed Mac batch:

```sh
.venv/bin/python tools/broadcast-regression --output .local/wip/CHANGE-ID/broadcast-01
```

This freshly decodes four entire broadcasts, produces paired GramPy/fldigi
scorecards, enforces per-capture/per-picture regression limits and writes
`review/index.html` for comparison. Missing inputs fail; changed images require
human review. See the [broadcast workflow](../docs/operations/broadcast-regression.md)
for baseline provenance, exit statuses and deliberate requalification.

## External data inventory

See the [sidecar maintenance guide](../docs/operations/sidecar-maintenance.md)
for provenance rules, the Git size budget and a versioned S3 handoff. The
committed [inventory](fixtures/sidecar-v1.json) identifies required data and
optional history. Run `tools/verify-sidecar` through the managed Mac wrapper
to verify required inputs, or add `--include-history` for the full archive.
The received text expectations are external, with their identity binding in
[received-expectations.json](fixtures/received-expectations.json).

## Controlled fixtures

The required four cases are installed under `tests/samples/controlled-mfsk-v1/`:
MFSK32 text, MFSK64 text, and MFSK64 8x4 grayscale/colour p8 pictures. Override
the samples parent with `GRAMPY_TEST_SAMPLES`, or the controlled directory itself
with `GRAM_PY_MFSK_FIXTURES`.

Their current identities and independently measured timing are in
[`controlled-v1.json`](fixtures/mfsk/controlled-v1.json). The original
`docs/decoder/data/mfsk_fixture_evidence.json` and packaged copy remain historical
wire-spec evidence; they are not silently repinned as new recordings.

The portable archive `archive/distribution/controlled-mfsk-v1-20261012.tar.gz`
is an optional immutable distribution copy. A normal sidecar installation
supplies the extracted `controlled-mfsk-v1/` directory. Its SHA-256 is:

```text
f0cebf1b048b398c8e743216e2594d0e1e2683be871c594530c2ff62ffc0eadb
```

To install into an absent directory, obtain that archive with the sidecar,
verify the SHA-256 above (also recorded in the committed manifest), create
`tests/samples` if needed, and unpack the archive there. Its top-level directory
is `controlled-mfsk-v1`. Do not overwrite a different fixture version. Then run
the strict controlled suite through the managed wrapper. The repository does
not invent or automatically select a remote download location.

The archive contains WAV/IQ/portable metadata plus compact independent receiver
results and its manifest. The committed manifest additionally binds the archive
checksum; that field is omitted inside the archive to avoid a circular hash.

Generation produces candidates, not accepted fixture identities. Follow the
[phase 2 validation record](../docs/operations/test-rationalization-phase2.md)
for the generator/receiver identities, float32 analytic-IQ recipe and independent
source-image timing measurement. Validate known content and provenance before
publishing a new immutable bundle, updating the manifest deliberately, and
running the fixture suite. Do not change hashes merely to obtain a pass.

## Received-IQ corpus

The received-IQ regression corpus is too large for Git and is installed at:

```text
tests/samples/received-corpus/
```

The received tier requires its selected corpus inputs and the
`regression-expectations/` directory, and fails when they are absent or changed.
The unit tier explicitly excludes those methods. The repository does
not select or automatically fetch a corpus.

The 2026-09-23 stored-manifest compatibility case required by the received tier is
`wrmi-20260923-15770000-full-broadcast`. Its canonical CF32 IQ and appliance
capture records live under `received-corpus/sources/wrmi-20260923T133007Z-15770000/`.
The saved GramPy decode manifest, text, nine PNGs, and component evidence are
under the corresponding `received-corpus/references/` directory. These are
decoder reference outputs, not independent truth. The original intake folder,
including diagnostic WAV files, was retired after canonical promotion and
identity checks. The unique content-bearing text manifest remains under
`tests/samples/archive/intake-products/sampleFullRun-20260923/`. Tests refer
to the canonical source and do not depend on intake or optional history. The accepted
compact outputs and quality measurements are documented in the
[`API guide`](../docs/decoder/api.md); the implementation plan and acceptance
record are [archived](../docs/provenance/archive/output-manifests-plan.md).

To create an archive, supply a version and output path:

```sh
tools/package-corpus \
  --version 1.0 \
  --output /path/to/received-corpus-1.0.tar.zst
```

The command updates `version.json` in the corpus, creates the archive, and
prints its SHA-256. Add `--encrypt` to prompt for a password and produce an
encrypted archive. No password is retained.

Fetch and install an archive by supplying its URL and SHA-256 explicitly:

```sh
tools/fetch-corpus \
  --url 'https://example.invalid/received-corpus-1.0.tar.zst' \
  --sha256 SHA256_FROM_PACKAGE_COMMAND
```

Add `--encrypted` to prompt for the archive password. The fetch command
verifies the downloaded bytes, validates the archive before extraction, and
atomically replaces an existing corpus only after validation succeeds. It
does not retain the URL, SHA-256, or password and does not compare corpus
versions.

Fetching requires `curl`, and packaging or fetching `.tar.zst` archives
requires `zstd`. Optional encryption also requires `openssl`.
