# GramPy Breakout Plan

This plan extracts the MFSK IQ decoder from Radiogram into a separate
GramPy repo to be published as a public repo. The decoder will then be
consumed in this project from PyPI. One of the folders, `tests/samples`, will
become a local directory with a `received-corpus` sub-folder built from
downloading a tarball from S3 and unpacking it. Unlike the current repository,
GramPy's `tests/samples` will not be symlinked from Dropbox.

## Execution status and project ownership

The technical work in Phases 1–4 is complete; their requested milestone commits
remain for the user to create. GramPy now lives in the real sibling checkout
`../GramPy`; Radiogram consumes it as an editable development dependency. The
former `GramPy` symlink and all `radiogram.mfsk` implementation have been
removed.

| Work | Project and owner |
| --- | --- |
| Completed separation, current temporary integration, and eventual PyPI dependency switch | Radiogram project |
| Corpus installation, GramPy clean-checkout validation, packaging, repository readiness, and release automation | GramPy project |
| Private GitHub publication and validation on another machine | User, operating on the GramPy project and GitHub |
| Public GitHub/PyPI release | GramPy project and user-controlled release accounts |

### History disposition

The full `history/` tree remains in Radiogram. It records the work that led to
the breakout and must not become a GramPy runtime, test, or documentation
dependency. Before the public GramPy release, review the history for the small
set of decision records or evidence worth copying or rewriting in GramPy;
remove private paths, operational details, and material not appropriate for the
public project. Do not use a symlink to share history between the repositories.

### Remaining work by project

**Run in GramPy**

1. Phase 5 corpus installation, including the history review above.
2. Phase 6 private GitHub validation.
3. GramPy's public repository, packaging, CI, and PyPI-release portions of
   Phase 7.

**Run in Radiogram**

1. Keep the editable `../GramPy` development dependency only until the public
   package is released.
2. After publication, complete the Radiogram-integration portion of Phase 7:
   declare the normal GramPy dependency, remove editable-install instructions,
   and test from a clean checkout against the exact published wheel/version.

**Run in both projects when Phase 7 begins**

1. Coordinate the selected package/distribution name, initial version, public
   API, and schema-identifier documentation.
2. Verify that the published package gives Radiogram the same regression
   behavior as the editable package.


## Phase 1 — Establish the boundary

1. Record a passing baseline for the current Radiogram repository.
2. Identify decoder-owned material:
    - `src/radiogram/mfsk/`
    - MFSK decoder tests
    - `tests/fixtures/mfsk/`
    - `tests/samples/received-corpus/`
    - MFSK schemas, tools, benchmarks, and documentation
3. Identify Radiogram-owned material that remains:
    - radio discovery and configuration
    - capture and daemon code
    - `iqprep.py`, except for the RSID detection types and logic required by
      the decoder. Copy that small self-contained portion into GramPy so that
      GramPy has no import of `radiogram.iqprep`. `iqprep.py` is temporary
      Radiogram code and will be removed before Radiogram production.
    - radio fixtures and capture samples
4. Inventory every MFSK-related item outside `src/radiogram/mfsk/`, including
   top-level tools, Pi scripts, fixtures, schemas, documentation/data files,
   benchmarks, and schema/output identifiers. Mark each item as moved to
   GramPy, retained as a Radiogram integration tool, or retired.
5. Identify all repository-relative resource lookups used by decoder code.
   Move required schemas and decoder data into GramPy package data, load them
   using package-resource APIs, and plan tests from an installed wheel.
6. Define GramPy's public callable API in `api.py` and decide the compatibility
   policy for existing `radiogram.mfsk.*` schema and JSON-output identifiers.
7. Keep `cli.py` with the decoder as a SigMF/testing/benchmark adapter. It is
   not the primary library interface.
8. Record the ownership, migration inventory, technical requirements, and
   temporary integration contract in
   [`docs/decoder/grampy_boundary.md`](docs/decoder/grampy_boundary.md).

## Phase 2 — Create the new GramPy project

