# Package defaults — October 16, 2026

`tools/package-corpus` now needs no version or output arguments for a normal
whole-sidecar export. An omitted version becomes a UTC snapshot timestamp,
independent of the GramPy software version. Default output is the checkout's
`.local/samples-<label>.tar.zst`, with `.enc` added for encryption. Legacy
received-only mode uses the `received-corpus-` filename prefix.

Explicit `--version` and `--output` still override these defaults. Default
filenames replace unsafe label characters with underscores while retaining the
original label in release metadata. Existing archives and symlinks, including
dangling symlinks, are never overwritten. Local exports are delivery artifacts:
remove the exact owned export after publication/verification when no longer
needed. The current guide is
[sidecar maintenance](../../../operations/sidecar-maintenance.md).

All 22 focused transfer tests passed, covering automatic labels, plain/encrypted
default output round trips, explicit overrides, label path safety and existing
file/symlink preservation, alongside prior whole-sidecar and legacy transfers.
The [managed receipt](validation-result.md) confirms successful completion.
Only independently authored temporary test payloads were packaged. The real
sidecar was not packaged or modified; no S3 operation, commit or push occurred.
The owned WIP and completed managed state were removed after preserving this
closeout. Earlier whole-sidecar changes remain pending in the working tree.
