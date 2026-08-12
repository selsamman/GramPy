# MFSK32, MFSK64, and MFSK Picture Wire Protocol

**Status:** wire-spec phase complete; review draft  
**Scope:** transmitted behavior required to interoperate with fldigi  
**Out of scope:** receiver architecture, DSP implementation, APIs, and pipeline
selection

## 1. Purpose

This document specifies the observable wire behavior needed to receive the
MFSK32, MFSK64, and MFSK picture transmissions used by Radiogram. It uses the
original MFSK16 specification as the baseline and records where fldigi matches,
extends, resolves an ambiguity in, or differs from that baseline.

This is a protocol specification, not a description of the fldigi
implementation. Source names are included only as provenance for behavioral
facts.

### 1.1 Requirement terms

The words **must**, **should**, and **may** describe interoperability
requirements, recommendations, and optional behavior respectively. They do not
describe the current implementation plan.

### 1.2 Evidence labels

Each substantive rule is assigned one of these evidence labels:

| Label | Meaning |
| --- | --- |
| `BASELINE` | Stated by the original published MFSK specification |
| `ARTICLE` | Described by the January 2001 explanatory article |
| `FLDIGI-4.2.12` | Confirmed in the pinned fldigi 4.2.12 source |
| `FLDIGI-4.2.06` | Confirmed in the pinned fldigi 4.2.06 source |
| `COMMON` | The two pinned fldigi versions agree |
| `DERIVED` | Mathematically derived from confirmed parameters |
| `CONTROLLED` | Measured from a version-pinned fldigi fixture with known input |
| `CAPTURE` | Confirmed against a real recorded transmission |

## 2. Normative targets and provenance

### 2.1 Published baseline

The baseline is the ARRL-hosted MFSK specification:

- “MFSK Spec,” attributed to Murray Greenman, ZL1BPU:
  <https://www.arrl.org/mfsk-spec>
- Murray Greenman, “MFSK for the New Millennium,” *QST*, January 2001:
  <https://www.arrl.org/files/file/Technology/tis/info/pdf/0101033.pdf>
- Murray Greenman and Nino Porcino, “An MFSK Mode for HF DX,” *ARRL and
  TAPR Digital Communications Conference*, 2000:
  <https://web.tapr.org/meetings/DCC_2000/DCC2000-MFSKmodeHF-ZL1BPU-IZ8BLYL.pdf>
- Nino Porcino and Murray Greenman, “The IZ8BLY MFSK Varicode,” version
  1.0, July 10, 2000:
  <https://www.qsl.net/zl1bpu/MFSK/Varicode.htm>

The baseline defines MFSK16, not MFSK32, MFSK64, or MFSK picture transfer.
Consequently, later-mode parameters and picture behavior are fldigi ecosystem
extensions unless another earlier public specification is found.

### 2.2 fldigi interoperability references

The primary fldigi reference is release 4.2.12:

- Tag: `v4.2.12`
- Commit: `b0032cabb70dc670064ed7561b9a626010a5e4ae`

The compatibility reference is release 4.2.06, which is the version used by
the existing Radiogram reference path:

- Tag: `v4.2.06`
- Commit: `ea5302cfe740a469354f98f9a3300351ac3d3b64`

Relevant source paths currently include:

- `src/mfsk/mfsk.cxx`
- `src/mfsk/mfsk-pic.cxx`
- `src/mfsk/interleave.cxx`
- `src/mfsk/mfskvaricode.cxx`
- `src/include/mfsk.h`
- `src/include/interleave.h`
- `src/include/mfskvaricode.h`
- `src/rsid/rsid.cxx`
- `src/rsid/rsid_defs.cxx`

The local GPL source checkout is an untracked research reference under
`.local/reference/fldigi/`. No fldigi source text is incorporated into the
Radiogram implementation.

Repository history places MFSK64 mode parameters in fldigi by July 2008
(`697650aba89affeac6a918b3def213e708b8fdf3`). The current multi-speed picture
header forms are also present in the July 2008 history. A September 2013 change
(`f5215cbf45c0c92e8f47d7c5761cc5e480b13ab7`) explicitly tuned picture receive
delays for MFSK16, MFSK32, MFSK64, and MFSK128. This supports treating MFSK64
and picture timing as established fldigi extensions rather than recent
4.2-series additions.

## 3. Protocol stack

An MFSK text transmission applies these transformations:

```text
text octets
→ IZ8BLY Varicode bit stream
→ rate-1/2, K=7 convolutional coding
→ diagonal bit interleaving
→ groups of four coded bits
→ Gray-coded selection of one of 16 tones
→ continuous-phase sequential single-tone FSK
```

MFSK picture transfer begins with an announcement carried through the text
path. After the announcement and a transition interval, the transmitter sends
an analog frequency-coded pixel raster instead of convolutionally coded MFSK
symbols. Text transmission resumes after the raster and transmitter flush.

**Evidence:** `BASELINE` for the MFSK16 text stack; `COMMON` for its use by
fldigi MFSK32/MFSK64 and for the text-to-picture state transition.

