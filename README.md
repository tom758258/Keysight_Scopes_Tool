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
- Configure or query acquisition type and average count with
  `:ACQuire:TYPE` and `:ACQuire:COUNt`.
- Enable, disable, or query analog channel display state with
  `:CHANnel<n>:DISPlay`.
- Set or query analog channel scale and offset with `:CHANnel<n>:SCALe` and
  `:CHANnel<n>:OFFSet`.
- Set or query analog channel coupling, probe ratio, and bandwidth limit with
  `:CHANnel<n>:COUPling`, `:CHANnel<n>:PROBe`, and
  `:CHANnel<n>:BWLimit`.
- Set or query horizontal timebase scale and position with `:TIMebase:SCALe`
  and `:TIMebase:POSition`.
- Configure or query analog edge trigger source, level, and slope with
  `:TRIGger:MODE EDGE` and `:TRIGger:EDGE:*`.
- Query read-only Vpp, frequency, period, display average voltage, display
  DC RMS voltage, minimum, maximum, rise time, fall time, amplitude, top, base,
  overshoot, preshoot, positive width, negative width, duty cycle, negative
  duty cycle, area, edge count, pulse count, parameterized time, phase, and
  safe 4000X delay measurements with explicit invalid-sentinel handling.
- Capture one or more analog channel waveforms in BYTE or WORD format and
  export CSV plus JSON metadata, with an optional default timestamped CSV path
  under `data`.
- Capture a finite batch of waveforms with `capture-batch`, writing per-capture
  CSV and metadata files, `manifest.json`, and `scpi.log` into one run
  directory.
- Capture the current oscilloscope screen as a color PNG image, with an
  optional default timestamped output path under `data`.
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

## Agent-safe Automation

Commands that accept instrument connections also accept `--json`, `--simulate`,
`--dry-run`, `--model`, and `--live`. Use `--dry-run --json` to validate
arguments and inspect planned SCPI without opening VISA or writing files. Use
`--simulate --json` to run against the deterministic hardware-free simulator;
capture workflows write fake output files for offline validation.

Agents should only access real hardware after explicit user approval, using
`--live --resource "USB0::...::INSTR" --json`. SCPI debug logs from
`--log-scpi` are written to stderr and must not be parsed as JSON.

```powershell
uv run python -m keysight_scope.cli verify --dry-run --json
uv run python -m keysight_scope.cli verify --simulate --json
uv run python -m keysight_scope.cli capture-batch --simulate --json --channel 1 --count 2 --output-dir .tmp_tests\sim_batch
```

See `docs/agent-integration-plan.md` for the full agent workflow and
restrictions.

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

Configure or query acquisition type and average count:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli acquisition --resource "USB0::...::INSTR" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli acquisition --resource "USB0::...::INSTR" --type normal --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli acquisition --resource "USB0::...::INSTR" --type average --count 16 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli acquisition --resource "USB0::...::INSTR" --type high_resolution --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli acquisition --resource "USB0::...::INSTR" --type peak --log-scpi
```

The `acquisition` command first queries `*IDN?`, then sends only the requested
`:ACQuire:TYPE` and optional `:ACQuire:COUNt` commands before one
`:SYSTem:ERRor?` post-check. `--query` reads back both acquisition type and
average count. `--count` is only valid with average acquisition mode and must be
between 2 and 65536. Type aliases include `norm`, `aver`, `avg`,
`high-resolution`, `hresolution`, `hres`, `peak_detect`, and `peak-detect`.
This command does not change timeout defaults, trigger wait strategy,
acquisition mode, run/stop state, or return-to-local behavior.

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

Set or query one analog channel input coupling:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-coupling --resource "USB0::...::INSTR" --channel 1 --coupling dc --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-coupling --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Set or query one analog channel probe attenuation ratio:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-probe --resource "USB0::...::INSTR" --channel 1 --ratio 10 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-probe --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Enable, disable, or query one analog channel bandwidth limit:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-bandwidth-limit --resource "USB0::...::INSTR" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-bandwidth-limit --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli channel-bandwidth-limit --resource "USB0::...::INSTR" --channel 1 --off --log-scpi
```

