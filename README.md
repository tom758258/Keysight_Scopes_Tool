# Keysight Scope Tool

Python package and CLI for safe Phase 1 communication with Keysight
InfiniiVision oscilloscopes through PyVISA.

Current Phase 1 scope:

- List VISA resources.
- Query and parse `*IDN?`.
- Detect 2000X, 3000X, and 4000X series models.
- Load conservative capability profiles.
- Provide hardware-free tests through `FakeBackend`.

The package does not send `*RST` and does not change channel, trigger,
timebase, acquisition, waveform, or front-panel state in Phase 1.

## Setup

Use the project virtual environment workflow:

```powershell
uv venv
uv pip install -e ".[dev]"
```

PyVISA will use the default VISA backend discovered on the computer. On the
instrument computer, the preferred backend is the installed Keysight IO
Libraries vendor VISA backend. `pyvisa-py` is a fallback for systems without a
usable vendor backend.

## Commands

List visible VISA resources and print the PyVISA backend selected:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli list
```

Query and parse `*IDN?` from a resource:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli idn --resource "USB0::...::INSTR"
```

Add `--log-scpi` to print the SCPI command log for manual hardware checks:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli idn --resource "USB0::...::INSTR" --log-scpi
```

For repeated hardware checks you can set:

```powershell
$env:KEYSIGHT_SCOPE_RESOURCE = "USB0::...::INSTR"
.\.venv\Scripts\python.exe -m keysight_scope.cli idn
```

## Tests

Normal tests are hardware-free:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Real instrument checks are manual and should start with USB. See
`docs/hardware-test-plan.md`.
