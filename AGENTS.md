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

- Mac: `tools/mac-local.sh`, optionally with a batch in `.local/mac-command.sh`;
- Pi: `tools/pi-remote.sh`, optionally with a batch in `.local/pi-command.sh`.

Run every managed wrapper on a network-capable execution surface. Mac jobs
may need it for the delayed notifier; Pi jobs need it for SSH. Direct
read-only inspection may remain on the default sandbox surface.

Reusable Pi workflows belong in the checked-in `tools/pi-*.sh` scripts. A
one-off Pi command belongs in `.local/pi-command.sh`; do not call `ssh`
directly. Optional command files are useful for reproducibility and
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
