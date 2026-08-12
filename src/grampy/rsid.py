from __future__ import annotations

import math
from pathlib import Path
import struct
from typing import Any

import numpy as np
from scipy import signal

class RsidError(ValueError):
    pass

class RsidDetection:
    def __init__(
        self,
        *,
        sample_start: int,
        sample_count: int,
        mode: str,
        center_hz: float,
        confidence_db: float,
        uncertainty_hz: float,
        tones: list[int],
        orientation: str = "unknown",
        rsid_code: int | None = None,
        rsid_code_distance: int | None = None,
    ) -> None:
        self.sample_start = sample_start
        self.sample_count = sample_count
        self.mode = mode
        self.center_hz = center_hz
        self.confidence_db = confidence_db
        self.uncertainty_hz = uncertainty_hz
        self.tones = tones
        self.orientation = orientation
        self.rsid_code = rsid_code
        self.rsid_code_distance = rsid_code_distance

    def as_annotation(self, *, output_start_sample: int) -> dict[str, Any]:
        annotation = {
            "core:sample_start": self.sample_start - output_start_sample,
            "core:sample_count": self.sample_count,
            "radiogram:operation": "rsid-detection",
            "radiogram:original_sample_start": self.sample_start,
            "radiogram:rsid_mode": self.mode,
            "radiogram:center_hz": round(self.center_hz, 3),
            "radiogram:confidence_db": round(self.confidence_db, 3),
            "radiogram:uncertainty_hz": round(self.uncertainty_hz, 3),
            "radiogram:rsid_tones": self.tones,
            "radiogram:orientation": self.orientation,
        }
        if self.rsid_code is not None:
            annotation["radiogram:rsid_code"] = self.rsid_code
        if self.rsid_code_distance is not None:
            annotation["radiogram:rsid_code_distance"] = self.rsid_code_distance
        return annotation


RSID_SYMBOLS = 15
RSID_BAUD = 11025.0 / 1024.0
RSID_TONES = 16
RSID_DETECTOR_HOP_SEC = 0.25
RSID_MODE_CODES = {
    69: "OLIVIA-8-250",
    70: "OLIVIA-16-500",
    71: "OLIVIA-32-1000",
    72: "OLIVIA-8-500",
    73: "OLIVIA-16-1000",
    74: "OLIVIA-4-500",
    75: "OLIVIA-4-250",
    116: "OLIVIA-8-1000",
    147: "MFSK32",
    620: "MFSK64",
}
RSID_ESCAPE_CODE = 6
RSID_PRIMARY_CODES = tuple(code for code in RSID_MODE_CODES if code != 620)
RSID_SECONDARY_CODES = (620,)
RSID_VALID_CODES = (RSID_ESCAPE_CODE,) + RSID_PRIMARY_CODES + RSID_SECONDARY_CODES
_RSID_CODEBOOK: np.ndarray | None = None