## 4. Physical layer

### 4.1 Signal form

Exactly one tone is active during each text symbol. Adjacent symbols are
contiguous: there is no intentional gap or amplitude shaping between them.
Transmitted phase is accumulated across sample and symbol boundaries, producing
continuous-phase FSK.

**Evidence:** `BASELINE`; `COMMON`, `mfsk::sendsymbol`.

The tone spacing is numerically equal to the symbol rate. This makes the tones
orthogonal over the nominal rectangular symbol interval.

**Evidence:** `BASELINE`; `COMMON`, mode construction in `mfsk::mfsk`.

### 4.2 Text-mode parameters

fldigi internally constructs both modes at an 8000 sample/second modem rate.
That internal rate is not itself a restriction on a compatible receiver.

| Parameter | MFSK32 | MFSK64 | Evidence |
| --- | ---: | ---: | --- |
| Tone count | 16 | 16 | `COMMON` |
| Bits per tone symbol | 4 | 4 | `COMMON` |
| Internal samples per symbol | 256 | 128 | `COMMON` |
| Symbol rate | 31.25 baud | 62.5 baud | `DERIVED` |
| Tone spacing | 31.25 Hz | 62.5 Hz | `DERIVED` |
| Lowest-to-highest tone span | 468.75 Hz | 937.5 Hz | `DERIVED` |
| Diagonal interleaver depth | 10 | 10 | `COMMON` |
| fldigi preamble parameter | 107 bits | 180 bits | `COMMON` |

Clean pinned printable-text fixtures were generated and independently decoded
by the packaged fldigi 4.2.06 receiver. The received payloads exactly match
their unique MFSK32 and MFSK64 inputs. Spectrum measurements across their
active intervals locate the sixteen expected tone centers with maximum
deviations of 4.11 Hz for MFSK32 and 11.75 Hz for MFSK64; the residuals reflect
short-record spectral estimation and continuous symbol transitions, not a
different spacing.

**Evidence:** `CONTROLLED`; MFSK32 WAV SHA-256
`9621633a1c6ba4297fbb2db24611f297f49d56520b45eb2334d843ba8553482d`;
MFSK64 WAV SHA-256
`4fe82965d4abaaff9bc9cc6d9a54d38f048ae049825de750bd99cb55cd755653`;
independent receive decodes.
| Picture capable | yes | yes | `COMMON` |

The occupied tone span in the table is fifteen tone intervals. It does not
include keying sidelobes or receiver guard bandwidth.

**Source:** `src/mfsk/mfsk.cxx`, constructor `mfsk::mfsk`, cases
`MODE_MFSK32` and `MODE_MFSK64`.

### 4.3 Tone ordering and Gray labeling

The original specification assigns ascending Gray labels to tones in increasing
frequency order. Tone zero is the lowest tone and represents `0000`; tone 15 is
the highest and represents `1000`.

| Tone | Bits | Tone | Bits |
| ---: | :---: | ---: | :---: |
| 0 | 0000 | 8 | 1100 |
| 1 | 0001 | 9 | 1101 |
| 2 | 0011 | 10 | 1111 |
| 3 | 0010 | 11 | 1110 |
| 4 | 0110 | 12 | 1010 |
| 5 | 0111 | 13 | 1011 |
| 6 | 0101 | 14 | 1001 |
| 7 | 0100 | 15 | 1000 |

fldigi applies this Gray mapping before tone selection. Reverse-sideband
operation reflects the physical tone index so the data labeling remains
consistent.

**Evidence:** `BASELINE`; `COMMON`, `mfsk::sendsymbol` and
`mfsk::softdecode`.

### 4.4 Center and absolute audio frequency

The wire protocol fixes tone spacing and relative ordering, not an absolute
audio center. The baseline calls for adjustable low and high audio placements
to accommodate radio filters. fldigi places the sixteen tones symmetrically
about the selected modem carrier.

For a selected center frequency \(f_c\), normal-sideband physical tone \(n\)
has frequency:

```text
f(n) = f_c + (n - 7.5) × tone_spacing
```

for \(n = 0,\ldots,15\). Reverse operation reflects this ordering.

**Evidence:** `BASELINE`; `COMMON`; formula `DERIVED` from
`mfsk::sendsymbol`.

## 5. Text coding

### 5.1 Varicode framing

fldigi maps each input octet through version 1.0 of the IZ8BLY MFSK Varicode
published by Nino Porcino and Murray Greenman on July 10, 2000. Bits are sent
most-significant first. Every table entry includes its terminating `00`;
therefore no additional delimiter is appended by the MFSK transmitter.

Before its terminal run of zeros, no codeword contains `00`. Some codeword data
ends in zero, so appending the `00` delimiter can produce a run longer than two
zeros. A receiver appends decoded bits to a shift register and recognizes a
boundary when its three-bit suffix is `001`: the last two zeros belong to the
prior terminated character and the final one is the first bit of the next
character. It then removes that final look-ahead bit and decodes the preceding
terminated codeword. This permits immediate recovery after a damaged or
unknown codeword at the next valid boundary.

