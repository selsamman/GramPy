# fldigi decodes on the Pi

Use this runbook when fldigi is the independent receiver for a GramPy decoder
comparison or MFSK encoder-compatibility check. The Pi owns the fldigi decode;
the Mac invokes a managed Pi command and reads the resulting evidence. Do not
start a persistent fldigi RPC service or a Mac RPC tunnel for this workflow.

## Tool map

| Tool or location | Purpose |
| --- | --- |
| `tools/pi-remote.sh [command-file]` in this repository | Runs one Pi command through the managed wrapper. It reads the target from `.local/pi-target.env` and defaults to `.local/pi-command.sh`. Use another `.local/` command file for a specific decode without overwriting an existing one. |
| `/opt/radiogram/current/tools/fldigi-decode-wav` on the Pi | The normal WAV receive adapter. It starts and cleans up fldigi, Xvfb, ALSA loopback, and XML-RPC; it enforces a decode lock and emits a `decode.tar` bundle. It defaults to RPC port 7362. |
| `/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64/install/bin/fldigi` on the Pi | The qualified receiver binary for reference ID `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`. Its SHA-256 is `dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3`. Put its directory first on `PATH` so the adapter selects it. |
| `/opt/radiogram/reference/session10d/qualification/fldigi-4.2.13-pi3-aarch64-q2/run-smoke.sh` and `/opt/radiogram/reference/session10d/corpus/*/run-corpus.sh` on the Pi | Historical, qualified invocation examples, including RxID and mapped-mode runs. They write into archived state; inspect them for flags and assertions, but do not rerun or edit them as a new candidate test. |
| `tools/fldigi-generate-wav` and `tools/pi-generate-*.sh` in this repository | Transmitter/fixture generation, **not** the receive adapter. |

The adapter is supplied by the Radiogram installation on the Pi, not by this
GramPy checkout. Verify the receiver binary identity on each qualification
run; a system `fldigi` can be an older version. The `current` adapter may also
change with a Radiogram deployment, so record its path and hash in durable
qualification evidence.

## Run a known RxID decode

Create a run-specific command file such as
`.local/pi-fldigi-decode-command.sh` with the following contents. This example
replays an existing Pi-side mode-change recording; replace the input and
expected text for another test. Keep new output separate from the archived
reference directories.

```sh
#!/bin/sh
set -eu

build=/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64
adapter=/opt/radiogram/current/tools/fldigi-decode-wav
input=/var/lib/radiogram/rsid-debug/wrmi-425-475.wav
work=$(mktemp -d /tmp/grampy-fldigi-decode.XXXXXX)
export PATH="$build/install/bin:$PATH"

test -s "$input"
test -x "$adapter"
test "$(fldigi --version | sed -n '1p')" = 'fldigi 4.2.13'
test "$(sha256sum "$build/install/bin/fldigi" | cut -d ' ' -f 1)" = \
    dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3
sha256sum "$input" "$adapter"

"$adapter" --input "$input" --output "$work/decode.tar" \
    --mode MFSK32 --rxid on --afc off --audio-frequency-hz 1500 \
    --debug-bundle full --nice 0 --post-playback-sec 15 \
    --audio-backend alsa-loopback --alsa-capture-plugin plug

test -s "$work/decode.tar"
sha256sum "$work/decode.tar"
printf 'decode_archive=%s\n' "$work/decode.tar"
```

From the repository on the Mac, run
`tools/pi-remote.sh .local/pi-fldigi-decode-command.sh` on a network-capable
execution surface. Pi commands, tests, and experiments must use the managed
wrapper; do not call SSH directly. One managed command may be active per
session. Its `.local/agent-runs/<session-id>/result.md` is the authoritative
exit record and `run.log` contains the command output. After incorporating a
completed result, remove only that completed session directory; never remove
one while `running.md` exists.

The archive contains `decoded.txt`, `metadata.json`, and, with
`--debug-bundle full`, `fldigi/control.log` and other diagnostics. For the
known example, require `control_exit_status: 0`, `rxid: "on"`, and the text
“This is Shortwave Radiogram in MFSK64”. Inspect the control log for RPC or
mode-change failures; exit status alone is not a reception pass. Record input,
adapter, binary, archive hashes, configuration, decoded text/images, and any
discrepancy. `/tmp` output is temporary: move or regenerate evidence into an
approved durable location before relying on it for qualification.

## Encoder-candidate qualification

The example above verifies the Pi receive path, not GramPy encoder output.
For encoder acceptance, follow the versioned matrix and manifest contract in
`docs/encoder/data/mfsk_encoder_pi_matrix_v2.json` and
`docs/encoder/data/mfsk_encoder_pi_qualification_manifest_v2.schema.json`.
Stage each generated WAV and its hash on the Pi, start fldigi in an unrelated
mode with RxID enabled, play the **entire WAV once** without manual mode
changes or window replay, and check every expected mode acquisition and
payload. Manual windows are diagnostics after failure, never a pass. The
checked-in end-to-end workflow is `tools/pi-qualify-mfsk-encoder.sh`; staging,
managed execution, scoring, and review instructions are in
`experiments/mfsk-wav-encoder/README.md`. The Session 8 evidence index is
`docs/encoder/data/session8/README.md`. Its picture failures require Session 9;
the known-recording example above is not candidate acceptance evidence.

The adapter owns RPC port 7362 and its own process lifecycle. If another
listener or persistent fldigi service is using the port, identify it and
resolve that conflict before starting a decode. Do not stop an unrelated
process merely because the port is occupied, and do not run independent
decodes concurrently against the adapter's lock.