def detect_rsid(
    *,
    data_path: Path,
    datatype: str,
    sample_rate: int,
    start_sample: int,
    stop_sample: int,
    nominal_center_hz: float,
    threshold_db: float,
    search_low_hz: float,
    search_high_hz: float,
    mode_hint: str | None,
) -> list[RsidDetection]:
    if datatype not in {"ci16_le", "cf32_le"}:
        raise RsidError(f"RSID detection does not support datatype: {datatype}")

    if mode_hint is None:
        return detect_rsid_fft_buckets(
            data_path=data_path,
            datatype=datatype,
            sample_rate=sample_rate,
            start_sample=start_sample,
            stop_sample=stop_sample,
            nominal_center_hz=nominal_center_hz,
            threshold_db=threshold_db,
            search_low_hz=search_low_hz,
            search_high_hz=search_high_hz,
        )

    symbol_samples = max(1, int(round(sample_rate / RSID_BAUD)))
    window_samples = symbol_samples * RSID_SYMBOLS
    if stop_sample - start_sample < window_samples:
        return []

    hop_samples = rsid_detector_hop_samples(sample_rate)
    iq_source = open_iq_source(data_path=data_path, datatype=datatype)
    frequencies = np.asarray(
        [
            nominal_center_hz + (tone - 7.0) * RSID_BAUD
            for tone in range(RSID_TONES)
        ],
        dtype=np.float64,
    )
    symbol_indexes = np.arange(symbol_samples, dtype=np.float64)
    oscillators = np.exp(
        -2.0j * np.pi * frequencies[:, np.newaxis] * symbol_indexes / sample_rate
    )
    candidates: list[RsidDetection] = []
    sample = start_sample
    while sample + window_samples <= stop_sample:
        iq = read_iq_samples(
            source=iq_source,
            datatype=datatype,
            sample_start=sample,
            sample_count=window_samples,
        )
        detection = score_rsid_window(
            iq=iq,
            sample_start=sample,
            sample_rate=sample_rate,
            symbol_samples=symbol_samples,
            frequencies=frequencies,
            oscillators=oscillators,
            nominal_center_hz=nominal_center_hz,
            mode_hint=mode_hint,
        )
        decoded_code, code_distance = decode_rsid_code(detection.tones)
        decoded_mode = RSID_MODE_CODES.get(decoded_code)
        if code_distance <= 2:
            detection.rsid_code = decoded_code
            detection.rsid_code_distance = code_distance
            if decoded_mode is not None:
                detection.mode = decoded_mode
        codeword_valid = code_distance <= 2
        # A hint retains the Phase-1 calibration behavior for old corpus tests;
        # unhinted production detection requires a decoded RSID codeword.
        mode_matches = mode_hint is None or detection.mode == mode_hint
        if detection.confidence_db >= threshold_db and mode_matches and (
            codeword_valid or mode_hint is not None
        ):
            candidates.append(detection)
        sample += hop_samples

    return suppress_nearby_rsid_candidates(candidates, sample_rate=sample_rate)


def suppress_validated_rsid_candidates(
    candidates: list[RsidDetection], *, sample_rate: int
) -> list[RsidDetection]:
    if not candidates:
        return []
    exclusion = int(round(sample_rate * 1.5))
    ordered = sorted(candidates, key=lambda item: item.sample_start)
    groups: list[list[RsidDetection]] = []
    for candidate in ordered:
        if not groups or candidate.sample_start - groups[-1][-1].sample_start > exclusion:
            groups.append([candidate])
        else:
            groups[-1].append(candidate)
    return [
        min(
            group,
            key=lambda item: (
                item.rsid_code_distance if item.rsid_code_distance is not None else 99,
                item.sample_start,
            ),
        )
        for group in groups
    ]


