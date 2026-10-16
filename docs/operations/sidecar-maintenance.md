# External test data: provenance, installation and maintenance

The `tests/samples` sidecar is supplied separately from Git, currently through
the maintainer's S3 storage. It is external test data, not a development output
directory. Keep the existing path so established overrides and tools continue
to work. `tests/fixtures/sidecar-v1.json` indexes the reviewed installed files.

## Decide where an artifact belongs

There are two storage buckets. Git contains independently project-authored
code, small synthetic vectors, recipes, case definitions and non-content
acceptance metadata. The sidecar contains broadcast-origin or uncertain-origin
material and large artifacts. Provenance takes precedence over size: a tiny
broadcast image or text excerpt still belongs externally. Derivatives inherit
the source classification, including crops, transformed signals, decoded
payloads and expected values copied from a recording.

For native fixture artifacts, use 1 MiB per file and 10 MiB per fixture family
as the normal Git budget. Larger native inputs belong externally; do not split
files to evade the budget. This budget does not authorize broadcast content in
Git. Source code and non-content engineering documentation are not fixture
artifacts. Record any deliberate budget change before adopting new inputs.

Never construct a checkout-only test by copying or transforming sidecar data.
Use independently authored input and independent expectations appropriate to
the behavior. Tests committed to Git may load external fixtures in a selected
external-data tier, but must not inline their payloads or expected content.
Non-content paths, hashes, sizes, intervals, geometry and aggregate limits may
be committed. Committed numerical evidence is not permission to turn a
broadcast-measured series into a checkout-only test input or expected vector;
generate independently authored synthetic series for those tests. Keep uncertain provenance external until a recorded review
establishes independent project-authored origin and suitability for Git.

## Installed layout and coverage

| Location | Purpose | Needed for regular tests? |
| --- | --- | --- |
| `controlled-mfsk-v1/` | Four accepted, independently generated fldigi transmissions and their large WAV/IQ inputs | Controlled tier |
| `received-corpus/` | Canonical RF, broadcast truth and accepted receiver references | Received tier; four selected complete broadcasts additionally serve the long quality gate |
| `regression-expectations/` | Content-bearing assertions externalized from received tests | Received tier |
| `archive/` | Selected historical evidence, large reference software and immutable distribution bundles | Optional; no regular test depends on it |

The sidecar's small metadata accompanying a recording is a portable installed
representation, not the primary home for project policy. Current independently
authored case definitions are in `tests/fixtures/received-cases.json`; copied
broadcast header expectations remain only in external installed case records.
The controlled evidence, broadcast policy and numerical baseline are in Git.
Native historical preparation metadata is in
`docs/encoder/data/session9/prepared.json`; original photographs remain external.

`tools/test-suite --suite unit` is the checkout-only regression selection.
It covers protocol, synthetic decoding/round trips, picture handling, scoring,
resource bounds and failures. It does not establish received-signal quality or
independent fldigi interoperability. Controlled/received/all selections fail
when required external inputs are absent or changed, rather than skipping.
The separate full-broadcast gate retains its accepted limits and inputs.

## Publish and install an S3 sidecar release

Treat the sidecar and committed manifest as a versioned pair. A maintainer can
hand off just the required directories, or include the optional archive for
historical investigations. Do not hand off `.local`, credentials, WIP or a
developer's cached outputs. The S3 location and access credentials are supplied
privately; this repository does not invent a bucket or download URL.

1. Review additions by provenance and necessity. Record path, hash, size,
   source, required/optional status and purpose in the committed inventory.
2. Run `tools/verify-sidecar --include-history` through the managed Mac wrapper
   against the intended complete release. Select the corresponding test tiers.
3. Publish a new immutable S3 prefix or bundle with that inventory version and
   checksum. Keep the previous release available until the replacement is
   installed and verified on another checkout. Do not overwrite the only copy
   of a broadcast capture or approved receiver reference.
4. Install required directories beneath `tests/samples`, or supply a different
   parent with `GRAMPY_TEST_SAMPLES`. Verify with `tools/verify-sidecar` and run
   the required tests. Use `--include-history` when installing the archive too.

`tools/package-corpus` and `tools/fetch-corpus` now transport the complete
installed `tests/samples` directory. They include controlled fixtures, received
RF/references, external expectations and optional archive history when present.
Packaging verifies the committed inventory before and after reading inputs and
adds `samples/sidecar-release.json` with the release version, inventory identity
and history-inclusion flag. It leaves source files and the received corpus's
version untouched. The installed transport metadata is validated separately by
`tools/verify-sidecar`; it is not an unclassified fixture or a new corpus input.

Put these commands in managed batches, using your private download URL:

```sh
tools/package-corpus

tools/fetch-corpus --url 'HTTPS_DOWNLOAD_URL' --sha256 'ARCHIVE_SHA256'
```

With no arguments, packaging labels the snapshot with the current UTC time
(`YYYYMMDDTHHMMSSZ`) and writes `.local/samples-<label>.tar.zst` under this
checkout. This identifies an export snapshot, not the GramPy software version.
The inventory and archive hashes identify its exact data. `--version LABEL`
provides your own label; `--output PATH` overrides the destination. Default
filenames sanitize path separators in labels, and an existing archive is never
overwritten. Remove the exact local export after publication and verification
when it is no longer needed; these are temporary delivery artifacts, not
permanent local configuration. Agents still record owned exports in their
change's work record, and may use `--output` to put them under that WIP directory.

Add `--encrypt` when packaging and `--encrypted` when fetching to prompt for a
password. URL, checksum and password remain explicit; they are not saved in the
repository or release metadata. No S3 upload is performed by either command.

Fetch checks the supplied archive checksum, rejects unsafe archive entries,
extracts to staging, verifies the release against the matching committed
inventory, and then replaces the entire installed sidecar. Failures preserve
the old installation; successful replacement removes local-only files. Keep
irreplaceable additions outside the installation or publish them as a reviewed
release before replacing it.

`--samples-root PATH` changes the source/install directory; `--corpus-root`
remains an alias. `--manifest PATH` supplies the matching inventory for an older
release. Use `--received-only` explicitly to package or fetch the old
received-corpus-only format; its default source/destination remains
`tests/samples/received-corpus`. Older bundles cannot replace an entire sidecar.

The original controlled `.tar.gz` remains under `archive/distribution/` as an
optional immutable delivery artifact; tests read its extracted fixture directory.

## Close a phase without accumulating outputs

Put new intake, decode outputs and review pages in `.local/wip/<change-id>/`.
Promote required external data only after establishing provenance, unique
coverage and its manifest identity. Promote suitable small native records to
Git. Preserve historical content externally only with a specific investigation
purpose; otherwise discard reproducible outputs after retaining the recipe and
compact findings. Verify promotion before deleting an intake duplicate.

`reference-captures`, `quality-calibration` and `stage5-performance` were retired
as legacy development/intake areas in the October 13 audit. Do not recreate
them as permanent sidecar directories. See the
[audit](sidecar-audit-20261013.md) for identities, dispositions and limitations.