Channel coupling supports `ac` and `dc`. Probe ratio must be a positive finite
number. Bandwidth limit is a per-channel on/off setting. These commands first
query `*IDN?` to validate the channel number against the detected model, then
perform one `:SYSTem:ERRor?` post-check.

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

Query read-only measurements:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item vpp --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item frequency --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item period --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item vavg --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item vrms --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item ac_rms --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item minimum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item maximum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item x_at_max --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item x_at_min --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item rise_time --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item fall_time --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item amplitude --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item top --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item base --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item overshoot --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item preshoot --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item positive_width --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_width --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item duty_cycle --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_duty_cycle --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item area --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item positive_edges --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_edges --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item positive_pulses --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_pulses --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item y_at_x --time 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item time_at_edge --slope positive --occurrence 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --channel 1 --item time_at_value --level 0.5 --slope positive --occurrence 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --source-channel 1 --reference-channel 2 --item phase --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli measure --resource "USB0::...::INSTR" --source-channel 1 --reference-channel 2 --item delay --log-scpi
```

The current measurement slice supports `vpp`, `frequency` (`freq` alias),
`period`, `vavg`, `vrms`, `ac_rms` (`acrms` and `vrms_ac` aliases),
`minimum` (`min` and `vmin` aliases), `maximum` (`max` and `vmax` aliases),
`x_at_max` (`xmax` and `x-at-max` aliases), `x_at_min` (`xmin` and
`x-at-min` aliases), `rise_time` (`risetime` and `rise-time` aliases),
`fall_time` (`falltime` and `fall-time` aliases), `amplitude` (`vamp` alias),
`top` (`vtop` alias), `base` (`vbase` alias), `overshoot`, `preshoot`,
`positive_width` (`pwidth`, `positive-width`, and `pwid` aliases),
`negative_width` (`nwidth`, `negative-width`, and `nwid` aliases),
`duty_cycle` (`duty`, `dutycycle`, and `duty-cycle` aliases), and
`negative_duty_cycle` (`nduty`, `negative-duty`, and `negative-duty-cycle`
aliases), `area`, `positive_edges` (`pedges` and `positive-edges` aliases),
`negative_edges` (`nedges` and `negative-edges` aliases), `positive_pulses`
(`ppulses` and `positive-pulses` aliases), and `negative_pulses` (`npulses`
and `negative-pulses` aliases), plus parameterized single-channel queries:
`y_at_x` (`yatx`, `y-at-x`, `vtime`, `y_at_time`, and `y-at-time` aliases),
`time_at_edge` (`tedge` and `time-at-edge` aliases), and `time_at_value`
(`tvalue`, `time-at-value`, `time_at_level`, and `time-at-level` aliases),
plus two-channel `phase` and 4000X-only safe `delay`.
`y_at_x` requires `--time`; `time_at_value` requires `--level`;
`time_at_edge` and `time_at_value` accept `--slope positive|negative` and
`--occurrence N`, defaulting to positive occurrence 1. Two-channel items require
a source channel and reference channel; `--channel` remains a compatibility
alias for `--source-channel`, and cannot be combined with it. Single-channel
items reject `--reference-channel`. The command first queries `*IDN?`,
validates the analog channel or channel pair, sends one read-only measurement
query such as `:MEASure:VPP? CHANnel1`, and performs one `:SYSTem:ERRor?`
post-check. The added item queries are
`:MEASure:VRMS? DISPlay,AC,CHANnelN`, `:MEASure:XMAX? CHANnelN`,
`:MEASure:XMIN? CHANnelN`,
`:MEASure:VAMPlitude? CHANnelN`, `:MEASure:VTOP? CHANnelN`,
`:MEASure:VBASe? CHANnelN`, `:MEASure:OVERshoot? CHANnelN`,
`:MEASure:PREShoot? CHANnelN`, `:MEASure:PWIDth? CHANnelN`,
`:MEASure:NWIDth? CHANnelN`, `:MEASure:DUTYcycle? CHANnelN`,
`:MEASure:NDUTy? CHANnelN`, `:MEASure:AREA? CHANnelN`,
`:MEASure:PEDGes? CHANnelN`, `:MEASure:NEDGes? CHANnelN`,
`:MEASure:PPULses? CHANnelN`, `:MEASure:NPULses? CHANnelN`,
`:MEASure:VTIMe? <time>,CHANnelN`,
`:MEASure:TEDGe? +/-<occurrence>,CHANnelN`, and
`:MEASure:TVALue? <level>,+/-<occurrence>,CHANnelN`,
`:MEASure:PHASe? CHANnel<src>,CHANnel<ref>`, and
`:MEASure:DELay? AUTO,CHANnel<src>,CHANnel<ref>`. `delay` is intentionally
limited to 4000X models because the 2000X/3000X delay query depends on
`:MEASure:DEFine` state. It does not change acquisition mode, trigger settings,
measurement source, measurement window, display state, VISA timeout, or
return-to-local behavior.
Invalid measurement sentinels such as `9.9E+37` are printed as
`Value: unavailable` with `Valid: false` and the original raw response
preserved; the CLI exits non-zero so automation does not treat the unavailable
value as usable data.

Capture waveform data:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --points 10000 --csv data\ch1.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --format word --csv data\ch1_word.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel 1 --channel 2 --points 1000 --csv data\ch1_ch2.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture --resource "USB0::...::INSTR" --channel all --points 1000 --csv data\all_channels.csv --log-scpi
```