def detect_rsid_fft_buckets(
    *,
    data_path: Path,
    datatype: str,
    sample_rate: int,
    start_sample: int,
    stop_sample: int,
    nominal_center_hz: float,
    threshold_db: float,
    search_low_hz: float,
    search_high_hz: float,
) -> list[RsidDetection]:
    """Detect unhinted RSID in bounded blocks.

    Blocks include enough context on each side for the resampling filter and
    the primary/secondary RSID sequence.  Each block owns a disjoint input
    range, so detections in the overlap are evaluated but only emitted once.
    This keeps memory independent of capture duration and gives a future live
    source a bounded-lookahead processing boundary.
    """
    source = open_iq_source(data_path=data_path, datatype=datatype)
    gcd = math.gcd(sample_rate, int(RSID_BAUD * 1024))
    up = int(RSID_BAUD * 1024) // gcd
    down = sample_rate // gcd
    block_samples = max(down, (sample_rate * 30 // down) * down)
    context_samples = max(down, (sample_rate * 8 // down) * down)
    candidates: list[RsidDetection] = []
    owned_start = start_sample
    while owned_start < stop_sample:
        owned_stop = min(stop_sample, owned_start + block_samples)
        read_start = max(start_sample, owned_start - context_samples)
        read_stop = min(stop_sample, owned_stop + context_samples)
        # Align block origins to the rational resampler phase. This makes the
        # local output grid coincide with the grid for a whole-stream run.
        read_start -= (read_start - start_sample) % down
        iq = read_iq_samples(
            source=source,
            datatype=datatype,
            sample_start=read_start,
            sample_count=read_stop - read_start,
            dtype=np.complex64,
        )
        resampled = signal.resample_poly(iq, up, down)
        candidates.extend(detect_rsid_fft_block(
            data_path=data_path,
            datatype=datatype,
            sample_rate=sample_rate,
            stop_sample=stop_sample,
            nominal_center_hz=nominal_center_hz,
            threshold_db=threshold_db,
            search_low_hz=search_low_hz,
            search_high_hz=search_high_hz,
            source=source,
            resampled=resampled,
            input_start_sample=read_start,
            owned_start_sample=owned_start,
            owned_stop_sample=owned_stop,
        ))
        owned_start = owned_stop
    return suppress_validated_rsid_candidates(candidates, sample_rate=sample_rate)


def detect_rsid_fft_block(
    *,
    data_path: Path,
    datatype: str,
    sample_rate: int,
    stop_sample: int,
    nominal_center_hz: float,
    threshold_db: float,
    search_low_hz: float,
    search_high_hz: float,
    source: np.memmap,
    resampled: np.ndarray,
    input_start_sample: int,
    owned_start_sample: int,
    owned_stop_sample: int,
) -> list[RsidDetection]:
    """Run the validated FFT detector over one contextualized input block."""
    fft_size = 2048
    hop = 512
    history_length = RSID_SYMBOLS * 2
    if len(resampled) < fft_size + (history_length - 1) * hop:
        return []

    bin_hz = (RSID_BAUD * 1024) / fft_size
    # A base bin plus 14.5 FFT bins is the RSID center. Search the usable
    # audio band directly; nominal_center_hz is only a legacy hinted-detector
    # input and is deliberately not used to constrain validated detection.
    base_bins = np.arange(
        max(1, int(math.floor(search_low_hz / bin_hz - (RSID_SYMBOLS - 0.5)))),
        min(
            fft_size // 2 - 32,
            int(math.ceil(search_high_hz / bin_hz - (RSID_SYMBOLS - 0.5))) + 1,
        ),
        dtype=np.int64,
    )
    if not len(base_bins):
        return []
    tone_offsets = 2 * np.arange(RSID_TONES, dtype=np.int64)
    tone_bins = base_bins[:, np.newaxis] + tone_offsets[np.newaxis, :]
    window = np.hamming(fft_size)
    bucket_history = np.zeros((history_length, len(base_bins)), dtype=np.uint8)
    ratio_history = np.zeros((history_length, len(base_bins)), dtype=np.float64)
    primary_book = np.asarray([encode_rsid(code) for code in RSID_PRIMARY_CODES], dtype=np.uint8)
    escape_word = np.asarray(encode_rsid(RSID_ESCAPE_CODE), dtype=np.uint8)
    secondary_book = np.asarray([encode_rsid(code) for code in RSID_SECONDARY_CODES], dtype=np.uint8)
    awaiting_secondary_until = -1
    candidates: list[RsidDetection] = []

    for frame, offset in enumerate(range(0, len(resampled) - fft_size + 1, hop)):
        spectrum = np.fft.fft(resampled[offset:offset + fft_size] * window)
        powers = np.abs(spectrum[tone_bins]) ** 2
        winners = np.argmax(powers, axis=1)
        winner_power = powers[np.arange(len(base_bins)), winners]
        noise = np.median(powers, axis=1)
        ratios = winner_power / np.maximum(noise, 1.0e-18)
        bucket_history[:-1] = bucket_history[1:]
        bucket_history[-1] = winners
        ratio_history[:-1] = ratio_history[1:]
        ratio_history[-1] = ratios
        if frame < history_length - 1:
            continue

        observed_normal = bucket_history[1::2].T
        selected_ratios = ratio_history[1::2].T
        confidence_db_by_base = 10.0 * np.log10(
            np.maximum(np.mean(selected_ratios, axis=1), 1.0e-18)
        )
        eligible_bases = np.flatnonzero(confidence_db_by_base >= threshold_db)
        if not len(eligible_bases):
            continue
        observed_normal = observed_normal[eligible_bases]
        observed_orientations = np.stack(
            (observed_normal, (RSID_TONES - 1) - observed_normal),
            axis=1,
        )
        if frame <= awaiting_secondary_until:
            codebook = secondary_book
            codes = RSID_SECONDARY_CODES
        else:
            codebook = primary_book
            codes = RSID_PRIMARY_CODES
        distances = np.count_nonzero(
            observed_orientations[:, :, np.newaxis, :]
            != codebook[np.newaxis, np.newaxis, :, :],
            axis=3,
        )
        flat_index = int(np.argmin(distances))
        eligible_index, orientation_index, code_index = np.unravel_index(
            flat_index, distances.shape
        )
        base_index = int(eligible_bases[eligible_index])
        distance = int(distances[eligible_index, orientation_index, code_index])

        escape_distances = np.count_nonzero(
            observed_orientations != escape_word[np.newaxis, np.newaxis, :],
            axis=2,
        )
        escape_flat = int(np.argmin(escape_distances))
        escape_eligible, _escape_orientation = np.unravel_index(
            escape_flat, escape_distances.shape
        )
        escape_distance = int(escape_distances[escape_eligible, _escape_orientation])
        if frame > awaiting_secondary_until and escape_distance <= 2:
            awaiting_secondary_until = frame + 27 * 2
            continue
        if distance > 2:
            continue

        confidence_db = float(confidence_db_by_base[base_index])
        code = codes[code_index]
        center_hz = (float(base_bins[base_index]) + RSID_SYMBOLS - 0.5) * bin_hz
        # The 30-slice bucket history plus the two-symbol FFT window reports a
        # match seven symbol periods after the nominal last-symbol center.
        first_symbol_center = offset + fft_size / 2.0 - (RSID_SYMBOLS + 6) * 1024
        rsid_start_resampled = first_symbol_center - 512.0
        detected_start = input_start_sample + int(round(rsid_start_resampled * sample_rate / 11025.0))
        detected_start = max(input_start_sample, detected_start)
        timing_probe = RsidDetection(
            sample_start=detected_start,
            sample_count=int(round(RSID_SYMBOLS * 1024 * sample_rate / 11025.0)),
            mode=RSID_MODE_CODES[code],
            center_hz=center_hz,
            confidence_db=confidence_db,
            uncertainty_hz=bin_hz / 2.0,
            tones=observed_orientations[eligible_index, orientation_index].astype(int).tolist(),
            orientation=("normal" if orientation_index == 0 else "reverse"),
            rsid_code=code,
            rsid_code_distance=distance,
        )
        detected_start = refine_rsid_start(
            data_path=data_path,
            datatype=datatype,
            sample_rate=sample_rate,
            detection=timing_probe,
            nominal_center_hz=center_hz,
        )
        symbol_samples_input = max(1, int(round(sample_rate / RSID_BAUD)))
        if detected_start + RSID_SYMBOLS * symbol_samples_input <= stop_sample:
            rsid_iq = read_iq_samples(
                source=source,
                datatype=datatype,
                sample_start=detected_start,
                sample_count=RSID_SYMBOLS * symbol_samples_input,
            )
            measured_centers = []
            chosen_tones = observed_orientations[eligible_index, orientation_index]
            for symbol_index, tone in enumerate(chosen_tones):
                segment = rsid_iq[
                    symbol_index * symbol_samples_input:
                    (symbol_index + 1) * symbol_samples_input
                ]
                expected_frequency = center_hz + (float(tone) - 7.0) * RSID_BAUD
                measured_frequency = estimate_complex_tone_frequency(
                    segment,
                    sample_rate=sample_rate,
                    fallback_hz=expected_frequency,
                )
                measured_centers.append(
                    measured_frequency - (float(tone) - 7.0) * RSID_BAUD
                )
            if any(abs(value - center_hz) > 1.0e-6 for value in measured_centers):
                center_hz = float(np.median(measured_centers))
        detection = RsidDetection(
            sample_start=detected_start,
            sample_count=int(round(RSID_SYMBOLS * 1024 * sample_rate / 11025.0)),
            mode=RSID_MODE_CODES[code],
            center_hz=center_hz,
            confidence_db=confidence_db,
            uncertainty_hz=bin_hz / 2.0,
            tones=observed_orientations[eligible_index, orientation_index].astype(int).tolist(),
            orientation=("normal" if orientation_index == 0 else "reverse"),
            rsid_code=code,
            rsid_code_distance=distance,
        )
        if owned_start_sample <= detection.sample_start < owned_stop_sample:
            candidates.append(detection)
        awaiting_secondary_until = -1

    return candidates


def rsid_detector_hop_samples(sample_rate: int) -> int:
    return max(1, int(round(sample_rate * RSID_DETECTOR_HOP_SEC)))


def decode_rsid_code(tones: list[int]) -> tuple[int, int]:
    global _RSID_CODEBOOK
    if _RSID_CODEBOOK is None:
        _RSID_CODEBOOK = np.asarray(
            [encode_rsid(code) for code in RSID_VALID_CODES],
            dtype=np.uint8,
        )
    observed = np.asarray(tones, dtype=np.uint8)
    distances = np.count_nonzero(_RSID_CODEBOOK != observed, axis=1)
    index = int(np.argmin(distances))
    return RSID_VALID_CODES[index], int(distances[index])


def encode_rsid(code: int) -> list[int]:
    symbols = [code >> 8, (code >> 4) & 0x0F, code & 0x0F] + [0] * 12
    indices = [2, 4, 8, 9, 11, 15, 7, 14, 5, 10, 13, 3]
    for factor in indices:
        for index in range(RSID_SYMBOLS - 1, 0, -1):
            symbols[index] = symbols[index - 1] ^ gf16_multiply(symbols[index], factor)
        symbols[0] = gf16_multiply(symbols[0], factor)
    return symbols


def gf16_multiply(left: int, right: int) -> int:
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & 0x10:
            # fldigi's RSID GF(16) table uses x^4 + x^3 + 1.
            left ^= 0x19
    return result & 0x0F


def read_iq_window(
    *,
    data_path: Path,
    datatype: str,
    sample_start: int,
    sample_count: int,
) -> list[complex]:
    bytes_per_sample = BYTES_PER_COMPLEX_SAMPLE[datatype]
    with data_path.open("rb") as source:
        source.seek(sample_start * bytes_per_sample)
        data = source.read(sample_count * bytes_per_sample)
    if len(data) != sample_count * bytes_per_sample:
        raise RsidError("input ended while reading RSID detection window")

    if datatype == "ci16_le":
        return [
            complex(*struct.unpack_from("<hh", data, offset))
            for offset in range(0, len(data), 4)
        ]
    if datatype == "cf32_le":
        return [
            complex(*struct.unpack_from("<ff", data, offset))
            for offset in range(0, len(data), 8)
        ]
    raise AssertionError(f"unsupported RSID datatype: {datatype}")


def open_iq_source(*, data_path: Path, datatype: str) -> np.memmap:
    if datatype == "ci16_le":
        return np.memmap(data_path, dtype="<i2", mode="r").reshape((-1, 2))
    if datatype == "cf32_le":
        return np.memmap(data_path, dtype="<f4", mode="r").reshape((-1, 2))
    raise AssertionError(f"unsupported NumPy IQ datatype: {datatype}")


def read_iq_samples(
    *,
    source: np.memmap,
    datatype: str,
    sample_start: int,
    sample_count: int,
    dtype: Any = np.complex128,
) -> np.ndarray:
    stop_sample = sample_start + sample_count
    if stop_sample > source.shape[0]:
        raise RsidError("input ended while reading IQ window")
    window = source[sample_start:stop_sample]
    if datatype in {"ci16_le", "cf32_le"}:
        result = np.empty(sample_count, dtype=dtype)
        result.real = window[:, 0]
        result.imag = window[:, 1]
        return result
    raise AssertionError(f"unsupported NumPy IQ datatype: {datatype}")


def score_rsid_window(
    *,
    iq: np.ndarray,
    sample_start: int,
    sample_rate: int,
    symbol_samples: int,
    frequencies: np.ndarray,
    oscillators: np.ndarray,
    nominal_center_hz: float,
    mode_hint: str | None,
) -> RsidDetection:
    winners: list[int] = []
    ratios: list[float] = []
    winner_freqs: list[float] = []
    segments = iq.reshape((RSID_SYMBOLS, symbol_samples))
    power_matrix = np.abs(segments @ oscillators.T) ** 2 / (symbol_samples * symbol_samples)
    for segment, powers in zip(segments, power_matrix):
        noise_floor = float(np.median(powers)) or 1.0e-12
        winner = int(np.argmax(powers))
        winners.append(winner)
        winner_freqs.append(estimate_complex_tone_frequency(
            segment,
            sample_rate=sample_rate,
            fallback_hz=float(frequencies[winner]),
        ))
        ratios.append(max(float(powers[winner]) / noise_floor, 1.0e-12))

    confidence_ratio = sum(ratios) / len(ratios)
    confidence_db = 10.0 * math.log10(confidence_ratio)
    center_hz = estimate_rsid_center(winner_freqs, winners, nominal_center_hz)
    spread = (
        sum((10.0 * math.log10(ratio) - confidence_db) ** 2 for ratio in ratios)
        / len(ratios)
    ) ** 0.5
    uncertainty_hz = max(RSID_BAUD / 2.0, spread)
    return RsidDetection(
        sample_start=sample_start,
        sample_count=symbol_samples * RSID_SYMBOLS,
        mode=mode_hint or "unknown",
        center_hz=center_hz,
        confidence_db=confidence_db,
        uncertainty_hz=uncertainty_hz,
        tones=winners,
    )


def estimate_complex_tone_frequency(
    samples: np.ndarray,
    *,
    sample_rate: int,
    fallback_hz: float,
) -> float:
    if len(samples) < 2:
        return fallback_hz
    correlation = np.vdot(samples[:-1], samples[1:])
    if abs(correlation) < 1.0e-12:
        return fallback_hz
    measured = math.atan2(correlation.imag, correlation.real) * sample_rate / (2.0 * math.pi)
    # Resolve the principal phase result to the expected positive audio tone.
    measured += round((fallback_hz - measured) / sample_rate) * sample_rate
    if abs(measured - fallback_hz) > RSID_BAUD * 0.75:
        return fallback_hz
    return measured


def tone_power(samples: np.ndarray, frequency_hz: float, sample_rate: int) -> float:
    indexes = np.arange(len(samples), dtype=np.float64)
    oscillator = np.exp(-2.0j * np.pi * frequency_hz * indexes / sample_rate)
    total = np.dot(samples, oscillator)
    count = len(samples)
    return float((total.real * total.real + total.imag * total.imag) / (count * count))


def estimate_rsid_center(
    winner_freqs: list[float],
    winners: list[int],
    nominal_center_hz: float,
) -> float:
    if not winner_freqs:
        return nominal_center_hz
    offsets = [
        (winner - 7.0) * RSID_BAUD
        for winner in winners
    ]
    centers = [frequency - offset for frequency, offset in zip(winner_freqs, offsets)]
    centers.sort()
    return centers[len(centers) // 2]


def suppress_nearby_rsid_candidates(
    candidates: list[RsidDetection],
    *,
    sample_rate: int,
) -> list[RsidDetection]:
    selected: list[RsidDetection] = []
    exclusion = int(round(sample_rate * 1.5))
    for candidate in sorted(candidates, key=lambda item: item.confidence_db, reverse=True):
        if all(
            abs(candidate.sample_start - existing.sample_start) > exclusion
            for existing in selected
        ):
            selected.append(candidate)
    return sorted(selected, key=lambda item: item.sample_start)


def refine_rsid_start(
    *,
    data_path: Path,
    datatype: str,
    sample_rate: int,
    detection: RsidDetection,
    nominal_center_hz: float,
) -> int:
    symbol_samples = max(1, int(round(sample_rate / RSID_BAUD)))
    window_samples = symbol_samples * RSID_SYMBOLS
    iq_source = open_iq_source(data_path=data_path, datatype=datatype)
    frequencies = np.asarray(
        [
            nominal_center_hz + (tone - 7.0) * RSID_BAUD
            for tone in range(RSID_TONES)
        ],
        dtype=np.float64,
    )
    symbol_indexes = np.arange(symbol_samples, dtype=np.float64)
    oscillators = np.exp(
        -2.0j * np.pi * frequencies[:, np.newaxis] * symbol_indexes / sample_rate
    )

    current = detection.sample_start
    previous_hop = rsid_detector_hop_samples(sample_rate)
    for hop_sec in (0.05, 0.02, 0.01):
        hop_samples = max(1, int(round(hop_sec * sample_rate)))
        radius = max(previous_hop, hop_samples * 2)
        begin = max(0, current - radius)
        end = min(iq_source.shape[0] - window_samples, current + radius)
        if end < begin:
            break
        best_sample = current
        best_confidence = float("-inf")
        sample = begin
        while sample <= end:
            iq = read_iq_samples(
                source=iq_source,
                datatype=datatype,
                sample_start=sample,
                sample_count=window_samples,
            )
            candidate = score_rsid_window(
                iq=iq,
                sample_start=sample,
                sample_rate=sample_rate,
                symbol_samples=symbol_samples,
                frequencies=frequencies,
                oscillators=oscillators,
                nominal_center_hz=nominal_center_hz,
                mode_hint=detection.mode,
            )
            if candidate.confidence_db > best_confidence:
                best_confidence = candidate.confidence_db
                best_sample = sample
            sample += hop_samples
        movement = abs(best_sample - current)
        current = best_sample
        previous_hop = hop_samples
        if movement <= hop_samples:
            break
    return current


