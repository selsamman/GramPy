# Test rationalization: phase 5

Date: 2026-10-12. Status: legacy .local retirement and validation completed;
closeout records prepared for review. Phases 3 and 4 were committed in `b99b886`.
This phase creates no Git commit.

## Result and scope

The inventory classified 4,035 legacy filesystem entries. Cleanup removed
142 explicitly listed roots containing 3,090 regular files and 1,203,769,670
logical bytes. Selected history copied to the sidecar totals 394,402,014 bytes;
11 additional selected identities reuse existing durable files. The net project
file-content reduction is approximately 809.4 MB, before the small new records.
These are logical-byte counts rather than an assertion about APFS snapshots
or physical free-space accounting.

The [disposition ledger](../provenance/changes/20261012-local-cleanup/disposition.json)
records each root's purpose and action. Deletion verified the original private
inventory's file contents and symlink identities, verified promoted copies,
checked for unrelated active managed runs and open legacy files, and did not
follow links into external directories. The
[authoritative deletion record](../provenance/changes/20261012-local-cleanup/deletion-result.md)
confirms completion with exit 0.

## Retained material

The [selected historical findings](../provenance/changes/20261012-local-cleanup/README.md)
and [artifact manifest](../provenance/changes/20261012-local-cleanup/artifacts.json)
cover the unique September 19 received capture, its accepted baseline/rasters,
original manual controls and diagnostic derivative, ten qualified practical
transmitter WAVs, one pinned fldigi binary and one accepted historical wheel.
Existing Git reviews, scores, source images, qualification and failure records
remain available. The external sidecar is preserved; these selected artifacts
were added under `tests/samples/provenance/20261012-local-cleanup/`.

Repeated decodes, generated IQ/components, packaging/install copies, embedded
transfer bundles, virtualenv/cache copies, raw logs and obsolete restoration
scaffolding were discarded. Current input data and decoder implementation
were not changed. Historical commands naming removed paths are marked with
the replacement provenance entry; their frozen identities remain unchanged.

Persistent machine files were verified byte-identical:

- `.local/pi-target.env`
- `.local/mac-command.sh`
- `.local/pi-command.sh`
- `.local/pi-stop-temporary-fldigi-rpc.sh`

After review, the reusable RPC start/stop commands were promoted to
`tools/pi-start-temporary-fldigi-rpc.sh` and
`tools/pi-stop-temporary-fldigi-rpc.sh`. The local Pi default is now a symlink
to the start helper. The inventory and deletion receipts above record the
initial cleanup state, before this follow-up promotion.

`agent-runs/` and `wip/` remain infrastructure locations. `reference/` is
scratch rather than permanent infrastructure; its slot contained only Finder metadata. Finder metadata was excluded
from project cleanup; the optional notifier was absent and was not invented.
The closed phase 4 and phase 5 WIP directories were removed after their
required findings and completion receipts were preserved outside WIP.
Remaining `.local` regular-file content is about 31 KB, including unrelated
Finder metadata. No legacy project output or completed managed session remains.

Only this repository's `.local` was retired. Sibling repositories, remote Pi
workspaces/installations and existing external corpus files were not deleted.

## Verification

Required controlled-fixture preflight and all 88 broadcast input identities
passed after deletion; all recorded production source hashes and 39 selected
historical identities matched. The regular `all` suite passed all 254 tests
with no skips in 152.176 seconds. Repeating the 15-minute broadcast decode is
unnecessary because its input bytes and decoder code are unchanged and phase 3
already exercised a fresh repeated acceptance run.

The [authoritative validation record](../provenance/changes/20261012-local-cleanup/validation-result.md)
confirms exit 0 after 155 seconds. The baseline's adoption metadata now points
to the user's `b99b886` checkpoint; input identities and numeric quality limits
are unchanged. Closeout details are in the
[cleanup result](../provenance/changes/20261012-local-cleanup/cleanup-result.json).
