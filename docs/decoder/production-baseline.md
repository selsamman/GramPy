# Accepted decoder baseline

## Identity

The accepted picture-decoding baseline was approved on 2026-08-09 in commit
`68b03b48bb3d511c1ae56e7eb64e3d80a21ab467`.

| Dimension | Accepted value |
|---|---|
| Pipeline organization | `supported_hybrid` |
| Picture filter | `response_matched` |
| Picture estimator | `bounded_correlation` |
| Component window | `full_hann` |
| Picture boundary estimator | `unified_grid` |
| Persistent-tone policy | `measure` |
| Reference decoder | pinned fldigi 4.2.13 Pi build |

## Acceptance evidence

The approved candidate used the received corpus, reviewed image truth, and
the pinned fldigi reference. Relative to the preceding accepted rectangular
bounded-correlation configuration, it reduced hierarchical raw image MAE from
34.3240 to 31.8286 and aligned image MAE from 31.7798 to 29.0702. Picture
recall and text CER were unchanged. The closely matched full-window FFT
candidate was not selected because its quality margin was negligible and its
measured cost was higher.

The detailed decision, diagnostics, scorecards, and visual candidate-set
review were distilled into the versioned contracts and validation guidance in
this repository. They are evidence for this baseline, not normal bootstrap
documentation.

## Use in future changes

Treat this document as the meaning of “accepted production baseline” for
decoder-quality work until a later accepted change replaces it. A candidate
must name its precise delta from this configuration, source revision, corpus
and truth revision, reference decoder, and measured platform. Follow the
repository-wide [change-management process](../operations/change-management-v1.md)
for evaluation and closure.

## Compact-output acceptance (2026-09-24)

The output-only stage 5 change keeps the accepted decoder configuration and
MFSK decode path. `decode_iq_products` and the two compact CLI paths publish
ordered text/pictures and aligned one-second quality data. The large
diagnostic document is opt-in; `decode_iq` and the existing diagnostic-only
CLI invocation remain supported.

On the 1,800-second WRMI capture, the product path preserved the three
MFSK mode intervals and all nine picture artifacts byte-for-byte. It produced
35 ordered text items and 1,800 quality rows. Signal, noise, and confidence
were available in 1,691, 1,800, and 1,621 seconds respectively. Both product
schemas validated and shared the diagnostic baseline's run ID and input hashes.

Paired runs on the same Mac, same input and default configuration:

| Measure | Legacy diagnostic only | Compact products only |
| --- | ---: | ---: |
| Command wall time | 133.19 s | 134.05 s |
| Command user + system CPU | 127.77 s | 124.40 s |
| Maximum resident set size | 398.2 MB | 556.2 MB |
| macOS peak memory footprint | 274.6 MB | 253.7 MB |
| JSON output | 16,073,902 bytes | 131,215 bytes |
| PNG and component artifacts | 6,976,817 bytes | 6,976,817 bytes |
| Total published bytes | 23,050,719 bytes | 7,108,032 bytes |

The compact path took 0.86 s more wall time (0.6%) and 3.37 s less CPU
(2.6%). Its JSON was 99.2% smaller and total published output was 69.2%
smaller. The four-snapshot reception pass reports 235,929,600 logical IQ
bytes read, about 29% on top of the legacy manifest's 816,020,488-byte
diagnostic estimate for the shared decode. The increase in maximum RSS is
explained by mapped IQ pages being resident during the sparse pass: an
isolated four-window-per-second read of the capture raised current RSS from
26.5 MB to 257.0 MB while the mapping itself initially changed RSS by less
than 0.1 MB. That experiment's macOS peak memory footprint was only
19.4 MB. In the paired decode runs, macOS's peak memory-footprint accounting
decreased. These memory
measures are platform-specific and should be checked for the appliance before
deployment. The historical 2,771-second Linux ARM64 run is not a paired
performance comparator.
