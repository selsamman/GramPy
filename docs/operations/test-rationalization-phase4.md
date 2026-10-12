# Test rationalization: phase 4

Date: 2026-10-12. Status: documentation prepared for review; no phase 4 commit.
Phase 3 remains staged separately. No existing scratch or corpus data has been
deleted or moved by this phase.

The [test-maintenance policy](test-maintenance.md) establishes:

- regular versus full-broadcast validation, including the explicit distinction
  between `all` and the selected four-broadcast gate;
- meaningful test creation, independent expectations, strict fixture failures,
  deliberate replacement/retirement and reviewed baseline revisions;
- `.local/wip/<change-id>/` ownership and a closeout rule that verifies durable
  replacements before deleting the exact owned directory;
- separate destinations for maintained test inputs, current instructions,
  selected historical findings and machine-private configuration;
- targeted historical lookup through the
  [provenance index](../provenance/README.md), outside routine agent reading.

AGENTS.md and change management carry the work-directory and closeout rules.
The [work-record template](work-record-template.md) supports ownership and
disposition notes without a per-file inventory of disposable generated output.
The [current broadcast guide](broadcast-regression.md) separates operating
instructions from the historical phase 3 findings.
The top-level README's obsolete missing-data skip claim is corrected. Test
instructions point to the maintenance policy, and new temporary commands use
the work-directory pattern while the wrappers' existing defaults remain valid.

This phase changes documentation only. Validation checked 52 local links in
13 documents with none missing, reviewed consistency against the existing
runner/wrapper interfaces, and passed diff whitespace checks. The phase 3
staged index remains unchanged (17 files); phase 4 is unstaged. No decoder,
test implementation, sidecar or workflow runner
was changed; another long corpus run is unnecessary for these documentation
changes. Existing legacy `.local` classification and cleanup remain phase 5.