The current capture slice supports BYTE and WORD waveform formats with 1000,
5000, and 10000 requested points. BYTE remains the default. WORD capture sets
`:WAVeform:BYTeorder MSBFirst` and `:WAVeform:UNSigned ON` before reading data.
Repeat `--channel` to capture multiple analog channels sequentially in one
session. Use `--channel all` to capture every analog channel reported by the
detected model capability profile; this does not query or filter by displayed
channels. Multi-channel CSV output uses the first channel's `time_s` axis and
writes voltage columns in requested order, such as `time_s,ch1_v,ch2_v`.
`--channel all` cannot be combined with explicit channel numbers.
Duplicate channels and channels outside the detected model capabilities are
rejected before waveform SCPI is sent. If the captured channel time axes or
sample counts do not match, the command fails instead of writing a misleading
aligned CSV.
If `--csv` is omitted, the CLI writes to `data/YYYY-MM-DD-HH-mm-ss.csv` using
the `UTC+8` timezone. If `--csv PATH` is provided, it writes exactly to that
path. Metadata JSON defaults to the same stem with `_meta.json` beside the CSV.
Single-channel metadata keeps the existing top-level `channel` and
`actual_points` fields. Multi-channel metadata has top-level IDN, resource,
model, series, format, and requested point fields plus ordered `channels`
entries containing each channel number, actual point count, preamble, and WORD
byte-order fields where applicable.
The command performs one `:SYSTem:ERRor?` post-check. It does not change VISA
timeout, acquisition mode, trigger waiting, waveform point mode, or
return-to-local behavior. If the CSV or metadata file cannot be written because
it is open in another program or the folder is not writable, the CLI reports a
plain `error:` message instead of a Python traceback.

