# Keysight Scope Tool

Python package and CLI for safe communication with Keysight
InfiniiVision oscilloscopes through PyVISA.

Current implemented scope:

- List VISA resource strings reported by the selected backend.
- Filter that list to resources that can be opened and respond to `*IDN?`.
- Verify basic communication by querying and parsing `*IDN?`.
- Detect 2000X, 3000X, and 4000X series models.
- Load conservative capability profiles.
- Read one or more entries from the system error queue with
  `:SYSTem:ERRor?`.
- Send basic acquisition control commands: `:STOP`, `:RUN`, and `:SINGle`.
- Enable, disable, or query analog channel display state with
  `:CHANnel<n>:DISPlay`.
- Provide hardware-free tests through `FakeBackend`.

The package does not send `*RST`, does not change VISA timeout defaults, and
does not perform return-to-local behavior. The Phase 2 control helpers only
send `:STOP`, `:RUN`, `:SINGle`, and system error queue queries.

No acquisition run-state query is currently exposed. `:RSTate?` timed out on
tested 4000X instruments and is not used by the CLI.

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

List VISA resource strings reported by the selected backend:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli list-resources
```

This is passive discovery only: a resource string can appear here even when the
instrument is not currently reachable.

List only resources that can be opened and queried with `*IDN?`:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli list-resources --live-only
```

This opens each listed resource and sends `*IDN?`. Resources that cannot be
opened or do not respond to `*IDN?` are omitted. Add `--log-scpi` to show the
verification query for each live check.

Verify that one resource can be opened and queried with `*IDN?`:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli verify --resource "USB0::...::INSTR"
```

Add `--log-scpi` to print the SCPI command log for manual hardware checks:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli verify --resource "USB0::...::INSTR" --log-scpi
```

For repeated hardware checks you can set:

```powershell
$env:KEYSIGHT_SCOPE_RESOURCE = "USB0::...::INSTR"
.\.venv\Scripts\python.exe -m keysight_scope.cli verify
```

Read one system error queue entry:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli check-error --resource "USB0::...::INSTR" --log-scpi
```

Drain the system error queue until no error is reported or the read limit is
hit:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli check-error --resource "USB0::...::INSTR" --all --log-scpi
```

Send basic acquisition control commands:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli stop --resource "USB0::...::INSTR" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli run --resource "USB0::...::INSTR" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli single --resource "USB0::...::INSTR" --log-scpi
```

The library methods `stop()`, `run()`, and `single()` each send only one SCPI
command. The CLI control commands additionally perform a transparent post-check
by querying one `:SYSTem:ERRor?` entry and printing the result. The
`:SYSTem:ERRor?` query removes the returned entry from the instrument error
queue.

Enable, disable, or query one analog channel display:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-display --resource "USB0::...::INSTR" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-display --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-display --resource "USB0::...::INSTR" --channel 1 --off --log-scpi
```

The `channel-display` command first queries `*IDN?` so the channel number can be
validated against the detected model before any channel display command is sent.
It prints the planned change or query, then performs one `:SYSTem:ERRor?`
post-check.

## Tests

Normal tests are hardware-free:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Real instrument checks are manual and should start with USB. See
`docs/hardware-test-plan.md`.

## Next Hardware Check

Phase 3 channel display control is implemented and covered by hardware-free
tests, but it has not been validated on a real oscilloscope yet.

Next time an instrument is connected over USB, run the Phase 3 channel-display
sequence in `docs/session-handoff.md` or `docs/hardware-test-plan.md`, then
record the model, resource string, full IDN, SCPI log, error queue result, and
whether LAN retest is requested.
