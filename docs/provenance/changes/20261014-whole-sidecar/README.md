# Whole-sidecar transport extension — October 14, 2026

Source baseline: `3f9026e`. The existing package/fetch commands now default to
all of `tests/samples`, with controlled recordings, received corpus, external
expectations and any installed optional history in one `samples/` archive.
The current [maintenance guide](../../../operations/sidecar-maintenance.md)
describes invocation and installation behavior.

Packaging verifies the matching inventory before and after reading source
files. It adds a versioned transport metadata file in the archive rather than
changing the source sidecar or received-corpus version. Fetch validates the
explicit archive checksum, safe archive paths, release/inventory identity and
all included artifacts in staging before replacing the installation. Failure
preserves the previous installation; successful replacement applies to the
entire selected sidecar root. URLs, checksums and passwords remain explicit.

A shared verifier supports both transport and `tools/verify-sidecar`.
`--samples-root` selects a custom source/install root; `--corpus-root` remains
an alias. Old received-only archives require `--received-only`, retaining their
previous format and installation scope. The low-level Python functions retain
legacy behavior when no sidecar inventory is supplied. Legacy packaging also
retains its previous received-corpus version-update behavior.

Validation used independently authored synthetic files, never copied broadcast
payloads. The 20 targeted transfer tests passed, including whole-sidecar plain
and encrypted round trips, required-only bundles, repacking an installed
release, missing/changed inputs with a valid outer checksum, incorrect inventory
identity, unknown files, received-only archive rejection and failed-install
rollback. The checkout-only suite passed all 247 tests without skips. The real
303-file sidecar inventory passed with optional history included.

Receipts: [targeted-result.md](targeted-result.md),
[regression-result.md](regression-result.md) and [cli-result.md](cli-result.md).
The regression batch returned exit 1 only because its final help check
incorrectly invoked a shell wrapper with Python, after tests and integrity
checks had passed. The corrected command check and a real shell-wrapper
package/fetch round trip completed with exit 0; no code change was needed for
that correction.

No live sidecar was packaged or replaced, no S3 access/publication occurred,
and no decoder quality limits, required signal data or fixture identities
changed. The seven new checkout-only tests bring that suite from 240 to 247.
No full broadcast decode was needed for this transport-only change. Owned WIP
was removed after preserving these results. No commit or push was created.
