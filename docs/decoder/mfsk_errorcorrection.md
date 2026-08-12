# Signal Processing Specification: Multi-Recording MFSK Combiner

**Version 1.0**  
**Status: Draft for Implementation**

---

## Overview

Three IQ recordings of the same MFSK transmission recorded at different times are combined to produce a single enhanced symbol stream with associated confidence scores. Success is measured against single-recording baseline decodes. At least one recording in the test corpus must be verified as individually undecodable or partially decodable to ensure the combiner is doing real work.

Two distinct impairment classes are targeted by different stages of the pipeline:

- **Atmospheric noise** — broadband, Gaussian-like, continuous. Addressed via SNR improvement through magnitude spectrum averaging and Maximal Ratio Combining (MRC).
- **Electrical interference** — periodic or impulsive, structured, decorrelates naturally across recordings taken at different times due to beating between interference period and symbol period. Addressed via burst detection and hard exclusion.

---

## Background: Why Three Independent Recordings Help

### Atmospheric Noise

Static hiss is random and zero-mean. Averaging N recordings reduces noise variance by 1/√N. For N=3 this gives a theoretical SNR improvement approaching +4.77 dB. The noise floor mean does not drop but its fluctuations shrink, making signal peaks stand out more reliably.

### Electrical Interference

50 Hz powerline interference has a 20 ms period. MFSK-16 has a ~16 ms symbol period. These are incommensurate — they never lock together. A recording started 4 seconds later than another will have the interference pattern at a completely different phase relative to the symbol grid. The probability that the same symbol position is independently corrupted in all three recordings is p³ where p is the per-symbol corruption rate. At p=0.05 this is 0.0125% — near-zero residual error from interference.

### Why Simple Majority Vote Is Insufficient

Majority vote assumes the correct answer is the most common one. This breaks down when:

- Two recordings share a strong interference source that mimics valid signal amplitude
- The interference lands on the correct tone frequency but with wrong phase
- Confidence information is discarded, preventing downstream error correction from making informed decisions

The pipeline uses confidence-weighted combination rather than simple voting, preserving soft information through to the final decode.

---

## Test Corpus Requirements

This is a prerequisite. The pipeline cannot be validated without a properly structured corpus.

### Corpus Structure

```
transmission_001/
    recording_a.wav       # captured at time T
    recording_b.wav       # captured at time T + offset_1
    recording_c.wav       # captured at time T + offset_2
    reference.txt         # known content from swradiogram (if available)
    baseline_a.txt        # fldigi decode of recording_a alone
    baseline_b.txt        # fldigi decode of recording_b alone
    baseline_c.txt        # fldigi decode of recording_c alone
```

### Recording Classification

Run each recording through fldigi independently before any combining work and classify:

| Class | Definition |
|---|---|
| Clean | >90% characters decoded correctly |
| Marginal | 40–90% decoded, errors present |
| Failed | <40% decoded, sync issues |

**The test corpus must contain at least one Marginal and one Failed recording per transmission group.** A corpus of three Clean recordings proves nothing — the combiner needs to demonstrate recovery from genuinely difficult material.

---

## Phase 1: Ingestion and Baseline SNR Measurement

### Processing

Load each recording as complex float32 IQ. Compute per-recording SNR using the signal/guard-band method:

$$\text{SNR}_{\text{input}} = 10 \log_{10}\left(\frac{P_{\text{signal}}}{P_{\text{noise}}}\right)$$

Signal power is measured within the MFSK tone band. Noise power is measured in adjacent guard bands of equal bandwidth. Store as the baseline for each recording. Detect center frequency and symbol rate from the strongest recording via FFT peak detection. Classify each recording into Clean/Marginal/Failed.

### Success Criteria

- Per-recording SNR computed and logged for all three recordings
- Center frequency detected within ±100 Hz
- Symbol rate estimated within ±2% of nominal
- Recording classification matches fldigi baseline quality (a Failed recording should have the lowest SNR — if it does not, the SNR measurement is incorrect)

---

## Phase 2: Frequency Drift Correction

### Processing

