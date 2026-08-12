# Decoder maintenance workflow

Start decoder work from the repository-wide
[`change-management process`](../operations/change-management-v1.md) and the accepted
[`production baseline`](production-baseline.md), not from a source-code default
or a historical session configuration.

For a normal decoder improvement:

1. Start from this directory, the relevant source module, and the narrowest
   applicable tests.
2. State the behavior or resource problem and the contract it affects.
3. Make the smallest production change that can test the hypothesis.
4. Run focused deterministic tests first, then the full development-machine
   suite.
5. Use the received corpus or Pi only when the change affects real-recording
   quality or target-platform behavior.
6. Record durable design decisions and acceptance evidence in the current
   documentation; do not add an unmaintained session narrative to the
   current entry points.

The appliance integration work is intentionally deferred. Changes that cross
the decoder/application boundary should be planned separately from internal
decoder improvements.