Examples, including the terminator:

| Octet | Character | Transmitted bits |
| ---: | :---: | :--- |
| 32 | space | `100` |
| 101 | `e` | `1000` |
| 116 | `t` | `1100` |
| 13 | CR | `10101100` |
| 2 | STX | `11101101000` |
| 4 | EOT | `11101110000` |
| 0 | NUL | `11101011100` |

For example, `e`, space, `t` is the concatenation
`1000 100 1100`, with no additional separator.

**Evidence:** `BASELINE`; published “The IZ8BLY MFSK Varicode,” version 1.0;
`COMMON`, `mfsk::sendchar`, `mfsk::recvbit`, `varienc`, and `varidec`.

The complete table is committed as the octet-indexed
`data/mfsk_varicode.json` companion. All 256 entries were mechanically compared
with the July 10, 2000 publication and the pinned fldigi 4.2.12 table and
matched exactly. The companion's octet-indexed organization is original and
differs from the publication's character-frequency order.

Character-display semantics for extended octets are outside this wire
contract; they do not change the octet encodings.

### 5.2 Convolutional code

Text bits are encoded by a rate-1/2 convolutional code with constraint length
7. fldigi identifies its two generator masks as hexadecimal `0x6d` and `0x4f`.
These correspond numerically to octal 155 and 117.

**Evidence:** `BASELINE` for rate and constraint length; `COMMON`,
`NASA_K`, `POLY1`, and `POLY2` in `src/include/mfsk.h`.

For each input bit, fldigi obtains two coded output bits and appends them to the
interleaver input in output-index order zero followed by one.

**Evidence:** `COMMON`, `mfsk::sendbit`.

The encoder begins with a zero-valued seven-bit shift register. For each input
bit `u`, it performs:

```text
state = ((state << 1) | u) & 0x7f
c0 = parity(state & 0x6d)
c1 = parity(state & 0x4f)
```

where `parity` is one for an odd population count and zero for an even
population count. The serialized coded-bit order is `c0`, then `c1`.

**Evidence:** `COMMON`, `encoder::encode`, `encoder::init`,
`mfsk::sendbit`, and `parity`.

The hexadecimal masks are decimal 109 and 79, or octal 155 and 117. Published
sources sometimes write convolutional generators with reversed coefficient
orientation. A compatible implementation must follow the state transition and
parity equations above rather than selecting generators from notation alone.

The frozen companion `data/mfsk_wire_vectors.json` includes independently calculated
reset, leading-zero, isolated-one, mixed-bit, and representative Varicode
vectors. Repository tests recalculate them directly from the equations above;
the expected values are not produced by the future decoder.

### 5.3 Interleaving

For MFSK32 and MFSK64, four coded bits form the logical input presented to a
self-synchronizing diagonal interleaver. fldigi configures a four-lane,
depth-ten interleaver.

**Evidence:** `BASELINE`; `COMMON`, `mfsk::mfsk` and
`interleave::symbols`.

The forward transformation can be specified with ten concatenated 4-by-4
stages. Each stage begins filled with zeros. For each four-bit input group
`x[0..3]`, a stage shifts each of its four rows one position toward column zero,
places `x[i]` in row `i`, column 3, and emits:

```text
y[i] = stage[i][3 - i]
```

The output group of one stage is the input group of the next. The output of the
tenth stage is interpreted as the four-bit tone-label value. This definition
also fixes the lane ordering: `x[0]` is the first coded bit accumulated for the
group and becomes its most-significant bit when packed.

**Evidence:** `BASELINE` specifies ten concatenated 4-by-4 IZ8BLY diagonal
interleavers; `COMMON`, `interleave::symbols`, `interleave::bits`, and
`mfsk::sendbit`.

At transmitter initialization all stage storage is zero. At receiver
initialization fldigi uses neutral soft values rather than hard zero bits; that
is receiver behavior and is not part of the transmitted protocol.

The 2000 DCC paper describes the ten-stage construction as spreading bits over
approximately 94 bit positions with a 71-bit delay. These published values are
useful independent checks on vectors generated from the transformation above.

A preliminary numbered-group evaluation exposes an apparent fldigi difference
from the published forward diagonal. The July 2000 interleaver document gives
the first complete single-stage outputs as `AFKP`, `EJOT`, `INSX`, and `MRW1`.
With lettered input groups `ABCD`, `EFGH`, `IJKL`, and `MNOP`, that published
orientation emits the oldest value from lane zero and the newest from lane
three. Current fldigi's transmitter-facing `INTERLEAVE_FWD` path selects the
opposite diagonal: after startup the corresponding group is ordered newest
lane zero through oldest lane three. fldigi's `INTERLEAVE_REV` path selects the
published diagonal and reverses its transmitter path correctly.