For each recording estimate instantaneous frequency offset using a sliding window phase estimator on the dominant tone bin. Window size should be 10× symbol period to average over tone transitions. Fit a linear polynomial to offset vs time — HF drift over a few minutes is well modeled as linear. Apply correction:

```python
corrected[n] = raw[n] * np.exp(-1j * 2 * np.pi * offset(n) * n / fs)
```

After correction verify all recordings show MFSK tones at consistent absolute frequencies by comparing peak bin positions across recordings.

### Success Criteria

- Residual frequency offset after correction < 10% of tone spacing
- Tone frequency variance across three recordings reduced by >80% vs uncorrected
- Correction parameters (offset, drift rate) logged per recording as diagnostics

---

## Phase 3: Timing Alignment and Symbol Boundary Establishment

### Processing

Take the highest SNR recording as master. Cross-correlate the magnitude envelope of each other recording against the master using `scipy.signal.correlate`. Use Peak-to-Average Power Ratio (PAPR) on the correlation peak to verify alignment quality. Apply sub-sample alignment via parabolic interpolation around the correlation peak.

Establish the symbol boundary grid on the master recording using the Gardner algorithm for symbol timing recovery. Gardner operates on the magnitude envelope and finds the regular spacing of symbol transitions without needing to know tone content. Store boundary positions as the reference grid used by all subsequent phases.

### Success Criteria

- Cross-correlation PAPR > 15 dB for all recording pairs — lower indicates a recording too degraded to align reliably; flag for reduced weighting rather than exclusion
- Timing offset between recordings after alignment < 0.1 symbol periods
- Symbol boundary grid covers full transmission duration without gaps
- Any recording failing the PAPR criterion is flagged with its weight reduced in Phase 5

---

## Phase 4: Per-Symbol Per-Recording Assessment

This is the core phase. Each recording is assessed independently at the symbol level before any combination occurs. This preserves per-recording information — the key advantage over combining in the analog domain first.

### Step 4a — Sample Quality Weighting Within Symbol Period

Before computing the FFT, weight samples within the symbol period to account for transition transients at boundaries. Apply a Hann window as baseline, then additionally zero the first and last 10% of the symbol period where transition contamination is highest. This exploits the clean steady-state center of each symbol period.

Note: intra-symbol stitching across recordings is not possible for MFSK. The FFT integrates across the entire symbol period simultaneously — a hard splice between samples from two different recordings creates a discontinuity whose spectral splatter corrupts the tone detection. The minimum coherent unit for MFSK is the full symbol period.

### Step 4b — Interference Detection

Compute an anomaly score: the ratio of peak energy in non-signal bins to median non-signal bin energy. A clean symbol period shows flat non-signal bins. An interference burst shows anomalous non-signal energy. Threshold at 3× median — flag as interference-corrupted if exceeded.

This detection operates after the FFT, where structured interference that mimics valid signal amplitude in the time domain is visible as wrong-bin energy in the frequency domain — a more reliable detection surface than time-domain amplitude alone.

### Step 4c — Tone Confidence Scoring

Compute FFT magnitude spectrum. Extract magnitudes at the M tone bin positions. Record:

```python
winner           = argmax(tone_magnitudes)
margin           = tone_magnitudes[winner] - second_highest(tone_magnitudes)
snr_local        = tone_magnitudes[winner] / mean(non_tone_bins)
interference_flag = anomaly_score > threshold
```

Output per symbol per recording: `(winner_tone, margin, snr_local, interference_flag)`

### Success Criteria

- Interference flag false positive rate on clean recordings < 5%
- Interference flag detection rate on known-bad segments > 50%
- Margin distribution shows clear separation between clean and corrupted symbols
- All four output values computed for every symbol period in every recording

---

## Phase 5: Weighted Combination

For each symbol period, combine the three independent assessments from Phase 4 using the appropriate strategy based on interference flags.

### Case 1: No Recordings Flagged

Apply Maximal Ratio Combining (MRC) — weight each recording's tone magnitude vector inversely by its local noise variance, then sum. This is the theoretically optimal combiner for Gaussian noise and delivers the full SNR improvement:

