# Test maintenance and work closeout

Tests protect supported behavior and accepted quality. Each change should
leave a useful regression check, clear required inputs and less temporary
state to interpret later. Use this policy with the
[change-management cycle](change-management-v1.md).

## Choose the validation scope

Run commands through the managed wrappers with the repository virtualenv and
source tree, as required by [AGENTS.md](../../AGENTS.md). The command lines
below belong inside a managed batch.

| Selection | Purpose and inputs | When to use |
| --- | --- | --- |
| `tools/test-suite --suite unit` | Protocol, algorithm, API and generated integration checks; no external sidecar | Routine development and CI; add targeted checks for the affected contract. |
| `tools/test-suite --suite controlled` | Maintained controlled recordings with known content and independent evidence | Changes affecting acquisition, text, picture transitions or fixture handling. |
| `tools/test-suite --suite received` | Received excerpts and saved-manifest compatibility checks | Changes affecting real-signal handling or artifact contracts. |
| `tools/test-suite --suite all` | All three regular tiers | Final regular regression with both sidecars installed. |
| `tools/broadcast-regression --output PATH` | Fresh complete decodes of the four policy-selected broadcasts, paired GramPy/fldigi scores and HTML review | Decoder-quality or scoring changes; final quality acceptance alongside the regular suite. |

Invoke the Python runners with `.venv/bin/python`. `all` does not include
broadcast acceptance. The broadcast gate covers its explicit selected corpus,
not every recording stored in the sidecar. The quicker tiers do not produce
equivalent full-broadcast quality acceptance. There is currently no shorter
windowed version of that scoring gate.

On the October 12, 2026 Mac validation, the regular suite took about 2½ minutes
and the four-broadcast workflow about 15 minutes. These are planning estimates,
not portable timing limits. Select proportionate evidence for the change;
record what ran, what was deliberately excluded and why. Use the existing
[decoder validation policy](../decoder/validation.md) for visual review and
the change-management process for Pi qualification.

## Create a test for an enduring contract

State the behavior or failure the test protects in its name and setup. Prefer
the smallest input that exposes that behavior, and use a generated temporary
input when it adequately represents the contract. A realistic received case
is valuable when signal conditions, transitions or long-running state matter.

Use an independent expected result: a protocol vector, known payload, reviewed
source material, qualified external reference or an accepted measured baseline.
Document which kind it is. Saved GramPy output is compatibility evidence;
agreement with fldigi is comparative evidence. Neither automatically becomes
independent transmitted truth.

Assert observable behavior and meaningful failure handling. Avoid assertions
that merely repeat implementation constants, documentation wording or the
same calculation that produced the result. Do not freeze incidental timings
or internal organization unless they are the contract being protected.

Keep the test's required setup discoverable in `tests/README.md` and its
committed fixture manifest. Tag external-data methods with the appropriate
suite. A selected test must fail when its required input is missing or changed;
it must not skip, substitute another recording or quietly weaken assertions.
Explicitly excluded tiers are not validation passes.

An unavailable independent source image may leave a declared pixel metric
unscored while detection and completion remain tested. Identify the exact
case and reason in the evidence. An unexpected missing fixture or an error
computing a metric is a validation failure.

## Maintain inputs and acceptance limits

Small protocol vectors and expectations belong in `tests/fixtures/` or the
existing normative data location. Large recordings, images and qualified
receiver outputs belong in the versioned `tests/samples` sidecar. Required
tests must never depend on `.local`, an intake folder or a past session's
output directory.

Before adopting new external input, establish its provenance and intended
coverage, validate the expected content, and record its relative path, hash,
size and version in a committed manifest. Document how to obtain or recreate
the bundle. Verify an installation outside the generation workspace before
calling it maintained coverage. Preserve required original recordings and
qualified reference results even when their derived scorecards can be rebuilt.

The broadcast policy and compact baseline live in
`tests/fixtures/broadcast-regression.json` and `broadcast-baseline.json`.
Normal runs do not update limits. A proposed replacement must identify the
changed inputs, configuration or scorer, report old/new coverage and scores,
and receive change acceptance before promotion. Do not change hashes or
limits solely to make a failure disappear. See the
[broadcast workflow](broadcast-regression.md) for calibration and
failure/review exit statuses.

## Replace and retire tests deliberately

When adding coverage, inspect the existing tests for the same contract. Before
removing one, list its unique assertions and failure cases and show where
they are preserved, or why the supported behavior has been retired. A larger
integration test does not automatically replace a focused error-path test.

Merge duplicated setup or redundant checks when it improves clarity. Retire
obsolete qualification/session tests from normal discovery when their product
contract has been replaced. Record the replacement or retirement reason in
the change closeout. Git retains old code and tests; copying every removed
test into an archive is unnecessary.

Keep historical experiments or tests only when they have a specific remaining
investigation value. Label their historical status, compatible source revision,
inputs and invocation, and exclude them from ordinary product validation.
Promote reusable evaluation machinery into `tools/` with its own maintained
contract instead of relying on an old experiment.