The two fldigi versions agree on this behavior, so a receiver interoperating
with fldigi must use fldigi's transmitted orientation even if the names
“forward” and “reverse” differ from the 2000 document.

For input group number `t`, current fldigi's ten-stage transmitter output is:

```text
[x0(t), x1(t - 10), x2(t - 20), x3(t - 30)]
```

with zero fill for negative group indices. Thus the four bits that entered
together emerge with delays of 0, 40, 80, and 120 serialized coded-bit times.
The average delay is 60 bit times and the first-to-last serialized position
spans 124 positions inclusive.

Applying the published diagonal orientation ten times instead gives:

```text
[x0(t - 30), x1(t - 20), x2(t - 10), x3(t)]
```

with the same average delay but the lane delays reversed. Neither exact result
directly reproduces the published summary of 94-bit spread and 71-bit delay.
Those figures may use a different definition, describe a different historical
implementation, or be erroneous. They are not used as fldigi wire parameters.

The 94-bit/71-bit summary is retired as a normative interoperability value.
The publication does not define measurement endpoints that reproduce it, and
neither published diagonal orientation nor fldigi's transmitted orientation
produces those figures under serialized-bit delay or inclusive-span
definitions. The exact transformation and independently checked vectors govern
this specification; the historical numbers are retained only to document the
baseline discrepancy.

The frozen companion `data/mfsk_wire_vectors.json` publishes numbered-group values,
both closed-form lane-order rules, serialized lane delays, average delay, and
inclusive span. Its lettered example makes the orientation difference concrete:
given groups `ABCD`, `EFGH`, `IJKL`, and `MNOP` at group times 0, 10, 20, and
30, fldigi emits `MJGD` at time 30 while the published forward orientation
emits `AFKP`.

### 5.4 Symbol assembly

The convolutional encoder emits two coded bits per input bit. Coded bits are
accumulated until four bits are available, interleaved, interpreted as a
four-bit value, Gray encoded, and mapped to a physical tone.

MFSK32 and MFSK64 share this coding structure. Their principal confirmed
physical difference is symbol duration/tone spacing.

**Evidence:** `COMMON`, `mfsk::sendbit` and `mfsk::sendsymbol`.

## 6. Transmission framing and encoder flush

### 6.1 Start

The original MFSK16 specification calls for the lowest tone to be transmitted
for eight symbol periods at the beginning of a transmission.

**Evidence:** `BASELINE`.

fldigi first primes the encoder and interleaver with its mode-specific preamble
count without transmitting the resulting symbols. This is internal state
initialization and has no direct wire duration.

fldigi 4.2.12 then transmits `floor(preamble / 3)` zero input bits through the
normal FEC, interleaver, and tone path: 35 bits for MFSK32 and 60 bits for
MFSK64. It next sends carriage return, STX (`0x02`), and carriage return through
the normal Varicode/FEC path.

In fldigi 4.2.06 the transmitted leading-zero loop is disabled, while the
non-transmitted state priming and `CR`, STX, `CR` sequence remain.

**Evidence:** `FLDIGI-4.2.12` and `FLDIGI-4.2.06`,
`mfsk::clearbits` and `mfsk::tx_process`.

This leading-zero count is a confirmed wire-visible difference between the
pinned versions. A receiver must not require it: acquisition may begin directly
with the coded start sequence or after an arbitrary partial preamble.

### 6.2 Idle

When no text character is available, fldigi sends the Varicode representation
of NUL, a one bit, and 32 zero bits through the normal FEC/interleaving path.

**Evidence:** `BASELINE` describes periodic nonprinting-character stuffing plus
an extended zero stream; `COMMON`, `mfsk::sendidle`.

### 6.3 End and flush

fldigi sends carriage return, EOT (`0x04`), and carriage return, then injects
one input bit of value one followed by the mode's preamble count of zero input
bits: 107 zeros for MFSK32 and 180 for MFSK64. These bits pass through the
normal convolutional encoder, interleaver, and symbol mapper to flush delayed
content.

**Evidence:** `BASELINE` for the general flush requirement; `COMMON`,
`mfsk::flushtx` and `mfsk::tx_process`.

Version 4.2.12 may additionally emit zero-bit pairs while applying its
configuration-dependent soft-stop envelope. Version 4.2.06 applies its stop
signal at a different point. These samples occur after the stable EOT and flush
contract. Their exact duration and amplitude are transmitter-envelope
behavior, not message framing; receivers should tolerate trailing coded zeros
and arbitrary carrier ramp-down without assigning them semantic content.

**Evidence:** `COMMON` for the end characters and `1`-then-zero flush;
`FLDIGI-4.2.12` and `FLDIGI-4.2.06` for leading-zero and envelope differences;
`mfsk::clearbits`, `mfsk::flushtx`, and `mfsk::tx_process`.

## 7. Picture announcement and transition

### 7.1 Announcement grammar

fldigi sends a human-readable line containing `Sending ` followed by one of
these control tokens:

```text
Pic:<width>x<height>;
Pic:<width>x<height>C;
Pic:<width>x<height>p<samples-per-pixel>;
Pic:<width>x<height>Cp<samples-per-pixel>;
```

