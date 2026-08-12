# Decoder design

## Purpose

The direct decoder consumes SigMF IQ recordings or bounded sample intervals
and produces deterministic MFSK32/MFSK64 text and MFSK64 picture results with
manifested provenance. It is an importable library with a thin CLI wrapper.

## Enduring design principles

- Preserve original-IQ sample coordinates and ancestry through derived data.
- Keep protocol interpretation separate from receiver acquisition and DSP.
- Use explicit state and bounded working sets so the implementation can run on
  the target Raspberry Pi.
- Prefer deterministic, reproducible results for identical input, configuration,
  dependency versions, and floating-point architecture.
- Preserve uncertainty and diagnostic evidence where it supports future
  improvement, without making diagnostics silently alter final decisions.
- Use offline look-ahead when it materially improves quality; streaming is a
  future organization, not a requirement for every implementation.
- Keep the decoder compatible with the existing IQ-preprocessor and appliance
  boundaries while those integrations mature.

## Major responsibilities

The decoder separates acquisition and coordinate handling, carrier and timing
tracking, tone evidence, soft bit mapping, deinterleaving and FEC, Varicode and
framing, picture assembly, and artifact publication. Implementations may fuse
or share work internally, but those observable responsibilities and contracts
remain distinct.

## Design rationale

This document and the accompanying contracts and validation records preserve
the design decisions needed to maintain GramPy. Archived development material
is intentionally not a repository dependency or implementation instruction.
