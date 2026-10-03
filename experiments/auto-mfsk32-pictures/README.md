# Automatic MFSK32 picture correction

The [change record](../../docs/decoder/auto-mfsk32-pictures-change.md) defines
the October 3 automatic-dispatch fix and its retained baseline. This directory
contains supplemental evidence workflows; the original encoder qualification
is not regenerated with the changed decoder.

Use the repository virtualenv/source tree and the managed wrappers described
in `AGENTS.md`:

- `evaluate.py qualify` scores retained default-API candidate decodes of the
  ten unchanged Session 9 WAVs against the frozen v3 gate and creates the
  three-row candidate-set review. It checks input identities and confirms that
  only the pipeline differs among the 40 identified production files.
- `evaluate.py received` compares the retained 1,800-second received broadcast
  with its accepted diagnostic baseline, including complete text and nine PNG
  hashes. Run against a fresh candidate output directory.
- `pi_decode.py` runs the normal MFSK32 p8 portrait, difficult MFSK32 p2 chart
  and mixed-mode MFSK64 photo through the default public API. It converts the
  unchanged whole PCM WAV to analytic IQ without supplying mode/carrier/timing.
  Each case uses a fresh process; elapsed time and peak RSS include conversion,
  decode, quality calculation and diagnostic output.
- `tools/pi-verify-mfsk-auto-pictures.sh` invokes that subset against an
  isolated source bundle and existing WAV bundle. Stage source, command files,
  machine paths and returned artifacts in `.local/`; invoke via
  `tools/pi-remote.sh`. No package installation or installed-source replacement
  is needed.
- `probe_baseline.py` exercises the retained fixed-mode source with a known
  carrier, then reproduces the exploratory 8-kHz mixed fixture against current
  and retained automatic source. Its outputs classify separate existing
  limitations; they do not replace the frozen practical matrix.
- `compare_nondefault.py` sends the 8-kHz fixture's acquired MFSK32 text to
  the pre-change bounded picture algorithm and verifies that both rasters
  exactly match the corrected automatic output. Run these probes against the
  retained `.local/decoder-auto-mfsk32/baseline-source/` snapshot and fresh
  output directories after the default-rate evaluation.

The permanent regression is `tests/test_auto_picture_roundtrip.py`: a complete
default-rate MFSK32 → MFSK64 → MFSK32 broadcast with three representative-sized
pictures, recovered following text and usable compact-product references.