`C` selects color; its absence selects grayscale. If the `p` suffix is absent,
samples per pixel defaults to 8. fldigi’s transmitter UI currently selects 8,
4, or 2 samples per pixel. Width and height are decimal positive integers.

The receiver accepts dimensions from 1 through 4095 inclusive. That receiver
limit describes fldigi interoperability but does not prove that every such
size is practical.

**Evidence:** `COMMON`, `pic_TxSendColor`, `pic_TxSendGrey`, and
`mfsk::check_picture_header`.

The parser scans a rolling window for `Pic:`; the preceding `Sending ` text and
newline are conventional transmitter output but are not required to trigger
fldigi picture reception.

**Evidence:** `COMMON`, `mfsk::check_picture_header`.

### 7.2 Transition

The announcement is encoded through the normal text path. The transmitter then
flushes the text encoder/interleaver, emits a fixed-frequency prologue, and
begins the pixel raster.

The text flush injects one input bit with value one followed by the mode's
`preamble` count of zero input bits. For MFSK32, one plus 107 input bits
produces 54 complete symbols and lasts 1.728 seconds. For MFSK64, one plus 180
input bits produces 362 coded bits. Because the header can leave the
four-coded-bit symbol accumulator either empty or half full, the flush emits
90 or 91 complete MFSK64 symbols and then discards any residual partial group.
Its wire duration is therefore 1.440 or 1.456 seconds.

Next, fldigi emits 352 internal samples (44 ms) at the normal-sideband
frequency `center - bandwidth/2`. This equals the frequency representing pixel
value zero. The first actual pixel component follows immediately. Phase is
continuous through the text symbols, transition prologue, and raster.

**Evidence:** `COMMON`, `mfsk::flushtx`, `mfsk::send_prologue`,
`mfsk::flush_xmt_filter`, `mfsk::sendpic`, and `tracepair(45, 352)`; durations
`DERIVED`.

The controlled MFSK64 color fixture locates the first raster component at WAV
sample 822712. The immediately preceding 2112 samples at 48000 Hz are exactly
44 ms, begin at sample 820600, and have a median frequency of 1028.70 Hz
against the expected 1031.25 Hz low endpoint. This independently confirms the
prologue duration, frequency, and adjacency to the raster.

**Evidence:** `CONTROLLED`, fixture and hashes in
`data/mfsk_fixture_evidence.json`.

The receiver detects the completed announcement only after Varicode,
deinterleaving, and Viterbi latency. It therefore delays its switch to picture
reception so that the receiver state change aligns with the earlier-arriving
pixel waveform.

**Evidence:** `COMMON`, transmitter states `TX_STATE_DATA`,
`TX_STATE_PICTURE_START`, and receiver states `RX_STATE_PICTURE_START`,
`RX_STATE_PICTURE`.

For MFSK64, fldigi 4.2.12 uses a mode-specific receiver delay initialized to
4956 internal 8000-Hz samples, with a conditional additional symbol interval
based on the decoder’s position within the four-bit symbol.

**Evidence:** `FLDIGI-4.2.12`, `mfsk::recvchar`.

For specifications and diagnostics, transition positions use these distinct
events:

1. **Header character completion:** the final semicolon has been recovered as
   an octet after receiver decoding. This is a logical event and has no unique
   raw-sample position because FEC and interleaving distribute its evidence.
2. **Prologue start:** the first sample after the last complete MFSK symbol
   emitted by the header flush.
3. **First raster sample:** the first sample after all 352 internal prologue
   samples.

A receiver may report its own estimated raw-sample positions for the latter
two events. It must not treat fldigi's decoder-latency compensation constant as
a transmitted duration.

## 8. Picture raster

### 8.1 Pixel modulation

Each pixel component is an unsigned value from 0 through 255. It is represented
by a constant-frequency interval centered around the selected modem carrier.
For normal operation fldigi transmits:

```text
pixel_frequency(v) = center_frequency
                   + bandwidth × (v - 128) / 256
```

where fldigi’s `bandwidth` is the lowest-to-highest MFSK tone span:
468.75 Hz for MFSK32 and 937.5 Hz for MFSK64. Reverse operation negates the
frequency/intensity direction.

**Evidence:** `COMMON`, `mfsk::sendpic`; bandwidth values `DERIVED`.

This mapping is slightly asymmetric around the endpoints because the divisor is
256: value 0 maps to center minus one-half bandwidth, while value 255 maps to
center plus 127/256 bandwidth.

**Evidence:** `DERIVED`.

| Mode | Value 0 offset | Value 128 offset | Value 255 offset |
| --- | ---: | ---: | ---: |
| MFSK32 | -234.375 Hz | 0 Hz | +232.5439453125 Hz |
| MFSK64 | -468.75 Hz | 0 Hz | +465.087890625 Hz |

### 8.2 Pixel duration