Capture a finite waveform batch:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli capture-batch --resource "USB0::...::INSTR" --channel 1 --points 1000 --format byte --count 3 --interval-seconds 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture-batch --resource "USB0::...::INSTR" --channel 1 --channel 2 --points 1000 --format word --count 2 --output-dir data\captures\ch1_ch2_batch --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli capture-batch --resource "USB0::...::INSTR" --channel all --points 1000 --count 2
```

`capture-batch` is a conservative finite batch capture command. `--count` is
required and must be a positive integer. `--interval-seconds` defaults to `0`
and must be a finite non-negative number; when non-zero, the sleep is applied
only between captures. The command opens one VISA session, queries `*IDN?`,
validates the detected capabilities, channels, point count, and waveform
format, then repeats the existing waveform capture APIs the requested number of
times. It performs one `:SYSTem:ERRor?` post-check after each capture.

If `--output-dir` is omitted, output is written under
`data/captures/YYYY-MM-DD-HH-mm-ss` using the `UTC+8` timezone. If that default
directory already exists, the CLI appends `-2`, `-3`, and so on to avoid
overwriting prior data. If `--output-dir DIR` is provided, `DIR` must not exist
or must be empty. This prevents new captures from being mixed with old files.

Each batch capture writes `waveform_0001.csv`,
`waveform_0001_meta.json`, and so on, using a sequence width of at least four
digits. The run directory also contains `manifest.json` with run parameters,
IDN fields, capture file paths, actual point counts, and system error results,
plus `scpi.log`. For `capture-batch`, `scpi.log` is always written; `--log-scpi`
additionally echoes the same package SCPI debug log to stderr for live hardware
checks.

If a post-capture system error is reported, the command leaves the already
written capture files and manifest in place, stops the remaining captures, and
returns non-zero. If interrupted from Python control flow, it writes a best
effort manifest with status `interrupted` and returns `130`.

Phase 6A `capture-batch` intentionally does not change acquisition mode, wait
for a trigger, poll for acquisition completion, change VISA timeout defaults,
perform return-to-local behavior, start background threads, or run an infinite
recorder loop.

Capture the current oscilloscope screen as a color PNG image:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope.cli screenshot --resource "USB0::...::INSTR" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli screenshot --resource "USB0::...::INSTR" --output data\screen.png --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope.cli screenshot --resource "USB0::...::INSTR" --background white --log-scpi
```

The `screenshot` command first queries `*IDN?`, sets `:HARDcopy:INKSaver` for
the requested image background, reads the current screen with
`:DISPlay:DATA? PNG, COLor`, restores the previous ink saver setting, and
performs one `:SYSTem:ERRor?` post-check. The default background is black,
matching the oscilloscope screen; `--background white` enables the inverted
white-background hardcopy style. If `--output` is omitted, the CLI writes to
`data/YYYY-MM-DD-HH-mm-ss.png` using the `UTC+8` timezone. The command validates
that the returned bytes have a PNG signature. Because screen images are larger
than normal query responses, screenshot capture temporarily sets the VISA
timeout to 10000 ms for the image transfer and restores the previous timeout
afterward. It does not change acquisition state, trigger settings, display
state, the default timeout, or return-to-local behavior.

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

Channel coupling, probe ratio, and bandwidth-limit control are implemented,
covered by hardware-free tests, and USB validated by user report on
.

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

Multi-channel BYTE and WORD waveform capture is implemented, covered by
hardware-free tests, and USB validated by user report on .

Finite `capture-batch` waveform capture is implemented and covered by
hardware-free tests. USB hardware validation remains pending for Phase 6A.

Read-only Vpp, frequency, period, display average voltage, and display DC RMS
voltage measurement queries are implemented, covered by hardware-free tests, and
USB validated on DSO-X 4024A. Read-only minimum, maximum, rise time, and fall
time measurement queries are implemented and covered by hardware-free tests;
USB validation passed by user report on . Read-only amplitude, top,
base, overshoot, preshoot, positive width, negative width, duty cycle, and
negative duty cycle measurement queries are implemented and covered by
hardware-free tests; USB CH1 validation passed by user report on .
Read-only area measurement query is implemented and covered by hardware-free
tests; USB CH1 validation passed by user report on . Read-only AC
RMS, X-at-max, X-at-min, edge count, and pulse count measurement queries are
implemented and covered by hardware-free tests; USB CH1 validation passed by
user report on . Read-only parameterized single-channel y-at-x,
time-at-edge, and time-at-value measurement queries are implemented and covered
by hardware-free tests; USB CH1 validation passed by user report on 2026-05-14.
LAN retest is deferred until a LAN environment is available.

Screenshot PNG capture is implemented and covered by hardware-free tests. USB
hardware validation passed by user report on .
