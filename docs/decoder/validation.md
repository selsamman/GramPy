# Decoder validation

Use the accepted [`production baseline`](production-baseline.md) and the
repository-wide [change-management process](../operations/change-management-v1.md)
to select proportionate evidence. Candidate-set visual review is required when
the scorecard changes in image-related behavior or when a plausible visual
defect could escape the scorecard.

Validation has three complementary layers:

1. Deterministic unit and protocol-vector tests for wire mapping, framing,
   coordinates, state, and artifact contracts.
2. Controlled fldigi-derived fixtures for known transmission behavior and
   reproducible picture/text cases.
3. The received-IQ corpus for propagation, receiver, drift, fades, boundaries,
   and real-world regression evidence.

Development-machine tests establish IQ and algorithm behavior. Raspberry Pi
acceptance establishes fldigi/audio/runtime behavior, resource cost, and
unattended operation. Neither environment substitutes for the other.

An improvement should identify its affected contract, establish a baseline,
measure quality and resource effects, and retain a regression test or durable
evidence record before adoption. Historical scorecards and session gates are
intentionally not a repository dependency or current acceptance threshold.