At fldigi’s internal 8000-Hz modem rate, a component value is held for the
announced samples-per-pixel count:

| Suffix | Samples/component | Duration/component | Components/second |
| --- | ---: | ---: | ---: |
| absent or `p8` | 8 | 1.000 ms | 1000 |
| `p4` | 4 | 0.500 ms | 2000 |
| `p2` | 2 | 0.250 ms | 4000 |

**Evidence:** `COMMON`, `mfsk::sendpic`; timing `DERIVED`.

Phase remains continuous between pixel components and across block boundaries.

**Evidence:** `COMMON`, accumulated transmitter phase in `mfsk::sendpic`.

### 8.3 Grayscale raster order

For grayscale, pixels are transmitted in row-major order: left to right within
each row, then top to bottom. fldigi converts RGB source material to one
luminance byte using integer weights 31% red, 61% green, and 8% blue before
transmission.

The RGB-to-gray conversion is transmitter behavior, not part of decoding an
already formed grayscale raster.

**Evidence:** `COMMON`, `pic_TxSendGrey`, receiver `mfsk::recvpic`.

The clean pinned MFSK64 grayscale fixture independently confirms the integer
luminance conversion and row-major raster. Its receiver validation decodes
`Sending Pic:8x4;` and produces an image. The known 32-component sequence
occupies exactly 1536 samples at 48000 Hz, or 32 ms. Its measured frequency
error is 7.27 Hz RMS with an 18.82 Hz maximum absolute error. Repeated endpoint
medians are 1030.62 Hz for value 0, 1493.82 Hz for value 128, and 1958.42 Hz
for value 255, against expectations of 1031.25, 1500, and
1965.087890625 Hz.

**Evidence:** `CONTROLLED`, pinned source and binary identified in Section
8.4, grayscale WAV SHA-256
`8f0c4707296e1d0f7718f43abad865081ec7204e08263836733784e07d8101d5`,
independent receive decode, and reproducible fixture analysis.

### 8.4 Color raster order

For color, each row is transmitted as three complete component scan lines:

```text
row 0 red, row 0 green, row 0 blue,
row 1 red, row 1 green, row 1 blue,
...
```

Within each component scan line, pixels proceed left to right.

**Evidence:** `COMMON`, `pic_TxSendColor`, `updateTxPic`, and
`mfsk::recvpic`.

The pinned primary MFSK64 fixture independently measures these rules from a
known 8-by-4 RGB vector. At the 48000-Hz WAV rate, the best-matching raster
begins at sample 822712 and contains exactly 4608 samples:

```text
8 columns × 4 rows × 3 components × 48 WAV samples/component
    = 4608 samples = 96 ms
```

Measured frequency error against the row-wise red, green, blue plane sequence
is 11.33 Hz RMS. The two plausible alternative layouts are decisively worse:
463.08 Hz RMS for pixel-interleaved RGB and 468.99 Hz RMS for three whole-image
component planes. Median measurements for repeated endpoint values are
1025.43 Hz for value 0 (expected 1031.25 Hz), 1498.19 Hz for value 128
(expected 1500 Hz), and 1966.42 Hz for value 255 (expected
1965.087890625 Hz). Short-interval measurement and audio resampling account
for the residual error; the ordering alternatives differ by hundreds of hertz.

**Evidence:** `CONTROLLED`, pinned commit
`b0032cabb70dc670064ed7561b9a626010a5e4ae`, binary SHA-256
`de63a235e959e01e31ab05045fd703d59d3ee74017b64d9b254e8f48cb0d6e9c`,
WAV SHA-256
`1105fb392d59a55ed315c9552118391e489b0210828a3197489e68fffadd4721`,
and reproducible `tools/analyze-mfsk-color-fixture` output.

### 8.5 Completion and return to text

The raster contains exactly `width × height` component values for grayscale and
`width × height × 3` component values for color. No separate checksum or
picture FEC has been identified.

After sending the raster, fldigi flushes the text modem state and resumes its
text state. The receiver counts the announced raster duration, saves the
completed image, and reinitializes text reception.

**Evidence:** `COMMON`, `mfsk::tx_process`, `mfsk::rx_process`.

The final raster component is followed immediately by the same text-path flush
defined in Section 6.3: one input bit of value one and then 107 zero bits for
MFSK32 or 180 zero bits for MFSK64. Because picture transmission begins after
a header flush has cleared the partial symbol accumulator, the post-picture
flush emits exactly 54 MFSK32 symbols (1.728 seconds) or 90 MFSK64 symbols
(1.440 seconds); MFSK64 discards the final half-symbol after advancing the
encoder. There is no additional picture delimiter.

After this flush the transmitter returns directly to its text-data state.
Queued text may therefore begin on the next transmitter processing cycle; if
none is queued, the normal idle sequence is sent. A receiver must use the
post-picture flush as its reacquisition interval rather than require an
additional silence or marker.

**Evidence:** `COMMON`, `mfsk::flushtx` and the transition from
`TX_STATE_PICTURE` to `TX_STATE_DATA`; counts and durations `DERIVED`.

