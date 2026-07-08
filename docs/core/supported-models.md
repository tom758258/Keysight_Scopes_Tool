# Supported Models

This document records public model support decisions for the Core runtime.
Command-level behavior remains documented in `../cli/README.md` and
`../contracts/`.

Capability profiles describe the runtime-supported and guarded feature surface.
They are not a claim that every feature has completed live validation on every
model, firmware, or transport.

## Runtime Profiles

Core detects DSO-X and MSO-X 2000X, 3000X, and 4000X series models from
`*IDN?` responses and maps them to runtime capability profiles.

| Series | Example models | Analog channels | Profile status |
| --- | --- | ---: | --- |
| 2000X | DSOX2004A | 2 or 4 from model key | Supported by capability profile |
| 3000X | DSOX3024A, MSOX3024A | 2 or 4 from model key | Supported by capability profile |
| 4000X | DSOX4024A, DSOX4034A | 2 or 4 from model key | Supported by capability profile |

The default runtime profile covers four-channel instruments when the model key
does not encode a two-channel variant.

## Capability Summary

All supported series profiles currently expose:

- BYTE and WORD waveform capture with a conservative 10,000-point safe maximum.
- Read-only measurement helpers and screenshot capture.
- Analog channel labels, display labels, and display annotation.
- Hardware-free Core/CLI/simulator/worker support for the documented one-shot
  trigger packs, including `trigger-tv` basic TV / video trigger configure and
  query.
- Triggered capture wait classification for DSO-X 2000X/3000X/4000X using the
  Operation Status Condition Run bit.

Series-specific differences:

- 2000X and 3000X channel labels allow up to 10 printable ASCII characters.
- 4000X channel labels allow up to 32 printable ASCII characters.
- 2000X and 3000X annotation uses one unindexed slot and does not support X/Y
  annotation position.
- 4000X annotation supports indexed slots 1 through 10 and X/Y annotation
  position.
- 4000X supports the guarded `delay` pair measurement path. 2000X and 3000X do
  not expose that helper because their delay query depends on measurement
  definition state.

Capability flags for raw waveform points mode, segmented memory, and serial
decode are currently disabled. Do not treat those future surfaces as supported
CLI, worker, or Core workflows.

## Live Validation Summary

Live validation is opt-in and model-specific. Normal automated tests remain
hardware-free.

| Model | Series | Connection | Public validation status |
| --- | --- | --- | --- |
| DSOX4024A | 4000X | USB | Full documented USB hardware plan passed by user report for the supported workflow set. |
| DSOX4024A | 4000X | LAN | Deferred until an explicit LAN resource is available and approved. |
| DSOX4034A | 4000X | USB | Focused validations passed by user report for recent compatibility work, including sample-rate, acquisition-points, record-length, force-trigger, triggered capture wait, channel labels, display labels, and indexed annotation. A full model matrix remains deferred. |
| DSOX4034A | 4000X | LAN | Deferred until an explicit LAN resource is available and approved. |
| DSOX3024A | 3000X | USB or LAN | Runtime profile exists; live validation is deferred until hardware is available. |
| DSOX2004A | 2000X | USB or LAN | Runtime profile exists; live validation is deferred until hardware is available. |

Detailed local hardware notes, exact lab resources, serial numbers, report
paths, and operator context belong in local-only validation notes, not in this
public document.

## Validation Boundaries

- Public capability JSON reports the runtime-supported feature surface only.
- Hardware validation must name the real instrument and command that was run.
- LAN support should be validated only after USB evidence and an explicit
  operator-selected LAN resource.
- Worker live validation is separate from one-shot CLI validation.
- No public document should hard-code private VISA resource strings, serial
  numbers, lab IP addresses, or local artifact paths.