```python
weight_i = 1 / noise_variance[recording_i, symbol_n]
combined_magnitudes = sum(weight_i * tone_magnitudes[i] for i in recordings)
decided_tone = argmax(combined_magnitudes)
```

### Case 2: One or Two Recordings Flagged

Exclude flagged recordings entirely for this symbol period. Apply MRC to the remaining clean recordings only. Confidence is reduced but the decision is protected from interference contamination. This is the hard exclusion step that MRC weighting alone cannot achieve — a strong interference burst down-weighted by MRC still contaminates the combine; exclusion removes it entirely.

### Case 3: All Recordings Flagged

Mark symbol as **erasure**. Do not guess. Pass the erasure marker forward to the decoder — a known erasure is more useful to error correction than a confident wrong answer.

### Aggregate Confidence Score

For all cases:

```python
confidence = (combined_margin / n_contributing_recordings) 
           * (n_contributing / n_total)  # penalty for exclusions
```

### Success Criteria

- SNR improvement on clean symbol periods falls within the theoretical corridor of +3.5 dB to +4.77 dB for N=3. Below +3.5 dB indicates phase misalignment; above +4.77 dB indicates an algorithmic artifact. Either triggers a processing failure log.
- Symbols decoded from Marginal recordings increases vs single-recording baseline
- Erasure rate (all three flagged) < 2% on corpus — higher suggests threshold miscalibration
- **Hard floor:** combined character error rate is never worse than the best single recording for any transmission group

---

## Phase 6: Symbol Stream Output and Scoring

### Processing

Decode the combined symbol stream through MFSK gray decode and Varicode character assembly. Produce three parallel outputs for comparison:

1. Best single recording decode (baseline)
2. Combined decode — hard decisions only
3. Combined decode — with confidence scores attached per character

Score against reference content where available (swradiogram known content) or against the best single recording decode where reference is unavailable.

### Metrics

| Metric | Definition |
|---|---|
| CER | Character error rate vs reference |
| Sync rate | Fraction of transmission where symbol clock was maintained |
| Erasure rate | Fraction of symbols marked unrecoverable |
| Confidence calibration | Error rate in bottom confidence quartile vs top quartile |
| Recovery rate | Symbols decoded correctly from Marginal/Failed recordings that all individual baselines missed |

The **recovery rate** is the primary metric — it directly measures what the combiner contributes beyond what single-recording decoding provides.

### Success Criteria

- Mean CER improvement > 20% vs best single recording across corpus
- Confidence calibration: bottom quartile error rate > 3× top quartile error rate (proves confidence scores carry real information)
- Recovery rate > 30% on symbols that all individual baselines failed
- Hard floor: combined CER never worse than best single recording CER for any transmission group

---

## Corpus-Level Reporting

At the end of a run against the full corpus, the following are reported:

**Per transmission group:**
- Baseline decode quality per recording (Clean/Marginal/Failed)
- Combined decode with character-level confidence
- SNR gain measurement validating Phase 5 is working physically
- Interference flag statistics validating Phase 4 is detecting real interference
- Recovery rate — the number that matters for deployment

**Across corpus:**
- Performance by recording class: does the combiner help more on Failed recordings?
- Performance by environment: urban vs rural friend recordings
- Confidence calibration curve: are the scores trustworthy?

---

## Implementation Notes

- Use `numpy` for all IQ math, `scipy.signal` for correlation and filtering, `scipy.fft` for spectral work
- IQ files assumed as interleaved int16 (standard RTL-SDR output), converted to complex64 on load
- All thresholds defined as parameters in a single config object — no magic numbers in code
- Each phase writes intermediate results to disk so the pipeline can be restarted at any phase without reprocessing
- A synthetic test signal generator should be built first and used to validate each phase before running on real recordings — generate known MFSK content, add controlled Gaussian noise and interference bursts, verify each phase behaves as specified
- Primary target modes: MFSK-16 and MFSK-32 as used by swradiogram

---

## Dependencies

```
numpy
scipy
pyrtlsdr       # IQ sample ingestion
matplotlib     # diagnostic visualization
```

---

*Derived from design discussion integrating Flash's MRC/SNR validation framework with symbol-level interference excision and corpus evaluation methodology.*