Real Shortwave Radiogram material may include additional operational spacing,
but such spacing is not part of the fldigi wire contract.

## 9. RSID relationship

RSID is an in-band mode-identification protocol preceding mode segments. It is
not part of the MFSK text or picture encoding described above, but it provides
mode and timing evidence to the surrounding receiver.

Radiogram’s existing `iqprep` implementation has independently validated:

- MFSK32 primary code 147.
- Extended-mode escape code 6.
- MFSK64 secondary code 620 following the escape and defined gap.

The MFSK wire spec will reference, rather than duplicate, the eventual RSID wire
section or companion specification.

## 10. Initial capture confirmation

The archived Shortwave Radiogram program 453 decode is a real received
transmission containing MFSK32 text, a transition to MFSK64, ten MFSK64 color
pictures, and a return to MFSK32. Its decoded text contains conventional
headers without a speed suffix, including:

```text
Sending Pic:199x139C;
Sending Pic:175x175C;
Sending Pic:137x199C;
```

The corresponding fldigi PNG outputs have exactly the announced dimensions.
All ten MFSK64 picture headers in this recording use `C` and omit `p`, selecting
the default eight samples per component.

**Evidence:** `CAPTURE`,
`tests/samples/archive/program453/decoded.txt` and
`tests/samples/archive/program453/decodedImages/`.

This confirms the announcement grammar, dimensions, color flag, default speed,
and successful MFSK64 picture reception. It does not independently establish
frequency endpoints, channel order, or the precise header-to-raster sample
boundary; those require IQ/audio measurement or a controlled transmitted
image.

## 11. Baseline-to-fldigi gap matrix

| Area | Circa-2000 baseline | fldigi MFSK32/MFSK64 | Classification |
| --- | --- | --- | --- |
| Modes | MFSK16 and MFSK8 | Adds MFSK32 and MFSK64 | Extension |
| Text modulation | Sequential, continuous-phase orthogonal tones | Same technique with faster mode parameters | Match plus extension |
| Tone labels | Four-bit Gray labels for 16 tones | Same labels | Match |
| FEC | Rate 1/2, K=7 NASA code | Same code; exact masks and serialization made explicit | Ambiguity resolved |
| Interleaver | Ten concatenated 4-by-4 diagonal stages; published forward example `AFKP` | Same dimensions, but transmitter-facing diagonal orientation appears reversed relative to the published example | Apparent variation |
| Varicode | IZ8BLY table with terminated codewords and `001` boundary interpretation | Same 256-octet table and boundary recognition | Match |
| Start | Lowest tone for eight symbol periods | Mode-specific state fill and version-dependent transmitted zero sequence, followed by CR/STX/CR | Variation/extension |
| Idle | NUL plus an extended zero stream, example length 16 | NUL, one bit, then 32 zero bits | Ambiguity resolved/extension |
| End | Flush pending characters and zeros to an idle interval | CR/EOT/CR plus one bit and mode-specific zero count | Extension |
| Picture | Not specified | Text header, flush, prologue, analog frequency raster, return to text | fldigi extension |
| RSID | Not specified | Separate in-band mode identification | Ecosystem extension |

The interleaver row is the most significant baseline-to-fldigi incompatibility
found. The exact published-versus-fldigi rules and independently checked
numbered and lettered vectors are recorded in Sections 5.3 and 14 and in
`data/mfsk_wire_vectors.json`.

## 12. Controlled transmitter fixtures

Controlled fixtures complement, but do not replace, received IQ. A pinned
fldigi transmitter can exercise exact text, mode, header, picture dimensions,
picture type, and pixel values without relying on what happened to appear in a
broadcast recording.

Shortwave Radiogram is understood to supply a fldigi-generated audio file to
the station for broadcast. On that assumption the RF station is a transport
path, not another MFSK wire implementation. Exact controlled fldigi fixtures
are therefore sufficient primary evidence for deterministic wire rules.
Received recordings confirm ecosystem compatibility and characterize
transport and receiver conditions; they need not independently reconstruct
every bit or pixel rule, and controlled fixtures need not be rebroadcast over
RF to qualify as wire evidence.

The intended fixture chain is:

```text
pinned fldigi TX
    -> captured mono WAV with guard audio
    -> tools/wav-to-sigmf
    -> cf32_le analytic IQ plus provenance metadata
```

fldigi exposes XML-RPC controls for selecting a modem, setting its carrier,
loading transmit text, entering transmit state, and running a macro. Its macro
language supports color and grayscale image directives, which enter the same
MFSK picture transmitter paths as the UI.

The complete mechanism has been demonstrated on the Linux fixture host with
fldigi 4.2.06: headless launch under Xvfb, XML-RPC mode and carrier selection
with readback, an ALSA-loopback WAV capture, macro-driven transmission of a
controlled 3-by-2 RGB PNG, macro-controlled return to receive after the image,
explicit recorder-overrun rejection, and WAV-to-SigMF conversion. The proof artifacts
are intentionally kept under ignored `.local/` storage. The parameterized
generator has now also produced the primary fixtures from pinned v4.2.12 commit
`b0032cabb70dc670064ed7561b9a626010a5e4ae`; that binary reports version
4.2.11, so both the tag commit and binary-reported version are retained in
provenance. The 4.2.06 fixtures remain compatibility evidence.

