# GramPy

GramPy is the direct MFSK IQ decoder being extracted from Radiogram.

This is a code-separation milestone. Publication and the final public API
documentation follow in later breakout phases.

## Test corpus setup

The received-IQ regression corpus is intentionally not stored in Git. Before
running corpus-dependent tests, install the exact corpus required by this
checkout:

```sh
tools/setup-corpus
```

The installer compares `tests/samples/received-corpus/version.json` with the
version recorded in versioned `tests/corpus.json`. It downloads only when the
version is absent or different, verifies the archive SHA-256 before extraction,
validates archive paths and the extracted corpus version, and then replaces the
local corpus. A `.tar.zst` archive requires the `zstd` command-line tool.

Run the test suite with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```
