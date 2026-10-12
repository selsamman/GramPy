# Work record template

Copy the following into `.local/wip/<change-id>/WORK.md` and fill it in.
Record artifact groups such as an entire generated run directory when they
share a disposition; a per-file inventory is unnecessary for known disposable
output. Hashes and individual paths belong in manifests for promoted inputs.

```markdown
# CHANGE-ID

Request/change record:
Owner:
Source/configuration baseline:
Status: investigating / candidate / awaiting review / deferred / closing
Last verified checkpoint:

## Owned artifacts

| Path or artifact group | Purpose | Intended disposition | Durable destination |
| --- | --- | --- | --- |
| commands and generated runs | Reproduction/evaluation | Discard after closeout | Required recipe/result promoted separately |
| intermediate notes | Investigation | Distill selected findings, then discard | Change closeout or historical entry |

Remote scratch locations and their owner:
Required machine-private configuration (names only; no secret values):

## Open decisions

Retention uncertainties, candidate decisions and incomplete validation:

## Closeout

Decision and validation:
Promoted paths and verified identities:
Validation with scratch unavailable:
Sidecar handoff/manifest:
Historical findings retained and why:
Remote scratch disposition:
No active runs or dependencies remaining:
Planned cleanup (promote this record before deleting WORK.md):
Record the actual deletion outcome afterward in the durable change closeout.
```

Follow [test maintenance and closeout](test-maintenance.md). A work record is
an ownership/checkpoint aid, not a substitute for the managed command's
authoritative completion record or for change acceptance.
