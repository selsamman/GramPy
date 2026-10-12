# Test coverage and rationalization audit

Date: 2026-10-11. Scope: GramPy at commit `2126385`, the standard
`unittest discover -s tests` suite, CI/release invocation, retained qualification
workflows, and dependencies on the sidecar corpus and controlled fixtures.

This is an audit and proposed maintenance backlog. No production code, tests,
fixtures, corpus files, acceptance limits, or defaults were changed. No commits
were created. Recommendations to retire tests are separate from authorization
to implement them.

Subsequent repairs are recorded separately in
[phase 1](test-rationalization-phase1.md) and
[phase 2](test-rationalization-phase2.md). This inventory describes the original
baseline, including its six fixture skips; it is not a current-suite verdict.

## Findings

1. **The standard suite does not enforce the accepted real-corpus decoder
   quality baseline.** It tests scoring arithmetic, some received-recording
   behaviors, generated round trips, and protocol contracts. It does not run
   fresh corpus decodes through the paired GramPy/fldigi quality evaluation and
   assert the approved limits. CI and release explicitly run a
   corpus-independent suite. A pass is not evidence that corpus-wide text or
   picture quality has been preserved.
2. **Six methods depend on unavailable pinned fldigi-generated recordings.**
   They skip, including when the received-IQ sidecar is installed. They consume
   transmitter WAV/IQ fixtures and committed expected measurements, not saved
   fldigi receiver text/images. These are not the scorecard comparison tests.
3. **Some passing tests validate old documents or oracle metadata rather than
   today's decoder behavior.** Their passing status should not count as fresh
   interoperability or quality evidence. Specific retirement candidates are
   identified below; most historical session names still contain useful tests.
4. **There are consolidation opportunities, but newer end-to-end tests do not
   automatically supersede older focused checks.** Independent oracles,
   negative cases, file safety, memory bounds, and explicit state provenance
   frequently protect faults that a successful round trip would miss.
5. **Practical gate sensitivity tests are outside normal discovery.** Six
   tests in `experiments/mfsk-wav-encoder/test_session9_broadcast.py` check blank
   images, geometry, colour bias, non-exact valid output, text ordering and
   protocol controls. The normal `tests/` suite does not discover that file.
6. **The quality CLI publishes a result without enforcing its verdict.**
   `accuracy_cli.main` returns zero after successfully writing a planning-gate
   report, even if that report has `passed: false` or `computable: false`.
   An acceptance runner must explicitly check those fields. The existing
   unpaired-case test intentionally expects report generation to succeed;
   changing that command's semantics requires a deliberate CLI decision.

## Evidence and limits of this audit

The accompanying [method inventory](data/test-coverage-audit/inventory.md)
lists every standard discovered method with observed status, elapsed time,
input tier, proposed disposition, reason and any specific consolidation target.
[Run evidence](data/test-coverage-audit/run.json) records the actual suite run.
[Detailed inventory](data/test-coverage-audit/inventory.json) also records direct
calls and assertion expressions to make the recommendations reviewable.

The inventory covers **248 methods in 42 test modules**, plus identifies six
practical-gate tests outside standard discovery. Test helpers and checked-in
fixture generators are supporting assets, not extra discovered test methods.

### Observed execution and dispositions

The final managed Mac run completed successfully: **248 methods, 242 passed,
six skipped, zero failures/errors**, in approximately **145 seconds** of test
execution (146 seconds for the managed command). The received-IQ sidecar was
present. All six skips were the controlled-fixture methods listed below;
the six received-IQ methods and saved-manifest case ran successfully.
See the [managed completion record](data/test-coverage-audit/result.md).

| Proposed disposition | Methods |
| --- | ---: |
| Keep | 232 |
| Repair missing-data integration | 5 |
| Consolidate (including strict fixture integrity preflight) | 4 |
| Retire from current product suite, with stated replacement/rehome conditions | 4 |
| Rewrite experiment-ranking assertion | 1 |
| Split runtime/package assertions from editorial prose assertions | 1 |
| Reclassify saved-manifest check | 1 |

These labels summarize proposals, not measured post-removal savings. The six
missing-fixture checks comprise five repair recommendations and one integrity
consolidation. None has been deleted. The six practical-gate tests outside
standard discovery were inspected but not executed in this audit.

This is a behavioral and dependency audit, not line/branch instrumentation.
No coverage percentage is claimed. Runtime is a single Mac observation, not a
benchmark. A keep recommendation means useful contract coverage was identified;
it does not prove completeness. Consolidation candidates have not been removed
or mutation-tested. Direct method call lists omit helper-mediated dependencies;
those were reviewed separately for the fixture and corpus cases.

