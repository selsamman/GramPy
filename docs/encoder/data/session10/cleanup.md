# Post-project cleanup and retention

**Completed, 2026-10-03**, following the PM's clarification that cleanup means
retiring working intermediates as well as closing the implementation sessions.
The earlier closeout deliberately kept evidence in place; this pass preserves
its content while reducing its working footprint.

| Area | Action | Preserved |
| --- | --- | --- |
| Permanent repo | Keep API/contracts/design/validation/baseline guides, tests, vectors, frozen qualification/acceptance records, reviews and reusable Pi/benchmark workflows. | Accepted source and final wheel hashes are unchanged. |
| Historical project work | Retain completed plans/change records and `experiments/` workflows as provenance; tool roles are labeled in `tools/README.md`. | Useful failure diagnoses and reproduction recipes; no runtime dependency. |
| Mac superseded work | Losslessly archive three obsolete working directories and compress two raw transfer logs. | Every archived file/log verified against original bytes before removing its loose copy. |
| Mac generated IQ | Remove ten analytic IQ caches after regenerating each byte for byte from its retained WAV. | WAVs, IQ metadata, decoded images/text/diagnostics, scores, recipe, dependency versions and restoration helper. |
| Mac packaging copy | Remove 40 `build/lib/` files after matching each to its permanent source. | Source, final wheel, regression/package records; development environment and package metadata retained. |
| Qualification Pi | Remove 15 explicitly inventoried, inactive staging directories after full preservation and fresh content/process checks. | 534 retained Mac counterparts plus verified archived unique contents and recorded links/modes; shared test runtime remains. |

Mac archiving/cache removal saved 337.1 MB.
After adding the Pi preservation archive and audit/restore records, net Mac
savings are approximately **250.6 MB**. Pi retired staging
contained **509.0 MB** of regular-file
content. These are logical-byte counts, not a promise about filesystem block
accounting. No active project process referenced the retired directories.

## What remains in `.local/`

Keep the final wheel and current benchmark inputs, authoritative WAVs, unique
failed/control transmissions, decoded outputs and measurements, one reference
binary, baseline source snapshots, and the compact archives/restoration records.
They remain useful acceptance and debugging evidence. No further project-wide
purge is needed. Targets, credentials, tunnels, unrelated local work, the main
virtualenv and the external `tests/samples` corpus are preserved. Finder
metadata is unrelated to this project and was not swept into this cleanup.

The new archives and restoration information live under
`.local/project-cleanup/`. Its `mac-cleanup.json` binds local archives/caches
to hashes; `pi-restore-manifest.json` maps every retired Pi file to a retained
Mac file or archived content object. `pi-preserved.tar.gz` is a verified,
63.8-MB archive of otherwise unmatched Pi
contents. Machine-specific paths stay in that private directory.

## Restoration

Use the repository virtualenv and managed wrapper. For example, a Mac command
file can invoke:

```sh
.venv/bin/python .local/project-cleanup/restore-local.py --iq all
```

Use `--archive ORIGINAL_PATH` for a local snapshot/log named in
`mac-cleanup.json`; restoration refuses to replace an existing path. One IQ
restore was exercised end to end and removed again after its hash passed.
All archive members were checked against their original content.

For a Pi reproduction, the local
`.local/project-cleanup/prepare-pi-restore.sh` can build a portable restoration
archive from retained files and the preserved content objects. Transfer and
restore it only through the managed Pi wrapper into absent staging paths.
This helper is preserved for future use; retired workspaces were not recreated
as part of cleanup. Existing scripts/logs may name old staging locations;
restore the recorded workspace before using such historical commands.

The operational installation and pinned fldigi receiver were not changed.
No production source, test, fixture, sample or accepted numerical record was
modified. No full regression rerun was needed for artifact-only cleanup;
content hashes, archive membership, exact IQ regeneration, active references,
source/package identities and frozen acceptance identities were verified.

See [cleanup-summary.json](cleanup-summary.json) for the recorded counts and
[the final package/benchmark record](README.md) for accepted functionality.
