# Change Management v1

## Purpose and boundary

This is the repository-wide process for short-lived changes that can be
independently accepted into production. It applies to quality improvements,
performance work, bug fixes, refactors, features, corpus/scoring work, and
operational changes.

It does not define a long-lived branch/PR workflow or a multi-phase effort
held outside production until all phases finish. Those belong to a later
version of this process. A larger roadmap may contain several independently
accepted changes; each one follows this process on its own.

A session is not a phase or an acceptance boundary. Investigation may span
sessions. When an approach is abandoned, retain the durable evidence and start
a fresh investigation/candidate cycle rather than carrying discarded reasoning
forward.

## Core cycle

1. **Request.** Product management states the desired outcome, constraints,
   urgency, and known risks.
2. **Define.** Create `.local/wip/<change-id>/WORK.md` to record ownership,
   status, baseline, artifacts and their intended disposition. Write a
   proportionate change note or specification. Non-trivial
   work identifies scope, exclusions, baseline, acceptance evidence, and any
   notional session boundaries. Commit this definition as a restore point.
3. **Investigate.** When uncertainty warrants it, run focused experiments or
   compare alternatives without changing accepted production behavior.
4. **Candidate.** Describe each production candidate as a minimal, explicit
   delta from the accepted baseline and state expected quality, performance,
   compatibility, and platform impact.
5. **Evaluate.** Collect the evidence appropriate to the affected behavior.
6. **Decide.** Product management accepts, rejects, defers, or requests a
   further investigation cycle. A score improvement alone is not acceptance.
7. **Integrate.** Make the accepted candidate the in-place production change;
   run final regressions. Commit this production checkpoint.
8. **Close.** Update the production baseline, durable documentation and tools.
   Promote required inputs and selected historical findings, verify their
   identities and validation with scratch unavailable, and record disposition
   in the change closeout. Delete the exact owned work directory after confirming
   no active run or dependent change remains. Commit this closure checkpoint.

The requester may combine the integration and closure commits for a genuinely
small change. Keeping them separate is preferred when the cleanup, artifacts,
or baseline update are material.

Commit steps describe review checkpoints; agents still require explicit user
authorization to create commits under AGENTS.md. Ending a session does not
close a change. Deferred work and work awaiting review keep their recorded
WIP state until their disposition is resolved.

## Work modes

Work mode describes how a change is developed; it does not replace the core
cycle.

- **Sidecar/alternative:** candidates or experiments run alongside accepted
  production. Use for competing algorithms, quality improvements, performance
  alternatives, and uncertain designs.
- **In-place controlled:** the production structure must change while the
  work is underway. Use for refactors, package extraction, pipeline
  organization, or compatible API evolution. Establish behavior-lock tests
  and before/after evidence first.
- **Configuration-only:** a supported setting changes without changing code
  structure. Qualify the new default like any other production candidate.
- **Urgent fix:** use an abbreviated definition and evaluation only when the
  urgency is explicit; complete the missing closeout evidence afterward.
- **Evidence/infrastructure:** corpus, scoring, review, fixture, or monitoring
  changes. These use the same process, but their acceptance evidence concerns
  measurement integrity rather than a product-output improvement.

## Baselines and candidate identity

Every evaluation must name the relevant immutable inputs:

- product baseline: source revision, pipeline organization, configuration, and
  accepted manifests/artifacts;
- corpus baseline: recordings, truth, expected outcomes, and corpus revision;
- reference baseline: pinned external decoder/build and its outputs when used;
- performance baseline: platform, timing, memory, I/O, and target feasibility.

Do not call a source-code default "production" unless it is the accepted
product baseline. A candidate record must state exactly what differs from that
baseline. Baselines change only during the close step after product acceptance.

## Evidence proportionality

Trust a scorecard when it covers the affected behavior and there is no credible
reason the change could create an important defect it would miss.

