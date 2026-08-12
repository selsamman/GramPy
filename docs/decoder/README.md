# Direct MFSK decoder

The decoder is a working production component. Future work should be
incremental maintenance and measured improvement, not a continuation of the
completed Session 1–11 implementation sequence.

Read the documents in this order:

1. [`design.md`](design.md) for enduring architecture and design rationale.
2. [`contracts.md`](contracts.md) for behavior that must remain stable.
3. [`validation.md`](validation.md) for evidence and acceptance methodology.
4. [`maintenance.md`](maintenance.md) for the normal change workflow.
5. [`production-baseline.md`](production-baseline.md) for the currently
   accepted decoder configuration and acceptance evidence.

Normative protocol behavior is in [`mfsk_wire_spec.md`](mfsk_wire_spec.md).
Corpus policy is in [`mfsk_received_corpus.md`](mfsk_received_corpus.md), with
the selection seed in [`corpus/received_corpus_seed.json`](corpus/received_corpus_seed.json).
Machine-readable vectors, Varicode, and fixture evidence are under
[`data/`](data/).

The versioned documents and data in this directory are the durable decoder
record. Historical development notes are intentionally not a GramPy
dependency.
