# Tests

Run the test suite from the repository root with:

```sh
PYTHONPATH="$PWD/src" PATH="$PWD/.venv/bin:$PATH" \
  .venv/bin/python -m unittest discover -s tests
```

## Received-IQ corpus

The received-IQ regression corpus is too large for Git and is installed at:

```text
tests/samples/received-corpus/
```

Corpus-dependent tests use the corpus when it is present and skip when it is
absent. The repository does not select or automatically fetch a corpus.

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

Packaging and fetching `.tar.zst` archives require `zstd`. Optional encryption
also requires `openssl`.
