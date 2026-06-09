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
- Set or query analog channel scale and offset with `:CHANnel<n>:SCALe` and
  `:CHANnel<n>:OFFSet`.
- Set or query horizontal timebase scale and position with `:TIMebase:SCALe`
  and `:TIMebase:POSition`.
- Configure or query analog edge trigger source, level, and slope with
  `:TRIGger:MODE EDGE` and `:TRIGger:EDGE:*`.
- Query read-only Vpp or frequency measurements for one analog channel with
  explicit invalid-sentinel handling.
- Capture one analog channel waveform in BYTE or WORD format and export CSV
  plus JSON metadata, with an optional default timestamped CSV path under
  `data`.
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
post-check. `--query` only reads back the current display state with
`:CHANnel<n>:DISPlay?`; it should not change the oscilloscope screen.

Set or query one analog channel vertical scale:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-scale --resource "USB0::...::INSTR" --channel 1 --volts-per-division 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-scale --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Set or query one analog channel vertical offset:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-offset --resource "USB0::...::INSTR" --channel 1 --volts 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-offset --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Scale must be a positive finite number in volts per division. Offset must be a
finite number in volts. These commands first query `*IDN?` to validate the
channel number against the detected model, then perform one
`:SYSTem:ERRor?` post-check.

Set or query the horizontal timebase scale:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli timebase-scale --resource "USB0::...::INSTR" --seconds-per-division 0.001 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli timebase-scale --resource "USB0::...::INSTR" --query --log-scpi
```

Set or query the horizontal timebase position:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli timebase-position --resource "USB0::...::INSTR" --seconds 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli timebase-position --resource "USB0::...::INSTR" --query --log-scpi
```

Timebase scale must be a positive finite number in seconds per division.
Timebase position must be a finite number in seconds. These commands first
query `*IDN?` to verify the connected scope model is recognized, then perform
one `:SYSTem:ERRor?` post-check.

Configure or query analog edge trigger source, level, and slope:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli edge-trigger --resource "USB0::...::INSTR" --source-channel 1 --level 0.25 --slope positive --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli edge-trigger --resource "USB0::...::INSTR" --query --log-scpi
```

The configure command sends `:TRIGger:MODE EDGE`, then sets source, level, and
slope. Supported slopes are `positive`, `negative`, `either`, and `alternate`.
Only analog channel sources are supported in this first trigger slice. Trigger
level must be a finite number in volts.

Query one read-only measurement:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item vpp --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item frequency --log-scpi
```

The first measurement slice supports `vpp` and `frequency`. The command first
queries `*IDN?`, validates the analog channel, sends one read-only measurement
query such as `:MEASure:VPP? CHANnel1`, and performs one
`:SYSTem:ERRor?` post-check. It does not change acquisition mode, trigger
settings, display state, VISA timeout, or return-to-local behavior. Invalid
measurement sentinels such as `9.9E+37` are printed as `Value: unavailable`
with `Valid: false` and the original raw response preserved; the CLI exits
non-zero so automation does not treat the unavailable value as usable data.

Capture one analog channel waveform:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --points 10000 --csv data\ch1.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --format word --csv data\ch1_word.csv --log-scpi
```

The current capture slice supports BYTE and WORD waveform formats with 1000,
5000, and 10000 requested points. BYTE remains the default. WORD capture sets
`:WAVeform:BYTeorder MSBFirst` and `:WAVeform:UNSigned ON` before reading data.
If `--csv` is omitted, the CLI writes to `data/YYYY-MM-DD-HH-mm-ss.csv` using
the `UTC+8` timezone. If `--csv PATH` is provided, it writes exactly to that
path. Metadata JSON defaults to the same stem with `_meta.json` beside the CSV.
The command performs one `:SYSTem:ERRor?` post-check. It does not change VISA
timeout, acquisition mode, trigger waiting, waveform point mode, or
return-to-local behavior. If the CSV or metadata file cannot be written because
it is open in another program or the folder is not writable, the CLI reports a
plain `error:` message instead of a Python traceback.

## Tests

Normal tests are hardware-free:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Real instrument checks are manual and should start with USB. See
`docs/hardware-test-plan.md`.

## Next Hardware Check

Phase 3 channel display control is implemented, covered by hardware-free tests,
and USB validated on DSO-X 4024A.

Channel scale and offset control is implemented and covered by hardware-free
tests, and USB validated on DSO-X 4024A.

Timebase scale and position control is implemented and covered by hardware-free
tests, and USB validated on DSO-X 4024A.

Analog edge trigger source, level, and slope control is implemented and covered
by hardware-free tests, and USB validated on DSO-X 4024A.

Single-channel BYTE waveform capture is implemented and covered by
hardware-free tests, and requested point counts 1000, 5000, and 10000 are USB
validated on DSO-X 4024A. The CLI now defaults `capture` output to a
timestamped CSV under `data` when `--csv` is omitted.

Single-channel WORD waveform capture is implemented and covered by
hardware-free tests, and requested point counts 1000, 5000, and 10000 are USB
validated on DSO-X 4024A.

Read-only Vpp and frequency measurement queries are implemented, covered by
hardware-free tests, and USB validated on DSO-X 4024A. LAN retest is deferred
until a LAN environment is available.
