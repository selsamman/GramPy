# MIT licensing rationale and boundaries

## Intended license

GramPy is intended to be distributed under the MIT License. The project chose
a permissive license so that the decoder can be embedded in Radiogram and in
other communications, archival, research, and censorship-resistance systems
without imposing a copyleft license on those systems.

The repository's `LICENSE` file will be the license grant and must be added
before release. This document explains the project's licensing rationale and
boundaries; it does not replace or modify the license.

## Why the decoder can be MIT-licensed

GramPy's implementation was written for this project in Python using NumPy and
SciPy. The project used published MFSK materials as its protocol baseline and
examined fldigi as a reference implementation where later wire behavior was
missing or ambiguous. That research produced an independent behavioral wire
specification before and alongside an independently designed IQ receiver.

The project does not treat consultation of a GPL-licensed reference
implementation as transferring that implementation's license to functional
facts learned from it. Conversely, the MIT designation is not intended to
relicense any fldigi code: no fldigi source or binary is distributed as part
of GramPy, and no fldigi source code is knowingly incorporated in the decoder.
The supporting development account and the scope of the project's reasonable
provenance review are recorded in [`PROVENANCE.md`](PROVENANCE.md).

Protocol parameters and values necessary for interoperability are included in
the wire specification, data files, and tests with source and derivation
information. Project-authored descriptions, organization, implementation, and
tests are offered under the repository license.

## What the MIT license does not cover

The GramPy MIT license does not grant rights in:

- fldigi or any other third-party software;
- the MFSK publications and other documents cited as sources;
- separately installed received-IQ recordings;
- broadcast text, photographs, artwork, or decoded images contained in those
  recordings; or
- dependencies distributed separately under their own licenses.

Controlled miniature source images and generators committed under
`tests/fixtures/` were created for this project. Large fldigi-generated
transmissions used for compatibility testing remain external and are not part
of the source or wheel distribution.

Separately installed corpus material is not part of GramPy and is not licensed
under its MIT license. Corpus tools and tests operate on material selected and
supplied independently of the source distribution.

## Contributions and later discoveries

Contributors should submit only work they created or material they are
authorized to provide under MIT-compatible terms. Protocol research should
continue to distinguish functional behavior from third-party implementation
text and should identify sources for newly documented compatibility rules.

If material incompatible with the intended MIT distribution is discovered,
the project will evaluate that specific material and rewrite, remove, or
properly license it rather than treating the MIT label as a substitute for
provenance.