The first primary image input is the binary P6
`tests/fixtures/mfsk/primary-color-8x4.ppm`, SHA-256
`21d5e19be8566a266d8c01f214e4049b59b9fdbba96ab1069178e88a548dc104`.
An equivalent PNG has SHA-256
`33e1986427384be02803fe5e8785f3068d17bbacaf6fb6f5b7f880cfea188ea2`.
Its normative RGB byte vector is defined independently in
`generate_primary_color_8x4.py`. The four rows exercise a grayscale ramp,
primary and secondary colors, independent component levels, and asymmetric
mixed values. This makes a single short transmission useful for checking:

- the `Pic:8x4C;` announcement;
- header-to-picture transition timing;
- row-major geometry;
- red, green, then blue row-plane order;
- frequency mapping at 0, 128, and 255 plus intermediate values;
- picture completion followed by the fixture macro's explicit return to
  receive.

`tools/pi-generate-primary-mfsk-fixture.sh` requires the exact pinned source
commit, invokes the isolated reference binary explicitly, and fetches the WAV,
generator metadata, source image, binary build result, logs, and hashes. The
WAV is then converted by `tools/wav-to-sigmf`; both representations remain
classified as fldigi-derived controlled fixtures rather than received IQ.

Analytic conversion preserves the fldigi audio waveform as a one-sided complex
baseband representation. It does not add multipath, fading, noise, clock error,
receiver filtering, tuning error, or any other radio transport effect.
Therefore:

- call these **fldigi-derived analytic IQ fixtures**, not synthetic broadcasts
  or captured IQ;
- use them for exact wire behavior and decoder-regression tests;
- use real received IQ for product interoperability acceptance;
- use deliberately impaired real IQ for controlled robustness and negative
  tests when the real corpus does not contain the required condition.

## 13. Confirmed 4.2.06 versus 4.2.12 differences

| Area | 4.2.06 | 4.2.12 | Wire significance |
| --- | --- | --- | --- |
| Start preamble | Zero-bit transmit loop disabled | Zero-bit transmit loop active for ordinary MFSK modes | Confirmed wire-visible |
| MFSK AFC ordering/averaging | Earlier guard order and fixed averaging constant | Reordered guards and configurable averaging | Receiver-only |
| Picture viewer sizing | Earlier UI layout | Revised UI layout | None |
| RSID logic | Requires separate comparison | Changed | Potential mode-acquisition effect; RSID companion scope |

The two versions otherwise agree on the target modes' tone parameters, Gray
mapping, Varicode table, convolutional code, interleaver transformation,
picture header grammar, pixel frequency mapping, speed suffixes, and raster
order. The picture-source diff between these releases is UI-only.

## 14. Independent vectors

The completed wire-spec phase includes the following protocol vectors:

1. Gray label and physical-tone mapping for all sixteen tones.
2. Convolutional encoder output from reset for a short fixed input.
3. Four-lane, depth-ten interleaver fill and steady-state output.
4. Complete Varicode encodings for representative printable and control octets.
5. A short text sequence transformed through Varicode, FEC, interleaving, and
   physical tone indices.
6. MFSK32 and MFSK64 timing vectors.
7. Grayscale and color picture headers, transition timing, component order, and
   frequency values for pixels 0, 128, and 255.

Vectors must not be generated solely by the decoder implementation being
tested. Provenance for each expected result must be recorded.

The committed `data/mfsk_wire_vectors.json` includes the fixed coding, interleaving,
mode-timing, framing, picture-mapping, and complete `e t` text-to-physical-tone
vector. `data/mfsk_varicode.json` supplies the complete independently compared
256-octet table. `data/mfsk_fixture_evidence.json` records the generator identity,
artifact hashes, independent-receiver outcomes, and key measurements for the
controlled fixture matrix. The large waveform artifacts remain untracked under
`.local/`.

## 15. Phase completion

Received-IQ inventory, slicing, annotations, impairment cases, and acceptance
metrics are deliberately deferred until the capabilities and pipeline-options
specifications establish their required inputs, state history, intermediate
observability, and failure cases. They are implementation/test-corpus work, not
open wire-protocol questions.

Reverse-sideband transmission is source-confirmed in both pinned versions as
reflection of physical text-tone indices and negation of picture frequency
offsets around the selected carrier. Attempts to control the reverse button
through fldigi's advertised headless XML-RPC setter and toggle APIs did not
survive immediate or delayed readback, so no controlled artifact was accepted.
That automation limitation does not create a conflicting wire interpretation.
A future manually controlled reverse fixture may cross-check receiver behavior,
but it is not a prerequisite for the capabilities specification.
