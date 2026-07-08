# Keysight Scope Core

Core runtime package for Keysight InfiniiVision oscilloscope control through
PyVISA-compatible backends.

Distribution: `keysight-scopes`

Import package: `keysight_scope_core`

## Scope

Core owns runtime behavior:

- Safe resource opening and run-mode resolution.
- IDN parsing and series detection.
- Capability profiles for supported InfiniiVision models.
- Channel, display label, display annotation, common display one-shot,
  timebase, trigger, acquisition, measurement, waveform, screenshot, and
  operation helpers.
- Analog channel advanced setting helpers for impedance, invert, full-scale
  range, units, vernier, and probe skew.
- Simulator and fake backend support for hardware-free tests.
- Read-only analog acquisition sample rate query helpers.
- Read-only acquisition points and record-length query helpers, separate from
  waveform transfer points.
- Explicit triggered-capture wait helpers that arm `:SINGle`, poll
  `:OPERegister:CONDition?`, classify DSO-X 2000X/3000X/4000X completion by
  the Operation Status Condition Run bit, and expose raw poll values for
  adapter JSON.
- Analog-channel pulse-width trigger helpers for the Keysight
  `:TRIGger:GLITch...` command family. This first slice configures and queries
  pulse-width trigger state only; it does not run, stop, single, force trigger,
  wait for trigger, or capture waveform data.
- Analog-channel runt trigger helpers for the Keysight `:TRIGger:RUNT...` and
  shared `:TRIGger:LEVel:LOW/HIGH` command families. This slice configures and
  queries runt trigger state only; it does not run, stop, single, force
  trigger, wait for trigger, or capture waveform data.
- Analog-channel transition trigger helpers for the Keysight
  `:TRIGger:TRANsition...` and shared `:TRIGger:LEVel:LOW/HIGH` command
  families. This v1 slice configures and queries transition trigger state only;
  it does not run, stop, single, force trigger, wait for trigger, or capture
  waveform data.
- DSO analog ASCII pattern trigger helpers for the Keysight
  `:TRIGger:PATTern...` command family. This v1 slice configures
  `:TRIGger:MODE PATTern`, `:TRIGger:PATTern:FORMat ASCii`, raw `0/1/X`
  patterns, and `:TRIGger:PATTern:QUALifier ENTered`; query mode preserves
  raw pattern, edge source, and edge readbacks. It is hardware-free only so
  far; no live hardware validation has been run.
- DSO analog-only OR trigger helpers for the Keysight `:TRIGger:OR` command
  family. This v1 slice configures `:TRIGger:MODE OR` and raw `R/F/E/X` edge
  masks, and queries `:TRIGger:MODE?` plus `:TRIGger:OR?`. Pattern order
  follows Keysight OR trigger bit assignment: CH4, CH3, CH2, CH1 on
  4-channel DSO models and CH2, CH1 on 2-channel DSO models. MSO/digital OR
  trigger mapping is not implemented. It is hardware-free only so far; no live
  hardware validation has been run.
- Model capability profiles for the runtime-supported feature surface.
  DSO-X 3000X and 4000X profiles enable 50 ohm channel impedance support;
  DSO-X 2000X profiles keep channel impedance guarded to one-meg only.

Core does not own CLI output schema, command-line parser behavior, console
script documentation, or WebUI workflow.

## Docs

- Public import and API integration: `docs/integration.md`
- Supported model profiles and public validation status:
  `docs/supported-models.md`
- Shared CLI, worker, and orchestrator contracts: `../contracts/`



## Force Trigger

The Core runtime exposes a one-shot force-trigger helper:

```python
from keysight_scope_core.trigger import force_trigger_command

force_trigger_command() == ":TRIGger:FORCe"
```

The helper only returns the SCPI command string. It does not open VISA,
does not wait for the instrument, and does not change any acquisition or
trigger configuration. Higher-level force-trigger behavior belongs to the
CLI `force-trigger` command, which sends `:TRIGger:FORCe` and then performs one
`:SYSTem:ERRor?` post-check.

`capture --wait-trigger` uses separate Core trigger-wait helpers. That path is
explicitly opt-in, sends `:SINGle`, polls `:OPERegister:CONDition?`, and may
send `:TRIGger:FORCe` only when the caller requested force-on-timeout. DSO-X
2000X/3000X/4000X waits treat the Operation Status Condition Run bit as
pending when set and complete when clear; other live series remain conservative
until separately validated.