| Change/evidence condition | Required evaluation |
|---|---|
| Covered scorecards unchanged and no plausible unmeasured impact | Relevant regression tests and scorecards; no visual review required. |
| Image/raster score changes | Scorecards and candidate-set visual review. |
| Plausible visual risk despite unchanged scores | Candidate-set visual review, for example when alignment can hide a localized raster defect. |
| Performance, concurrency, allocation, or I/O change | Correctness/compatibility tests plus measured time, memory, I/O, and target feasibility. |
| Protocol, encoder, or bit-perfect feature | Golden vectors, exact-byte/hash assertions, error-path tests, and interoperability evidence where available. |
| Corpus or scorer change | Versioned inputs, migration/coverage report, and proof that the measurement remains valid. |

For visual output, use a **candidate-set N-up review**:

`truth · accepted production baseline · each surviving candidate · pinned external reference`

The number of columns is therefore `3 + candidate count`; do not hard-code a
four- or five-column limit. Only candidates that remain credible after focused
evaluation need appear in the final review.

## Target-Pi qualification

These checks govern acceptance for deployment on the target Pi. Publishing a
generic library package to PyPI is a separate release decision; a consumer
deployment can qualify the package on its own schedule.

Pi evidence is required when a change affects device integration, deployment,
runtime/dependency behavior, memory allocation, buffering, I/O, concurrency,
or target-platform performance; when Mac evidence approaches known Pi limits;
or when the production decision depends on target feasibility.

A production decoder change with broad corpus impact normally requires at
least a representative Pi subset: affected mode(s), one difficult recording,
and one normal recording. Use the full Pi corpus when the change is broad, the
subset finds a concern, or the release decision depends on target performance.

Mac-only evidence may be sufficient for a pure algorithm/configuration change
when formats, I/O pattern, concurrency, memory behavior, and dependencies are
unchanged and the measured cost change is modest. Record the rationale for
skipping Pi in the decision record.

## Roles and decisions

Product management owns scope, tradeoffs, and acceptance. The implementer
provides an evidence-backed recommendation and must distinguish observation,
inference, and unresolved risk. External-reference agreement is useful
evidence, not proof of correctness.

## Durable and historical material

- Current domain docs hold supported behavior, operating process and baseline
  entry points; concise change records hold decisions and closeouts.
- `docs/provenance/changes/<change-id>/` holds selected native historical
  findings and compact evidence, with source revisions and a retention purpose.
  These are for targeted investigation, not routine agent reading.
- `experiments/<change-request>/` holds active, checked-in experiments that
  materially inform a pending decision.
- `tools/` holds reusable, stable commands and review/scoring infrastructure.
- `src/` holds product behavior and supported runtime configuration.
- `tests/samples/` holds the external sidecar: maintained large test inputs and
  qualified reference outputs. Selected large historical artifacts may go in
  its `provenance/<change-id>/` area with a committed artifact manifest; current
  tests must not depend on that history area.
- `.local/wip/<change-id>/` holds owned temporary commands, notes, logs and
  generated outputs while a change is open. Required evidence is promoted
  before closeout; the owned directory is then deleted.
- Machine-private configuration, target files and secrets remain elsewhere in
  `.local/` with their own lifecycle. Managed runner state follows AGENTS.md.

Do not copy an external project's entire history or preserve every intermediate
output. Retain the decision records and selected findings needed to maintain
GramPy or understand a costly investigation. Distill supported behavior into
current documentation; label historical material separately and keep it out
of bootstrap and normal test dependencies. Git preserves previous committed
versions. Existing imported provenance and historical records need not move
when adopting this forward-looking policy.

The [test-maintenance and closeout policy](test-maintenance.md) defines the
artifact dispositions, promotion checks, test-retirement process and exact
work-directory cleanup procedure. Legacy `.local` directories require their
own inventory/disposition review rather than deletion by name or age.

## Version 2 boundary

Version 2 may add branches, pull requests, agent-managed commits, long-lived
multi-phase work held outside production, and corresponding review/merge
rules. Those additions should extend this core cycle rather than replace it.
