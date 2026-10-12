# Agent Execution Contract

## Environment

Use the repository virtualenv and source tree for Python work:

```sh
PYTHONPATH="$PWD/src" PATH="$PWD/.venv/bin:$PATH" \
  .venv/bin/python -m unittest discover -s tests
```

Do not silently use system Python when `.venv` exists. If a required
dependency is missing, ask before changing the implementation or using a
weaker substitute.

## Managed execution

Direct commands are for clearly short, read-only inspection or targeted work.
Run tests, experiments, corpus jobs, Pi work, and commands of unknown or
potentially long duration through the managed wrapper:

- Mac: `tools/mac-local.sh [command-file]`;
- Pi: `tools/pi-remote.sh [command-file]`.

Put new one-off batches under `.local/wip/<change-id>/` and pass their path
to the wrapper. The existing `.local/mac-command.sh` and `.local/pi-command.sh`
defaults remain supported.

Run every managed wrapper on a network-capable execution surface. Mac jobs
may need it for the delayed notifier; Pi jobs need it for SSH. Direct
read-only inspection may remain on the default sandbox surface.

Reusable Pi workflows belong in the checked-in `tools/pi-*.sh` scripts. Keep
one-off Pi command files in the change's work directory; do not call `ssh`
directly. Command files are useful for reproducibility and
checkpointing, but are not required merely to combine commands.

Managed state is stored in `.local/agent-runs/<session-id>/`:

- `running.md` means the command is active;
- `result.md` is the authoritative completion record;
- `run.log` contains command output for later diagnosis.

Only one managed command may be active per session. Do not poll merely because
one is active. When `result.md` is available, incorporate it into the task
outcome, then remove that completed session directory. Never remove it while
`running.md` exists. A delayed best-effort notification is attempted only if
the completed directory remains; notification success is independent of
command exit status.

## Boundaries and repository safety

The wrapper does not grant network or protected-filesystem access. Command
authorization, sandbox permissions, DNS/network access from the execution
surface, Pi SSH reachability, and remote authentication are separate
conditions. Keep Pi targets, network targets, and secrets in `.local/`.

Treat `.local/` as valuable unversioned state; never prune it by filename.
Preserve the external `tests/samples` corpus. Avoid unrelated structural
changes, especially to `src/`, decoder code, tests, fixtures, and sample data.
Do not create commits unless explicitly requested.

## Test maintenance and change scratch

Use `docs/operations/test-maintenance.md` when creating, replacing or retiring
tests, changing fixtures or quality limits, or closing a development phase.
Selected required-data tests fail when their inputs are absent or changed.
The regular `all` suite does not include the separate broadcast quality gate.

Create `.local/wip/<change-id>/WORK.md` before generating new change artifacts.
Record ownership, status, source baseline, outputs (including remote scratch)
and intended promotion/discard destinations. Keep one-off commands, notes,
logs and generated outputs under that work directory. Keep machine-private
configuration and credentials outside it.

At change closeout, promote maintained material to the repo or sidecar and
selected historical findings to `docs/provenance/changes/<change-id>/` (large
historical artifacts go in the indexed sidecar history area). Verify the
promoted identities and that required validation uses durable paths. Record
disposition in the closeout, ensure no owned run is active or dependency remains,
then delete the exact owned work directory and explicitly owned remote scratch.
Awaiting review or deferred work is still WIP; ending a chat is not closeout.
Unclassified legacy `.local` state requires a separate inventory/disposition
review and is never covered by a new work directory's deletion scope.

Read current guidance and the active change record for normal work. Consult
specific historical provenance only when investigating an earlier decision;
do not load the archive as routine bootstrap or treat it as current instructions.
