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
- Model capability profiles used by the runtime.

Core does not own CLI output schema, command-line parser behavior, console
script documentation, or WebUI workflow.

## Docs

- Public import and API integration: `docs/integration.md`
- Shared CLI, worker, and orchestrator contracts: `../contracts/`
