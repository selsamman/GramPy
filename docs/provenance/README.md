# Historical provenance

This is a lookup area for explaining earlier development decisions. It is
not routine agent bootstrap, current requirements or a dependency of normal
tests. Start with current domain documentation and the active change record;
follow a historical link when the task needs the earlier evidence.

| Location | Retention purpose |
| --- | --- |
| [`archive/`](archive/README.md) | Selected imported decoder planning and implementation records, preserved verbatim. |
| `changes/<change-id>/` | Selected native investigation findings and compact evidence after a change closes. Create entries only when there is material historical value. |
| `tests/samples/archive/<change-id>/` | Optional broadcast/uncertain-origin content and large historical artifacts, indexed by a committed manifest in the corresponding change entry. |

For each new historical entry, label its status and source revisions, explain
why it is retained, and link the concise change closeout and any artifact
manifest. Preserve useful negative findings as well as successful results.
Keep current contracts and reusable instructions in their supported locations.
Previous versions of committed files remain recoverable through Git history.

The [test-maintenance and closeout policy](../operations/test-maintenance.md)
defines promotion, retention, work-directory cleanup and sidecar handoff.
Existing change records elsewhere in `docs/` remain at their current paths;
adding this policy does not move or duplicate them.

Selected native entries:

- [2026-10-13 sidecar audit](changes/20261013-sidecar-audit/README.md): provenance
  classifications, corrections to embedded broadcast evidence, canonical-input
  preservation, verified retirement and required/optional S3 handoff.
- [2026-10-12 local cleanup](changes/20261012-local-cleanup/README.md): unique
  received RF, practical/manual original inputs and pinned reproduction anchors,
  with an explicit legacy disposition ledger and verified artifact manifest.