Primary sources:

- [CI](../../.github/workflows/ci.yml) and
  [release workflow](../../.github/workflows/release.yml).
- [Accepted decoder configuration/evidence](../decoder/production-baseline.md).
- [Decoder validation](../decoder/validation.md), which explicitly excludes
  historical session gates from current acceptance thresholds.
- [Change-management process](change-management-v1.md), which requires
  proportionate evaluation and product acceptance, rather than defining an
  automatically executed quality regression.
- [Encoder validation](../encoder/validation.md), including the accepted v3
  practical matrix.
- [Historical quality evaluation](../../experiments/auto-mfsk32-pictures/evaluate.py).

## What the six missing-fixture tests actually protect

| Method (file and class are in the inventory) | Input and check | Recommended treatment |
| --- | --- | --- |
| `test_pinned_iq_decodes_to_exact_final_octets_with_coordinates` | fldigi-generated MFSK32 IQ; known transmitted bytes, carrier/mode, STX/EOT and event coordinate invariants | Repair as an independent transmitter interoperability case; retain coordinate assertions independently of quality metrics. |
| `test_controlled_iq_decodes_exact_octets_through_shared_pipeline` | fldigi-generated MFSK64 IQ; known bytes, carrier, tone spacing, symbol timing and no intermediate files | Repair in the same controlled-fixture suite. |
| `test_grayscale_header_transition_and_complete_raster` | fldigi-generated 8x4 grayscale IQ; header, shape, component count, completion and original-recording raster timing | Repair if a validated replacement is adopted; derive recording-specific timing from the replacement's independently reviewed evidence. |
| `test_color_header_row_plane_assembly_and_reacquisition` | fldigi-generated colour IQ; header/shape, component count, prologue relation and return-to-text interval | Repair; the current assertions do not compare pixel values against fldigi's decoded image. Add or retain appropriate source-truth fidelity coverage. |
| `test_controlled_text_can_use_bounded_organization` | the MFSK32 fixture; forces the bounded pipeline and verifies text and organization | Replace its input with a maintained integration case that actually exercises the bounded branch. Generated or received input is possible, but independent fixture coverage must remain separately if retained as a requirement. |
| `test_available_pinned_artifacts_match_all_hashes` | inventory of WAV/IQ/metadata files against recorded hashes | Consolidate integrity checking into one strict sidecar preflight, retaining negative integrity tests. |

The originals were already missing at encoder Session 1 and in the October 3
pre-cleanup regression report. This audit does not establish a deletion event.
All four regenerated sets exist in the sibling Radiogram archive. The Pi has
the corresponding WAVs; their hashes match those regenerated sets, not the
original expectations. The Pi's actual pinned fldigi transmitter binary hash
matches the committed generator identity. No original matching WAVs were found
in `/opt/radiogram` or `/home/pi` during the read-only search. This was not a
whole-device forensic search or an inspection of every archive member.

Machine paths and inspection logs remain private under `.local/`. Do not
silently replace expected hashes: generated capture timing/length differs and
the old exact sample positions are recording-specific. These cases could be
re-established with independently validated replacement inputs, but exact
original artifact recovery/reproduction has not been demonstrated.

## Retirement and consolidation decisions

### High-confidence candidates to remove from the current product suite

These checks no longer justify being described as current product regressions.
Their documents can remain historical provenance. If a historical reproduction
workflow is deliberately supported, its contract tests can live with that
workflow and run explicitly instead.

| Candidate | Why it is not current behavior coverage | Coverage to preserve before retirement |
| --- | --- | --- |
| `PiQualificationContractTests.test_matrix_has_the_required_interoperability_coverage` in `test_mfsk_encoder_evidence.py` | Freezes the v1 matrix and manual segment-window receiver runs; accepted qualification now uses the v3 whole-WAV practical matrix. | Test the active v3 matrix's required mode/speed/composition coverage and qualification settings. v3 is not a structurally identical replacement. |
| `PiQualificationContractTests.test_pi_manifest_schema_is_valid_and_requires_hashes_and_outcomes` in the same file | Validates a synthetic record against the historical v1 schema, not a current qualification run. | Validate the actual schema/record consumed by the maintained qualification path. Keep v1 validation explicitly only if its reproduction workflow remains supported. |
| `RsidOracleTests.test_draft_pi_contract_requires_continuous_rxid_acquisition` | Checks the historical v2 draft matrix's exact case count/settings. Useful RSID generation checks in the other two methods do not require that draft contract. | Assert the still-required whole-input RxID behavior against the maintained practical workflow; keep v2 compatibility testing separately if required by historical tooling. |
| `OfflineEncoderOracleTests.test_frozen_reference_wav_measurements_remain_exact` | Reads committed JSON numbers and checks them against more constants; it never reads a WAV or performs a measurement. Its name implies more runtime coverage than it provides. | Centralized provenance/hash validation can retain document identity. Actual fixture decoding/measurement or maintained quality checks must provide behavior coverage. |

