# Selected historical evidence after .local cleanup

The [October 13 sidecar audit](../../../operations/sidecar-audit-20261013.md)
supersedes the sidecar paths and retention descriptions below. Selected history
now lives under `tests/samples/archive/20261012-local-cleanup/`; the native
preparation record is in Git, the historical wheel was retired, and previously
committed broadcast imagery is external. The current installed inventory is
`tests/fixtures/sidecar-v1.json`. Original receipts remain historical snapshots.


Historical, non-normative evidence retained on 2026-10-12 from source checkpoint
`b99b886`. Normal tests and future development do not require this history area.
Current validation instructions are in [test maintenance](../../../operations/test-maintenance.md)
and [broadcast regression](../../../operations/broadcast-regression.md).

The earlier cleanup compressed workspaces and retained a broad restoration
scheme. This pass instead preserves explicit useful inputs and findings,
discards reproducible output and retires the old all-workspace restoration
scheme. The [disposition ledger](disposition.json) records every legacy root;
the [artifact manifest](artifacts.json) identifies the selected preserved files.

## Retained findings and inputs

- The unique September 19, 2026 23:00 UTC, 9.455-MHz Airspy recording is a
  complete received signal, not a generated fixture. Its original metadata,
  exact historical automatic-decode baseline and nine accepted raster images
  are preserved. This was the source for the
  [automatic-picture comparison](../../../decoder/data/auto-mfsk32-pictures/received-broadcast.json).
  The old directory also contained a separate September 23 saved manifest;
  that manifest already exists in the maintained received corpus. The two
  identities must not be conflated.
- The original paired native/fldigi manual-control WAVs and explicitly offline
  clock-corrected diagnostic retain the evidence for transmitter time-scale
  investigation. Existing Git records preserve the manual/Pi images, results
  and diagnosis. See [session 9 findings](../../../encoder/data/session9/README.md).
  Failed partial capture attempts do not establish a fix; their raw dumps,
  virtual environments and embedded transfers have been discarded.
- The ten unchanged practical-qualification transmitter WAVs, their recorded
  identities and frozen matrix are preserved so the accepted fldigi results
  remain tied to obtainable inputs. Existing Git truth/review images are reused
  where byte-identical. See the
  [practical acceptance](../../../encoder/data/session9/practical-acceptance.json).
- One exact qualified fldigi 4.2.13 aarch64 executable and one accepted
  historical `radiogrampy-0.1.3` wheel are retained as precise reproduction
  anchors. They are historical artifacts, not current package
  installation instructions. The current Pi installation was untouched.

The accepted scores, reviews, qualification records, failure diagnoses and
reusable recipes remain in Git. Old source versions can be recovered from Git;
generated IQ, repeated decodes, diagnostic components, build/install copies,
raw transfer logs and bundle archives are not retained merely to restore an
old scratch tree. The source and matrix identities in the historical records
still apply; those records have not been silently repinned.

## Handoff and targeted reproduction

The selected large files live under
`tests/samples/provenance/20261012-local-cleanup/`. Copy that complete directory
with the project's external sidecar handoff and verify paths, sizes and hashes
against `artifacts.json`. Records marked `repo` reuse existing Git files.
There is no assumed public download location. `tools/package-corpus` packages
the received-corpus subtree; it does not include this sibling historical area.

Raw received RF and external captures cannot be regenerated exactly. For an
intentional historical reproduction, use the matching old source/wheel and
frozen matrices in an isolated owned workspace, resolve their recorded inputs
to this manifest and reproduce only the needed experiment. The frozen v3
matrix contains the former `.local/session9/mac-control/source-160x120.png`
path; its identical chart is already in Git and identified by this manifest.
Historical preparation scripts also guard an old source snapshot. Their old
default paths are not maintained test dependencies or instructions to restore
legacy directories in the main checkout.

The maintained controlled fixture package, four-broadcast regression corpus
and current acceptance limits remain in their existing locations. Historical
availability is separate from their strict required-input validation.