## Give each change its own work directory

Create `.local/wip/<change-id>/` before producing temporary change artifacts.
Use a stable change identifier, for example `20261012-test-maintenance`, rather
than a chat/session identifier. Several sessions can work on the same change;
independently accepted phases can have separate directories.

Keep a `WORK.md` in that directory with:

- the request/change-record link, owner, source baseline and current status;
- the commands, outputs, notes and any remote work locations owned by it;
- each artifact's intended disposition: promote to the repo, promote to the
  sidecar, preserve as selected historical evidence, or discard;
- unresolved decisions and the last verified checkpoint.

Use the [work-record template](work-record-template.md) when helpful. Artifact
groups can share a disposition; known generated output does not require a
per-file inventory.

Update it as evidence becomes important. Capture intermediate notes there
while investigating; distill them for the decision rather than leaving their
value to be inferred at cleanup. Put one-off command files and generated
outputs under the work directory. Pass the command-file path to the wrappers:

```sh
tools/mac-local.sh .local/wip/CHANGE-ID/mac-command.sh
tools/pi-remote.sh .local/wip/CHANGE-ID/pi-command.sh
```

Place a broadcast run under, for example,
`.local/wip/CHANGE-ID/broadcast-01/`. Each run still requires a new output
directory. The wrappers' legacy default command-file paths remain supported.
Reusable Pi workflows continue to belong in checked-in `tools/pi-*.sh`.

Machine configuration, target files, credentials and notifier configuration
stay in `.local` outside a change's work directory. They have a machine-level
lifecycle and must not be deleted as change scratch or copied into evidence.
Managed command state remains in `.local/agent-runs/<session-id>/`; follow its
existing completion/removal rules rather than relocating or deleting active
state. Give remote temporary outputs the same ownership and closeout record;
do not prune shared receiver installations or reference stores.

## Preserve history without making it routine reading

Current supported behavior and operating instructions belong in the normal
domain documentation. Required test inputs and active limits belong in their
maintained manifests. Keep a concise closeout in the change record: outcome,
accepted delta, validation, input identities, relevant limitations and links.

Selected native historical findings belong under
`docs/provenance/changes/<change-id>/`. A short `README.md` should explain the
question, findings, rejected alternatives worth remembering, decision, source
revisions and evidence links. Mark the material historical and non-normative.
Keep only notes and compact evidence that explain a decision or prevent an
expensive repeated investigation. Git history already preserves earlier
versions of committed code and documentation.

If an irreplaceable large historical artifact merits preservation, put it in
`tests/samples/provenance/<change-id>/` and describe it in a committed
`artifacts.json` alongside the historical note: sidecar-relative path, SHA-256,
bytes, provenance, retention purpose and retrieval/recreation instructions.
That history area is not an active fixture store; promote an artifact to a
maintained corpus if a current test starts requiring it. Do not retain raw
logs, diagnostic dumps, rendered review copies or repeated decodes by default
when the inputs, recipe and compact decision evidence suffice.

The existing `docs/provenance/archive/` holds selected imported records and
remains unchanged. The [provenance index](../provenance/README.md) supports
targeted historical lookup. Agents should read current guidance and the active
change record during normal work, and open a specific historical record only
when the task needs its rationale. History is not part of routine bootstrap
and cannot override current instructions. Keep credentials and private target
details out of both Git and shared sidecar history.

## Close the work directory

Closeout follows an accepted, rejected, abandoned or superseded change. Ending
a chat is not closeout. Work awaiting review or deliberately deferred remains
work in progress with a clear status and checkpoint.

1. Classify every owned artifact and resolve any uncertain retention decision.
2. Promote required code, tests, tools, current guidance and compact acceptance
   evidence to the repo; promote required large inputs to the sidecar and
   selected findings to their historical destinations.
3. Verify promoted copies against their recorded identities. Confirm that
   commands and tests use the durable paths and can run with the work directory
   unavailable. Check that the sidecar handoff includes the required files.
4. Record the validation, disposition, durable links and planned remote cleanup
   in the change closeout. Sanitize retained evidence and ensure repo
   promotions are included in the reviewed commit/checkpoint before deleting
   their only working copies.
5. Confirm no owned command is active, no other change depends on the directory,
   and the directory's identity/contents match its ownership record. Delete
   that exact work directory and its explicitly owned remote scratch.
   Do not follow links into the corpus or other shared/unowned directories.
6. Record the actual deletion outcome in the durable closeout outside WIP.
   Identify any incomplete cleanup and its owner rather than claiming closure.

The absence of a Git commit is not a deletion criterion. Directory ownership,
completed closeout and verified durable replacements are the criteria. Do not
prune `.local` by filename, age or extension. Unclassified legacy directories
require an inventory and disposition review; this forward-looking rule does
not authorize blanket cleanup of existing state.