These are recommendations, not claims that an existing test already covers
every assertion. The first three should be replaced by active-contract checks
before their disappearance is treated as a net coverage improvement.

### Consolidation candidates with explicit caveats

| Older/check overlap | Recommended survivor or destination | What must not be lost |
| --- | --- | --- |
| R3 `test_varicode_checkpoint_is_chunk_equivalent_and_has_provenance` and 11C `test_varicode_source_coordinates_survive_checkpoint` | One parameterized parser checkpoint test based on 11C | R3 checks confidence `0.8` and source **bit** intervals; 11C checks source **input** intervals. Transfer all three assertions before retiring R3. |
| Decoder session1 FEC/Gray vectors and encoder session2 FEC/Gray checks | One protocol test group with separate implementation entry points | They call different APIs (`convolutional_encode` versus `StatefulTextToneEncoder`). Shared vectors alone do not make them redundant. |
| Wire-vector, encoder-evidence and fixture-inventory document checks | One provenance/integrity group | Retain independent equations, all-octet validity, packaged-copy identity and malformed/missing/mismatched data behavior. Remove repeated checks of the same constants only after mapping them. |
| `MfskWireVectorTests.test_complete_varicode_table_has_required_structure` | `OfflineEncoderOracleTests.test_all_varicode_octets_are_exact_and_uniquely_terminated` | The survivor already checks structure/terminators/uniqueness and all fixed octets used by the older test. Transfer the older test's schema assertion before deleting it. Production `varicode_codeword` tests must remain: oracle-data validation is a different layer. |
| Session3 text round trip, session5 picture round trip, session6r2 automatic acquisition, and mixed-picture public API round trip | Organize as one integration matrix; retain focused low-level checks where they isolate distinct paths | Fixed-mode hints, explicit framing, both-mode/repeated-mode acquisition, audio boundaries, recovered pixels, and return-to-text are different failure surfaces. No wholesale deletion justified. |
| Decoder session6 synthetic clocks and R4 picture evidence | Consolidate shared signal/header setup | R4 adds fractional clocks, ranked boundaries, drift/steps and bias. Session6 covers grammar and local frequency-track mapping. Preserve distinct assertions. |
| Session12A API/CLI defaults | One defaults test group with two entry points | CLI and API can drift independently. Do not remove one merely because defaults match today. |
| Encoder session7 metadata/export/documentation test | Split package/API checks from prose assertions | Keep exports, dependencies and absent encoder CLI contract. Exact documentation phrases such as `library-only` are fragile editorial assertions and can be removed from runtime tests or handled by documentation review. |
| `test_text_manifest` full-broadcast reference check | Keep as a stored-manifest compatibility case in the sidecar tier | It transforms a saved GramPy manifest; it does **not** decode the recording. Rename/classify accordingly rather than crediting it as decoder quality coverage. |

### Tests that look historical but should stay

- Session10B's `phase_difference` cases: the estimator is still exposed in
  `DecodeConfig` and CLI choices. Keep correctness/quantization coverage. The
  experiment's relative ranking (`phase_difference` better than `fft_peak` on
  one ramp) is a candidate to rewrite as per-estimator correctness limits;
  changing relative ranking can be an improvement, not a regression.
- Session10F's `test_experimental_change_score_recovers_synthetic_boundary`:
  despite its name, `_locate_protocol_change` is still used as the current
  unified grid's local change guard. Keep and rename around its maintained
  behavior, not an obsolete experiment.
- R3/11C checkpoint, unknown-start, confidence-aware grammar, dropout,
  rollback and bounded-state tests: integration success does not prove these
  edge contracts.
- Encoder waveform/oracle, phase continuity, file-alias/preflight, write
  failure and cleanup tests: exact encoder output and filesystem behavior are
  valid contracts, separate from noisy receiver quality.