A skeleton repo with `.git` has been established and is symlinked to this
project as `GramPy`. The symlink can be used to copy and move files. It
will be removed upon completion and testing of both radiogram and GramPy.
Move the decoder implementation, tests, tools, schemas,
documentation, package data, and a temporary local copy of the corpus into
GramPy. `tests/samples` in the current repo is symlinked to Dropbox; in the
new GramPy repo it will be a normal non-versioned directory. Only
`received-corpus` is needed, so do not copy other sample artifacts.

Do not add Dropbox references to GramPy.

## Phase 3 — Define the temporary sibling-package integration

1. Install GramPy from the temporary sibling symlink into Radiogram's virtual
   environment as an editable development dependency.
2. Update Radiogram imports to use only GramPy's public `api.py` interface;
   do not retain compatibility imports from `radiogram.mfsk`.
3. Move decoder tests to GramPy. Retain or add focused Radiogram integration
   tests that exercise the installed sibling package through the call paths
   Radiogram will use in production.
4. Document this explicitly temporary arrangement, including the exact local
   installation command and that it must be replaced by a normal PyPI
   dependency in Phase 7.
5. Confirm this state proves the intended property: the decoder was neither
   inadvertently deleted nor still supplied by source left in Radiogram.

## Phase 4 — Cut the temporary symlink

Run both projects in their current shared development arrangement and confirm:

- GramPy decoder tests pass with the temporary local corpus.
- Radiogram tests pass while consuming the editable sibling GramPy package.
- Radiogram has no remaining `radiogram.mfsk` implementation or imports.
- Required files were moved rather than omitted.
- No GramPy code depends on Dropbox.
- No GramPy code depends on Radiogram, repository-relative resource paths, or
  absolute paths.

A fresh-checkout test is not required in this phase because the corpus is
`.gitignore`d and the installation mechanism has not yet been added.

Then:

1. Remove the temporary symlink.
2. Reinstall GramPy into Radiogram's virtual environment from GramPy's real
   checkout path (not the removed symlink), then rerun both projects' tests.
   This is the code-separation proof that the decoder was moved intact and
   Radiogram is consuming the package rather than leftover source.
3. Commit GramPy as a code-separation milestone, even though a clean checkout
   cannot yet run corpus-dependent tests.
4. Commit Radiogram in its still-working temporary local-package state. Its
   setup documentation must make clear that this local development dependency
   is temporary; the Phase 7 PyPI integration is the durable installation path.

This milestone represents the completed code separation, not a distributable
GramPy release.

**Completed:** the temporary symlink was removed; GramPy was reinstalled from
the real `../GramPy` checkout; GramPy's 140-test suite passed with 6 skips; and
Radiogram's 90-test suite passed with 2 skips. No source, test, or tool under
`radiogram.mfsk` remains in Radiogram.

## Phase 5 — Add manual corpus transfer tools (run in GramPy)

The corpus is too large for Git, but it is not a versioned dependency selected
by the repository. Corpus-dependent tests use an existing local corpus and
skip when it is absent. No test or evaluation command automatically downloads
one.

`tools/package-corpus` updates the corpus `version.json`, creates a `.tar.zst`
archive, and prints its SHA-256. Optional encryption prompts for a password
without retaining it. `tools/fetch-corpus` requires an explicit URL and
SHA-256 on every invocation, optionally prompts for the archive password,
validates the archive and version file, and atomically installs it. There is no
repository manifest, stored credential, or local/repository version
synchronization.

The operating instructions live in `tests/README.md`, not the project README.
A clean checkout can run the test suite without a corpus; installing one is a
separate manual action.

## Phase 6 — Private GitHub validation (user, in GramPy)

Publish GramPy to a private GitHub repository.

On another machine:

1. Clone GramPy.
2. Set up the virtual environment.
3. Run the documented setup process.
4. Confirm the corpus downloads.
5. Run the full GramPy test suite.
6. Confirm the package and tools work without any symlink or Dropbox path.

Do not clone or retest Radiogram in this phase; that separation has already
been validated.

At the end of this phase, commit Radiogram's working non-public arrangement.

