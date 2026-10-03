# Encoder packaging and closeout

**Request, 2026-10-03:** PM confirms 48-kHz WAV output is sufficient, accepts
the practical images, and directs final packaging/cleanup with a Pi encoder
CPU-time-to-broadcast-duration estimate.

## Scope and baseline

Close Session 9 and fold Session 10 into this accepted scope. The required
broadcast output rate is 48 kHz. The existing API's broader rate validation and
the exploratory 8-kHz round trip are not additional qualification requirements
or blockers. All accepted practical waveforms remain byte-identical. The
additional encoder correction is D-030's grayscale-to-color row ordering,
described below; decoder algorithms, API shape and defaults are unchanged.

The [acceptance record](data/session9/practical-acceptance.json) binds D-027 and
D-028 to the tested source and preserved results. Use the current local
`radiogrampy` 0.1.3 version for a final wheel; publication/deployment and Git
commits are not part of this request.

## Final evidence to retain

- Build and inspect the final wheel, including accepted automatic MFSK32
  dispatch, encoder modules, packaged wire/schema data, public exports and
  declared dependencies.
- Install it into an isolated target directory and run the repository suite
  against the installed wheel with the repository virtualenv.
- Use that same wheel on the Pi in an isolated target directory. Benchmark
  representative 48-kHz text, pictures, mixed audio/text/picture and long copied
  audio. Record encoder CPU and wall time separately, their ratios to emitted
  broadcast duration, peak RSS, WAV bytes, and source/package identity.
- Keep numerical/visual acceptance bound to the frozen qualification records;
  retain investigation evidence and machine-local state deliberately.
- Promote supported behavior, validation, platform measurements and the
  accepted production baseline into operational documentation.

Prior Pi encoding exists: Session 8 recorded 0.831–4.040 seconds of encoder
wall time for 8.210–30.702 seconds of output, with per-case wall-time ratios
0.0992–0.1316. These are single small-fixture runs, not CPU measurements or
representative large-picture benchmarks. Pi decoder/receiver durations are
separate and must not be presented as encoder performance.

**Status: closed, 2026-10-03.** The final wheel passes installed-package
regression (248 tests, six expected skips) and 14 encoder-only Pi samples.
All ten accepted practical WAVs are byte-identical. The audited L-to-color
ordering defect is corrected under D-030 and independently verified.
No further PM image review is pending for the preserved qualification cases.

## Requirement disposition

**Packaging audit correction, D-030:** an `L` PNG transmitted with
`color="color"` incorrectly repeated each pixel three times on the wire.
The protocol requires repeating each whole row as its R, G and B planes.
This can introduce false colors and wrong horizontal detail even though
dimensions and duration are correct. Its Session 4 assertion contained the
same wrong expectation. The practical qualified sources are RGB, so their
accepted WAVs are unaffected. Correct this existing AC-005 implementation
defect, assert independent row-plane vectors and public WAV equality for
equivalent L/RGB sources, then rebuild and validate the final package.
No new feature or contract change is involved.

