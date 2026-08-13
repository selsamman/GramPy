# GramPy provenance

**Status:** pre-publication draft; historical-document review complete,
targeted source sanity check pending

## Purpose and scope

GramPy is an independently written Python, NumPy, and SciPy decoder for the
MFSK32, MFSK64, MFSK picture, and RSID wire behavior used by Shortwave
Radiogram. This document records the development method and the reasonable
provenance review performed before public release. It is not a representation
that GramPy was developed without consulting prior implementations, nor is it
an exhaustive comparison with all earlier software.

This record covers the intended provenance boundary for the GramPy source
code, protocol data, tests, and decoder documentation. It does not clear or
license the separately stored received-IQ corpus. That corpus contains
third-party broadcast material and is not intended to be part of the public
GramPy distribution.

## Development method

The project deliberately separated protocol research from decoder design:

1. The published circa-2000 MFSK specification, explanatory articles, and
   IZ8BLY MFSK Varicode publication were used as the starting point.
2. The published material did not completely specify the later MFSK32,
   MFSK64, and picture behavior required for interoperability. Version-pinned
   fldigi source and controlled fldigi transmissions were therefore examined
   to resolve gaps and ambiguities.
3. Findings were recorded as externally observable wire behavior in
   [`docs/decoder/mfsk_wire_spec.md`](docs/decoder/mfsk_wire_spec.md). Rules in
   that document distinguish published, version-specific, common, derived,
   controlled, and received-capture evidence.
4. The receiver was designed separately from the wire investigation. Its
   architecture, contracts, evidence model, and algorithms were developed for
   offline IQ processing in Python with NumPy and SciPy rather than by porting
   fldigi's C++ receiver architecture.
5. Implementation proceeded through independently testable vertical slices.
   Protocol vectors, synthetic DSP cases, controlled fldigi-generated
   transmissions, and received IQ served different validation roles. Fldigi
   output was treated as a version-pinned compatibility reference, not as
   automatic ground truth.

The intended boundary was stated before decoder implementation in
[`docs/decoder/direct_decode.md`](docs/decoder/direct_decode.md): inspect
fldigi where necessary to document interoperability behavior, but do not copy
its code or prose. The fldigi checkout remained under an ignored local
reference directory and is not included in GramPy.

This was a clean-room-oriented protocol-documentation process, but this record
does not claim the strictest formal clean-room model in which the people or
agents implementing the decoder had no exposure to the reference source. The
claim is narrower: GramPy was written as an independent implementation of the
published and documented wire behavior, and no fldigi source code is knowingly
incorporated in it.

## Protocol facts and project expression

Interoperability requires GramPy to use the same functional parameters and
wire values as compatible transmitters and receivers. These include tone
counts and spacing, convolutional-code masks, Gray labeling, interleaver
orientation, timing values, state transitions, picture mappings, and
Varicode encodings. GramPy records the source and derivation of those facts in
the wire specification and its machine-readable companions.

The complete Varicode mapping is stored in an original octet-indexed JSON
representation and is attributed to the published IZ8BLY MFSK Varicode. Fixed
wire vectors were derived or mechanically verified as protocol evidence; they
are not copies of fldigi source declarations or tests.

Names of fldigi files, functions, versions, and commits appear in the
documentation solely to identify the evidence used to establish behavior.
Controlled audio or IQ produced by running fldigi is recorded as generated
compatibility evidence. Large generated artifacts and fldigi binaries or
source are not distributed in this repository.

## Retained supporting record

The decoder was developed before GramPy was extracted from its parent
Radiogram project. A small set of planning and early session records is
preserved verbatim under [`docs/provenance/archive/`](docs/provenance/archive/README.md).
Their hashes identify the reviewed copies without importing the parent
project's commit history into GramPy.

| Archived record | SHA-256 | Relevance |
| --- | --- | --- |
| [`direct_decodeing_from_iq_approach.md`](docs/provenance/archive/direct_decodeing_from_iq_approach.md) | `d33a7964d4bd4ca27e83d3f9e023cf4b5680f85459a77bcbb8c86018d86420e8` | Establishes the published-specification baseline, narrow fldigi inspection, wire specification before coding, and independent Python receiver plan. |
| [`mfsk_iq_decode_designspec_guidelines.md`](docs/provenance/archive/mfsk_iq_decode_designspec_guidelines.md) | `444cb69c273a8e261658c79757f8b7490c628d09fa431137603115e242304158` | Separates the completed wire investigation from receiver architecture and evaluates independent candidate algorithms. |
| [`mfsk_iq_decode_implementation_spec.md`](docs/provenance/archive/mfsk_iq_decode_implementation_spec.md) | `2a229ddffcfb6ac719a5e993e7f3fa5468ce4172583faf10f7abcfbbac624f23` | Defines the Python IQ decoder's contracts, evidence model, pipeline alternatives, and validation hierarchy. |
| [`mfsk_iq_decode_session1.md`](docs/provenance/archive/mfsk_iq_decode_session1.md) | `2dca1484a8dd580e1d50a8d47eee50b22843b76c1af31d20079283ee42e06f91` | Records the initial independent package and diagnostic harness. |
| [`mfsk_iq_decode_session2.md`](docs/provenance/archive/mfsk_iq_decode_session2.md) | `055bdb3a1acd18af9051abeff06ce3200d5c6dc28bdeef315ed0892a2351ab2c` | Records isolated, version-pinned fixture generation and verification. |
| [`mfsk_iq_decode_session3.md`](docs/provenance/archive/mfsk_iq_decode_session3.md) | `6c47b52fcded14758d42cd0b24a818fd4d9ca2e3a89579f2e71a658084e3cf7e` | Records the first complete NumPy IQ-to-text vertical slice and its independent controlled evidence. |

These records support the development account. They are not current design
requirements and are not required to build, use, or maintain GramPy. If the
parent repository and its commit history survive, they provide an additional
check on the preserved record.

## Review status and limitations

The pre-publication provenance review is intentionally proportionate to this
open-source project's practical risk. The first step reviewed the development
method and the retained Radiogram records listed above. Those records show a
consistent plan to establish wire behavior first and implement an independent
Python receiver against that specification.

Before this statement is finalized, a focused sanity check will cover only the
areas with a direct provenance relationship to fldigi: the wire specification,
coding tables and vectors, interleaving, convolutional coding, picture mapping
and timing, and fldigi-specific references. It will look for evident copied
source or prose; it will not attempt a forensic, line-by-line comparison of the
entire GramPy repository with every version of fldigi.

As of August 12, 2026, the historical-document review found no indication that
copying fldigi source code or prose was part of the development method. The
final statement should record the result of the focused sanity check. If a
specific provenance concern is later identified, it should be examined on its
facts and the affected material rewritten, removed, or licensed as
appropriate.