- Session11E parallel range, edge, cancellation, bounded-read, compact-state
  and routing tests: essential properties absent from simple quality metrics.
- Scorer alignment, raw channel bias, missing-truth, CER and aggregation tests:
  necessary to trust a future quality gate. They do not substitute for running
  that gate on real data.

## File-level coverage map

Counts and individual dispositions are in the inventory. This map explains
why each area belongs in the suite and which layer it exercises.

| Test file/group | Behavior protected | Disposition |
| --- | --- | --- |
| `test_analyze_mfsk_color_fixture` | Finds known row-plane raster in independently constructed signal | Keep analysis-tool correctness. |
| `test_auto_picture_roundtrip` | Public automatic mixed-picture decoding, file identity/order, fidelity and resumed text | Keep coupled integration; not external decoder quality. |
| `test_auto_segmented_decode` | Mode dispatch, order/IDs, error isolation | Keep mocked orchestration, complementary to integration. |
| `test_cli_public_api` | Public API delegation, one decode, multi-output and terminal failures | Keep interface/failure checks. |
| `test_decode_quality` | Confidence proxy, missing/inline evidence, incomplete images, spatial damage | Keep; proxy is not measured decoder accuracy. |
| `test_reception_quality` | Signal/noise behavior and nonfinite input availability | Keep; signal measurement is distinct from accuracy. |
| `test_text_manifest` | Framing, Unicode, picture links and stored-manifest compatibility | Keep; move sidecar method to explicit data tier. |
| `test_mfsk_accuracy`, `test_mfsk_accuracy_cli` | CER/event/raster metrics, alignment, summaries and gate-report logic | Keep; add rejecting-gate cases and end-to-end enforcement. |
| `test_mfsk_corpus`, `test_setup_corpus` | Inventory, promotion, packaging, checksum/encryption/path/failure handling | Keep; synthetic transfer tests are real safety checks. |
| Decode session1 | Coordinates, wire primitives, SigMF CLI/schema, invalid/nonfinite/clipped input | Keep; consolidate repeated vector setup. |
| Decode session3 | FEC/Varicode plus missing controlled MFSK32 case | Keep primitives; repair independent fixture case. |
| Decode session4 | Real MFSK32 acquisition, text agreement and RF tracking | Keep corpus tier; narrow interval, not whole-corpus quality. |
| Decode session5 | Missing controlled MFSK64 case and real MFSK64 text interval | Repair controlled case; keep received case. |
| Decode session6 | Header grammar, clocks/tracks plus missing grayscale/colour cases | Keep synthetic coverage; repair independent cases. |
| Decode session7 | Hashed raster/component artifacts and real picture/resumed text | Keep; artifact safety is not supplanted by parallel ranges. |
| Decode session10B | Supported estimators/windows/filtering, fractional batching, damaged-header coordination | Keep; rewrite experiment-ranking assertion. |
| Decode session10C | Persistent competitor detection without changing evidence, policy rejection | Keep diagnostic contract. |
| Decode session10F | Flush/protocol evidence, current unified clock and boundary recovery | Keep; historical names are misleading, not proof of obsolescence. |
| Decode session11C | Stateful receiver, vectorized semantics, chunk equivalence, rollback, memory | Keep; consolidate older parser checkpoint overlap. |
| Decode session11E | Parallel picture ranges and compact/bounded text orchestration | Keep. |
| Decode session12A | Approved API and CLI defaults | Keep both entry points, organize together. |
| Remediation R1 | Synthetic RSID acquisition/automatic pipeline, weak real mode-event cases | Keep; real method detects events, not text/pixel fidelity. |
| Remediation R2 | No-RSID acquisition competition, tracks, interference/erasure, real text | Keep. |
| Remediation R3 | Stateful primitives, grammar, dropout and received cut without RSID | Keep; consolidate parser overlap carefully. |
| Remediation R4 | Fractional picture clock, boundary alternatives, offset/drift/step/bias | Keep; consolidate setup with other picture tests. |
| Remediation R5 | Missing-fixture bounded text integration | Repair/replace input and verify branch actually exercised. |
| Encoder session2 | Stateful byte-to-tone mapping/chunking/checkpoints/validation | Keep; distinguish production from oracle validation. |
| Encoder session3 | Framing, synthesis, canonical WAV, bounded writes/failure cleanup, text round trip | Keep; consolidate vector/integration setup. |
| Encoder session4 | Image normalization, RGB order, frequencies, geometry and resource preflight | Keep. |
| Encoder session5 | Picture announcements/transitions, phase continuity and resumed text | Keep; consolidate integration matrix without losing low-level paths. |
| Encoder session6 | Public parts API, mixed composition, WAV parsing, aliases and failure cleanup | Keep; different entry point from session3 cleanup. |
| Encoder session6R1 | Independent RSID PCM oracle, supported rates, memory and mutations | Keep. |
| Encoder session6R2 | RSID composition accounting, repeated/empty segments, RIFF limit and automatic acquisition | Keep. |
| Encoder session7 | Streaming large inputs, output coordinates, packaging/exports/docs | Keep runtime checks; remove fragile prose coupling. |
| `test_mfsk_encoder_evidence` | Independent oracle validation/packaged identity plus historical v1 contracts and JSON measurements | Keep oracle; retire/rehome v1 and constant-only checks as detailed above. |
| `test_mfsk_rsid_oracle` | Independent RSID field arithmetic/timing plus historical v2 draft contract | Keep first two; replace/rehome draft contract. |
| `test_mfsk_wire_vectors` | Independent protocol data consistency and fixture metadata | Keep equations; consolidate repeated provenance validation. |
| `test_mfsk_fixture_inventory` | Matrix metadata, inventory/CLI strictness/path rejection plus missing real integrity check | Keep negative/tool cases; centralize strict sidecar preflight. |
| `test_mfsk_fixture_source` | Deterministic PNG/PPM plus independent PNG decoding | Keep; generation equality and semantic correctness are distinct. |
| `test_mfsk_image_review` | Arbitrary candidate sets, scorecard identities/metrics/gate fields, incomplete arguments | Keep tool interface; not a quality regression run. |