This maps the existing AC cases to the accepted product scope and retained
evidence. It is a closeout assessment, not a claim of new tests beyond the
records cited. All receive-quality acceptance uses D-027/D-028, with 48 kHz
confirmed by D-029. See [validation](validation.md) for the regression files
and [the original AC definitions](mfsk_wav_encoder_change.md#acceptance-cases).

| Requirement | Accepted disposition and evidence |
| --- | --- |
| AC-001 API surface | Exact exports, frozen records, defaults and keyword-only signature; Session 6 regression and final wheel inspection. |
| AC-002 text octets/codecs | Independent all-octet Varicode/FEC/interleaver/tone vectors and strict codec errors; Session 2/6 regressions. |
| AC-003 text files | Binary bytes/newlines preserved, empty and chunk-boundary cases; Session 5/6/7 regressions. |
| AC-004 independently framed modes | Exact framing plus per-segment RSID; Session 6R regressions and five passing Session 8 whole-WAV acquisition cases. |
| AC-005 PNG/color/gray mapping | Exact component/arithmetic/order/frequency vectors; Session 4/5 regressions and practical large-picture reception. |
| AC-006 p8/p4/p2 | Exact suffix/timing vectors and retained speeds in practical matrix. Decoded equality replaced by scoped numerical/visual quality under D-027. |
| AC-007 image transitions/resumed text | Exact announcements, flush/prologue order and timestamps; Session 5 regression and practical ordered-text checks. |
| AC-008 AudioParts | Ancillary chunk exclusion and unchanged copied PCM; Session 6/7, independent practical checks, final Pi mixed/copy samples. |
| AC-009 silence | Exact zero frames and invalid-duration rejection; Session 6/7 and practical/Pi sample checks. |
| AC-010 mixed composition | Ordered text-file/audio/silence/picture coordinates; Session 6/7 and whole-WAV mixed broadcast. |
| AC-011 exact output/replacement | Exact caller path and preflight-before-replacement; Session 3/6 regressions. |
| AC-012 preflight errors/overflow | Invalid input/configuration, alias and arithmetic RIFF-ceiling cases preserve old output; Session 3–7 regressions. |
| AC-013 reported-failure cleanup | Read/sink/accounting failures and removal-failure chaining; Session 3/6/6R regressions. Forced termination excluded by contract. |
| AC-014 input aliases | Same object, relative/absolute spelling, links and input preservation; Session 6 regression. |
| AC-015 PNG bounds/resources | Profile/geometry/disk limits validated; 1024x1024 bounded-allocation exercise in Session 7. Pi performance measures representative images, not the maximum 4095x4095 input. |
| AC-016 WAV profile | PCM16 mono rate-match/nonempty/complete-data and incompatible-format rejection; Session 6 regression and final exact-copy samples. |
| AC-017 rate/carrier bounds | Exact validator boundaries remain compatible behavior. D-029 makes 48 kHz the required receive-qualified rate; no other-rate quality promise. |
| AC-018 streaming/resources | 64-KiB bounded reads/copies/silence, one-raster working allocation, exact totals; Session 7 plus final Pi duration/RSS/bytes measurements. |
| AC-019 installed package/platforms | Final wheel inspected and isolated installs on Mac/Pi; installed-wheel regression and public API workloads. Python minimum declared 3.11; final runtimes are 3.14 Mac and 3.13 Pi, not a new 3.11 test. |
| AC-020 pinned fldigi qualification | Ten practical whole-WAV cases pass frozen screen; all images accepted by PM. Historical tiny failures retained outside the practical scope. |
| AC-021 decoder regressions | Full suite, received-broadcast preservation and Pi subset pass. D-028 evaluated and accepted separately; defaults/algorithms unchanged. |
| AC-022 RSID | Frozen pinned-source codeword/tone/guard vectors, mutation rejection and exact PCM checks; Session 6R and whole-WAV reception. |
| AC-023 automatic mixed reception | Adjacent/reversed/repeated modes and later MFSK after audio/silence in whole-WAV Pi reception; no manual window/mode changes. |

## Deliberate preservation

The frozen v2 failures, v3 numerical results, PM acceptance overlay and
supplemental decoder evidence remain unchanged. `experiments/` scripts are
marked historical and retained for reproduction. The original WAVs, transferred
Pi staging, investigation logs, local command files and external corpus remain
valuable evidence in their existing locations. Only completed managed run
directories and explicitly owned, newly generated benchmark/check WAVs are
removed after their evidence is consumed. No blanket `.local/` cleanup, corpus
change or unrelated file deletion is performed.

## Final result

The [final evidence index](data/session10/README.md) records the local 0.1.3
wheel, SHA-256 `e549e3d7cc635f678e04a43b2cd79407f2c7622d56293e98fc50eca67b543ab7`, installed-wheel regression,
unchanged accepted WAVs and final Pi measurements. CPU-to-broadcast ratios
are 0.133–0.172 for the text/picture/mixed workloads; maximum
whole-worker peak RSS is 101.02 MiB. Exact AudioPart copying remains
verified. Publication, deployment and commits were not performed.

The grayscale-to-color correction changes only `picture_encode.py` from the
Session 9 encoder. Its original source hash
`def188575ba7064e8436516eca5971c79304ca0f46e207d27a04342b6c684845`
becomes `3e5c1a761d54052db3045a5fcf31b46fb275ca7af6f57c7f2571a2aa6b0947c6`.
The new independent row-plane assertion fails against the prior wheel;
the final suite passes. Equivalent L/RGB WAVs are identical for both modes
and p8/p4/p2, with additional 240x180 p8 checks. All ten accepted Mac WAVs and
all 14 repeated Pi benchmark WAVs remain identical to their previous versions.
There was no fresh receiver replay of the equivalent L-source cases; their
corroboration is exact wire/WAV equality to the equivalent working RGB path.

The accepted behavior can now be maintained from the API, contracts, design,
validation and production-baseline guides. Session 9 is closed; Session 10
is folded and complete within D-029's 48-kHz practical scope.

## Subsequent artifact cleanup (2026-10-03)

The [cleanup and restoration record](data/session10/cleanup.md) supersedes earlier statements
that all loose working files and transferred Pi staging remain in their
original locations. Unique evidence is preserved; obsolete snapshots/logs
are archived, derivable IQ caches are removed after exact regeneration, and
inactive Pi staging is retired. Accepted measurements and source are unchanged.
