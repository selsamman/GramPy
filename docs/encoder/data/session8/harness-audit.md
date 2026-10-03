# Receiver harness audit (2026-10-02)

The [HTML human review](comparison.html) shows all seven Session 8 images,
known originals, local GramPy recovery, and pinned fldigi saved PNGs. It
provides speed/color filters, nearest-neighbor enlargement, exact component
error counts, and pixel-hover comparisons. The original failed qualification
results remain unchanged.

## Comparison with decoder qualification

The archived Session 10D qualification and corpus scripts invoke the same
`/opt/radiogram/current/tools/fldigi-decode-wav` path and the same pinned fldigi
4.2.13 binary. Both use ALSA loopback with `plug` capture, AFC off, no
niceness adjustment, and a 15-second post-playback wait.

More directly, archived small-image receiver bundles contain **byte-identical**
control scripts and ALSA configuration files to the corrected Session 8 run:

| Artifact | SHA-256 in both runs |
| --- | --- |
| `fldigi/control.py` | `4d38bb0bb1025f458722179b28642a4386b1e02975268e689abb8045c88d34f2` |
| `fldigi/asound.conf` | `7fbe5a215fa9ad00602d396c7037b809970b72a2acd35f52b756d0cd2808c499` |

The current adapter's hash matches its retained Session 8 copy:
`130fe71cef0bbc5585f9cdf74c423cd94999ee34720b277a09814c06d046a211`.
The complete historical adapter file was not available in these archived
bundles, so its whole-file byte identity is not established.

Runtime settings differ. Historical small-image cases started in MFSK64 with
RxID off and used adapter-generated configuration. Session 8 started in
BPSK31 with automatic RxID and explicitly supplied fresh receiver settings.
Its requested polling interval was 0.25 seconds, clamped by the same control
script to 0.5 seconds; the historical default was 5 seconds. The first Session
8 attempt had an incorrect audio setting, which was corrected before the
second run. These differences must remain explicit in any control experiment.

## Historical artifact concern

The historical smoke script asserted expected text, minimum picture count,
and absence of RPC connection refusal. It did **not** assert that PNGs were
decodable, correctly dimensioned, or pixel-faithful.

Read-only inspection of the original archived small-image bundles found:

- The grayscale artifact is a 143-byte PNG that neither the Pi's Pillow nor
  the repository's Pillow can decode. Its IHDR declares 136 × 104, despite
  the case naming an 8 × 4 grayscale fixture. The original bytes are retained.
- The color artifact is a readable 8 × 4 RGB image. Its pixel hash is
  `5818c81a454a0d69ddecaa4bfb7b868ed416e561da83eb7a933518331b831b97`,
  different from the current known original's
  `52334109d177d2ed03802ab1c206d4a717d1fe26bbd89d5a6ecde6116a5d3007`.
  Source-image identity must be verified before interpreting that historical
  difference as a quantitative decoder error.

[Archived image bytes, metadata, hashes, and decoding results](harness-audit/archived-images.json)
and [historical invocations](harness-audit/historical-invocations.log) are
preserved without changing or rerunning the archived qualification.

This strengthens the need to investigate the shared receiver/save path and
the old qualification's image assertions. It does not prove the native
encoder is correct, identify a save race conclusively, or invalidate every
historical corpus image. The next controlled test should compare identical
source images, autosaved artifacts and the fully updated viewer, while
holding receiver startup/settings constant.
