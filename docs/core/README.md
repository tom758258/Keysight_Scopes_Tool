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
- Channel, timebase, trigger, acquisition, measurement, waveform, screenshot,
  and operation helpers.
- Simulator and fake backend support for hardware-free tests.
- Read-only analog acquisition sample rate query helpers.
- Read-only acquisition points and record-length query helpers, separate from
  waveform transfer points.
- Explicit triggered-capture wait helpers that arm `:SINGle`, poll
  `:OPERegister:CONDition?`, classify DSO-X 2000X/3000X/4000X completion by
  the Operation Status Condition Run bit, and expose raw poll values for
  adapter JSON.
- Model capability profiles used by the runtime.

Core does not own CLI output schema, command-line parser behavior, console
script documentation, or WebUI workflow.

## Docs

- Public import and API integration: `docs/integration.md`
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