## Missing quality regression: proposed maintained contract

The minimum durable acceptance bundle is:

1. Selected immutable input recordings with hashes and reviewed case roles.
2. Required text/image truth and/or saved qualified fldigi reference results
   for the chosen metrics, with explicit provenance and missing-data policy.
3. Scorer version/options (including raw versus aligned image measures),
   grouping/weights and approved per-case/aggregate regression tolerances.
4. Accepted GramPy baseline measurements and configuration/source identity.
5. A runner that freshly decodes with the candidate, verifies case completeness,
   scores it and exits unsuccessfully for missing data, uncomputable results,
   threshold violations or prohibited per-case regressions.

A new fldigi run on the Pi is not necessary for every GramPy-only change if the
inputs and qualified saved reference outputs remain valid. Qualification is
needed when that reference or its input/receive configuration changes. Not
every metric needs fldigi: reviewed transmitted/source truth is preferable
where available. Human visual acceptance remains necessary for risks not
captured by the scores; it cannot be replaced by a unit assertion.

Do not turn the August 9 reported MAE values (31.8286 raw, 29.0702 aligned)
into universal thresholds. They identify an accepted evaluation, not a complete
case list, scorer contract or approved tolerance. The October practical matrix
has its own explicit limits, but those do not automatically govern all received
broadcasts. Recover the paired evaluation contract or approve a new one before
claiming equivalence to the historical acceptance.

## Suggested implementation order

Phase 3 implements the maintained full-broadcast gate and proposes explicit
current-production regression limits. See the
[phase 3 record](test-rationalization-phase3.md) for validation and provenance.
The historical findings above remain an audit of the original state.

1. Decide the current decoder quality regression cases and approved policy;
   make one documented, strict sidecar acceptance entry point using existing
   scoring tools. Keep unit CI fast and label corpus validation separately.
2. Bring the six practical gate sensitivity tests into maintained discovery
   if their gate remains supported. Add failing/uncomputable gate verdict
   enforcement and demonstrate rejection of meaningful quality defects.
3. Replace historical v1/v2 document checks with active qualification contract
   checks, or run them explicitly with supported historical workflows. Retire
   constant-only waveform-measurement assertions from behavior coverage.
4. Validate/adopt replacement independent fixtures where their unique coverage
   is required; centralize data availability and integrity checking.
5. Consolidate the specifically mapped overlaps, then organize tests by behavior
   rather than session. Renaming is lower priority than coverage and pruning.
6. For each removal, document the surviving assertion/entry point and unique
   input/negative case. Where equivalence is uncertain, keep the test until a
   targeted defect check establishes that the survivor would catch its fault.

This audit does not recommend deleting an entire session file merely because
it is old. It identifies specific stale product obligations and overlap, while
preserving independent and boundary coverage that newer happy-path tests lack.