## Phase 7 — Complete the public PyPI conversion (GramPy release, then Radiogram)

This phase converts GramPy from the private validation project into the public
Python library and updates Radiogram to consume the published package.

### Public GramPy repository

- [ ] Final public repository name, description, and topics
- [ ] Open-source `LICENSE`
- [ ] Correct author and copyright information
- [ ] Complete README
- [ ] Installation instructions
- [ ] Usage examples for `api.py`
- [ ] SigMF adapter and CLI documentation
- [ ] Corpus setup instructions
- [ ] Development, test, and benchmark instructions
- [ ] Architecture overview
- [ ] Known limitations
- [ ] Complete separate IP, provenance, and redistribution-license review for
  the corpus, fixtures, derived artifacts, and documentation
- [ ] `CONTRIBUTING.md`
- [ ] `AGENTS.md`, if desired
- [ ] `SECURITY.md`
- [ ] `CHANGELOG.md` or release notes
- [ ] Code of conduct, if desired
- [ ] Issue and pull-request templates, if desired
- [ ] No credentials, private URLs, Dropbox paths, or local paths committed
- [ ] No corpus archive committed to Git

### Python packaging

- [ ] Final distribution name and import name
- [ ] Complete `pyproject.toml`
- [ ] Supported Python versions documented and configured
- [ ] Runtime dependencies declared
- [ ] Optional development and test dependencies declared
- [ ] Package data and decoder schemas included in builds
- [ ] Console scripts clearly identified as optional tooling
- [ ] License metadata present
- [ ] Project URLs present
- [ ] Version number selected
- [ ] Wheel build succeeds
- [ ] Source distribution build succeeds
- [ ] Installation works in a clean virtual environment
- [ ] Public API import works after installation
- [ ] No dependency on repository-relative paths
- [ ] Package tested from the built wheel, not only an editable checkout
- [ ] Package-resource schemas and decoder data work from the built wheel

### Public automation and release

- [ ] Publish the reviewed GramPy source repository on GitHub before its first
  production PyPI release
- [ ] Create and push the release tag from the reviewed source revision
- [ ] GitHub Actions test supported Python versions
- [ ] CI runs corpus-independent tests without fetching a corpus
- [ ] Explicit corpus fetching remains checksum-verified
- [ ] Build validation runs in CI
- [ ] Package installation validation runs in CI
- [ ] Release and tagging procedure documented
- [ ] PyPI publishing credentials configured securely
- [ ] Test-index publication performed if useful
- [ ] First public PyPI release published from the tagged GitHub workflow
- [ ] Public GitHub release created for the same tag
- [ ] Published package can be installed with `pip install`

### Radiogram integration

Update Radiogram to consume the published GramPy package rather than a local
symlink or editable sibling checkout.

- [ ] Add GramPy to Radiogram's normal package dependencies
- [ ] Use the selected minimum GramPy version or compatible version range
- [ ] Remove temporary local/editable GramPy installation instructions
- [ ] Update Radiogram imports to use GramPy's public `api.py` interface
- [ ] Remove remaining imports of moved `radiogram.mfsk` internals
- [ ] Update Radiogram's packaging and lock/dependency documentation
- [ ] Update Radiogram README setup instructions
- [ ] Run Radiogram tests after a normal `pip install` of GramPy
- [ ] In a clean environment, install the exact published GramPy wheel/version
  declared by Radiogram and run its integration and regression tests
- [ ] Test Radiogram from a clean checkout with no symlink and no Dropbox
- [ ] Verify decoder behavior against the expected regression results
- [ ] Commit the completed published-package integration

## Completion criteria

The breakout is complete when:

1. GramPy is public on GitHub.
2. GramPy is installable from PyPI with `pip install`.
3. A clean GramPy checkout runs without a corpus, while an explicitly selected
   corpus can be installed through `tools/fetch-corpus`.
4. Radiogram installs GramPy as a normal Python dependency.
5. Radiogram passes its tests without a symlink, Dropbox, or local GramPy
   checkout.
6. The temporary breakout plan can be deleted after the work is reviewed and
   completed.
