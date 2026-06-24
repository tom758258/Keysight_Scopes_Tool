# Keysight Scope CLI

Command-line adapter for safe communication with Keysight InfiniiVision
oscilloscopes through PyVISA.

Distribution: `keysight-scopes`

Console script: `keysight-scopes`

Module entry point: `python -m keysight_scope_cli.cli`

## Install For Development

From the repository root:

```powershell
uv pip install -e ".[all,dev]"
```

## Basic Usage

```powershell
keysight-scopes identify --simulate --json
python -m keysight_scope_cli.cli identify --simulate --json
```

Commands that accept instrument access support dry-run, simulate, and live
modes. Agents and automation should use dry-run and simulate before requesting
real hardware access. JSON payloads include `schema_version: 1` and
`timestamp_utc`.

Shared machine contracts remain at root:

- `docs/contracts/common-cli-jsonl-contract.md`
- `docs/contracts/scopes-cli-jsonl-contract.md`
- `docs/contracts/common-worker-protocol.md`
- `docs/contracts/scopes-worker-contract.md`
- `docs/contracts/common-orchestrator-workflows.md`
- `docs/contracts/scopes-orchestrator-workflows.md`

Package-local CLI integration notes remain in `docs/cli-integration.md`.

## Implemented Scope

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
- Query, hide, or configure manual cursors; set/query trigger holdoff; run
  explicit autoscale; save/recall setup slots or `.scp` files; and configure
  FFT math functions.
- Query read-only Vpp, frequency, period, display average voltage, display
  DC RMS voltage, minimum, maximum, rise time, fall time, amplitude, top, base,
  overshoot, preshoot, positive width, negative width, duty cycle, negative
  duty cycle, area, edge count, pulse count, parameterized time, phase, and
  safe 4000X delay measurements with explicit invalid-sentinel handling.
- Rebuild front-panel quick measurements and query measurement statistics with
  `measure-stats`.
- Collect read-only diagnostic snapshots with `doctor`.
- Query multi-channel and optional pair measurement sweeps with
  continue-and-summarize failure handling.
- Log a finite batch of read-only measurements with `measure-log`, writing a
  CSV, `manifest.json`, and `scpi.log` into one run directory.
- Run capture-safe hardware smoke checks that write a report directory with
  JSON, SCPI log, waveform CSV, metadata, and screenshot artifacts.
- Capture one or more analog channel waveforms in BYTE or WORD format and
  export CSV plus JSON metadata, with optional PNG plot output and an optional
  default timestamped CSV path under `data`.
- Capture a finite batch of waveforms with `capture-batch`, writing per-capture
  CSV and metadata files, `manifest.json`, and `scpi.log` into one run
  directory.
- Capture the current oscilloscope screen as a color PNG image, with an
  optional default timestamped output path under `data`.
- Provide hardware-free tests through `FakeBackend`.

The package does not send `*RST`, does not change VISA timeout defaults, and
does not perform return-to-local behavior. State-changing commands are exposed
only through explicit CLI commands; `doctor`, `smoke`, and `acquisition-check`
do not call the new cursor, holdoff, autoscale, setup, statistics, or FFT paths.

No acquisition run-state query is currently exposed. `:RSTate?` timed out on
tested 4000X instruments and is not used by the CLI.

## Development

From PowerShell, change into the project directory, create or reuse the local
virtual environment, install the package with development dependencies, then
run the default hardware-free tests:

```powershell
cd path\to\Keysight_Scopes
```

```powershell
uv venv .venv
```

```powershell
uv pip install -e ".[all,dev]"
```

This repository currently uses `uv` for the local virtual environment and
editable installs, but it is not configured as a `uv` workspace and does not
use a committed `uv.lock`. Do not commit a generated `uv.lock` unless the root
`pyproject.toml` is later changed to define an explicit uv workspace.

Run the repository test wrapper from the root directory:

```powershell
.\scripts\run-tests.ps1
```

This runs tests from all three areas: `tests/core`, `tests/cli`, and
`tests/webui`.

The wrapper creates an isolated pytest temporary directory, removes it after a
successful run, and preserves it after a failure for inspection. Additional
pytest arguments can be passed after the script path.

PyVISA will use the default VISA backend discovered on the computer. On the
instrument computer, the preferred backend is the installed Keysight IO
Libraries vendor VISA backend. `pyvisa-py` is a fallback for systems without a
usable vendor backend.

## Agent-safe Automation

Commands that accept instrument connections also accept `--json`, `--simulate`,
`--dry-run`, `--model`, and `--live`. Use `--dry-run --json` to validate
arguments and inspect planned SCPI without opening VISA or writing files. Use
`--simulate --json` to run against the deterministic hardware-free simulator;
capture workflows write fake output files for offline validation. JSON payloads
include `schema_version: 1` and `timestamp_utc`.

Simulator commands also accept presets, JSON scenarios, repeated signal
overrides, and error injection options, but only with `--simulate`.

```text
--simulate-preset noisy-sine
--simulate-scenario path\to\scenario.json
--simulate-signal CH:shape:frequency_hz:vpp_v:offset_v:phase_deg[:noise_rms_v]
--simulate-system-error -113
--simulate-binary-transfer-failure
--simulate-invalid-measurement CH2
--simulate-display-off CH1
```

`CH` may be `CH1` or `1`. Supported shapes are `sine`, `square`, `ramp`, `dc`,
and `noise`. Built-in presets are `noisy-sine`, `square-with-offset`,
`phase-shifted-pair`, `dc-invalid-frequency`, and `trigger-misaligned`.
Simulator configuration layers are applied in this order: built-in defaults,
`--simulate-preset`, `--simulate-scenario`, then explicit CLI overrides such as
`--simulate-signal` and error injection options. Scenario files are JSON only.

Agents should only access real hardware after explicit user approval. For a
one-shot command, an explicit `--resource "USB0::...::INSTR"` or
`KEYSIGHT_SCOPE_RESOURCE` opts in to that single live instrument. `--live`
remains accepted for one-shot compatibility, but is not required and cannot be
combined with `--simulate` or `--dry-run`. Live workers still require
`--live --resource`. SCPI debug logs from `--log-scpi` are written to stderr
and must not be parsed as JSON.

```powershell
uv run python -m keysight_scope_cli.cli identify --dry-run --json
uv run python -m keysight_scope_cli.cli identify --simulate --json
uv run python -m keysight_scope_cli.cli capture --simulate --json --simulate-preset phase-shifted-pair --channel 1 --channel 2 --csv .tmp_tests\preset.csv
uv run python -m keysight_scope_cli.cli measure --simulate --json --simulate-scenario path\to\scenario.json --channel 1 --item frequency
uv run python -m keysight_scope_cli.cli measure --simulate --json --simulate-signal CH1:square:1000:1.0:0:0:0.02 --channel 1 --item vpp
uv run python -m keysight_scope_cli.cli capture --simulate --json --simulate-binary-transfer-failure --channel 1 --csv .tmp_tests\failure.csv
uv run python -m keysight_scope_cli.cli capture-batch --simulate --json --channel 1 --count 2 --output-dir .tmp_tests\sim_batch
uv run python -m keysight_scope_cli.cli measure-log --simulate --json --channel 1 --items vpp,frequency --count 2 --output-dir .tmp_tests\sim_measure_log
```

Automation and orchestrator contracts live under `docs/contracts/`; start with
`docs/contracts/scopes-worker-contract.md`,
`docs/contracts/common-cli-jsonl-contract.md`,
`docs/contracts/scopes-cli-jsonl-contract.md`, and
`docs/contracts/scopes-orchestrator-workflows.md`. Keep dry-run or simulated
checks in front of live instrument access, and use an explicit operator-selected
resource for live commands.

## Commands

List VISA resource strings reported by the selected backend:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli list-resources
```

This is passive discovery only: a resource string can appear here even when the
instrument is not currently reachable.

List only resources that can be opened and queried with `*IDN?`:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli list-resources --live-only
```

This opens each listed resource and sends `*IDN?`. Resources that cannot be
opened or do not respond to `*IDN?` are omitted. Add `--log-scpi` to show the
verification query for each live check.

Verify that one resource can be opened and queried with `*IDN?`:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli identify --resource "USB0::...::INSTR"
```

Add `--log-scpi` to print the SCPI command log for manual hardware checks:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli identify --resource "USB0::...::INSTR" --log-scpi
```

For repeated hardware checks you can set:

```powershell
$env:KEYSIGHT_SCOPE_RESOURCE = "USB0::...::INSTR"
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli identify
```

Read one system error queue entry:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli check-error --resource "USB0::...::INSTR" --log-scpi
```

Drain the system error queue until no error is reported or the read limit is
hit:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli check-error --resource "USB0::...::INSTR" --all --log-scpi
```

Send basic acquisition control commands:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli stop-acquisition --resource "USB0::...::INSTR" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli run --resource "USB0::...::INSTR" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli single --resource "USB0::...::INSTR" --log-scpi
```

The library methods `stop()`, `run()`, and `single()` each send only one SCPI
command. The CLI control commands additionally perform a transparent post-check
by querying one `:SYSTem:ERRor?` entry and printing the result. The
`:SYSTem:ERRor?` query removes the returned entry from the instrument error
queue.

Configure or query acquisition type and average count:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "USB0::...::INSTR" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "USB0::...::INSTR" --type normal --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "USB0::...::INSTR" --type average --count 16 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "USB0::...::INSTR" --type high_resolution --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "USB0::...::INSTR" --type peak --log-scpi
```

The `acquisition` command first queries `*IDN?`, then sends only the requested
`:ACQuire:TYPE` and optional `:ACQuire:COUNt` commands before one
`:SYSTem:ERRor?` post-check. `--query` reads back both acquisition type and
average count. `--count` is only valid with average acquisition mode and must be
between 2 and 65536. Type aliases include `norm`, `aver`, `avg`,
`high-resolution`, `hresolution`, `hres`, `peak_detect`, and `peak-detect`.
This command does not change timeout defaults, trigger wait strategy,
acquisition mode, run/stop state, or return-to-local behavior.

Run the acquisition configuration validation workflow and write a report
directory:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition-check --dry-run --json --model DSOX4034A
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition-check --simulate --json --model DSOX4034A --output-dir .tmp_tests\acquisition_check
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition-check --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --json --log-scpi
```

`acquisition-check` runs the fixed validation sequence
`query -> normal -> average count 16 -> query -> high_resolution -> peak ->
final query`. It writes `report.json` and `scpi.log` under
`data/hardware_acquisition/YYYY-MM-DD-HH-mm-ss` unless `--output-dir` is
supplied. Use `--average-count N` to override the default count of 16. The
workflow intentionally leaves the instrument in `peak` acquisition mode after a
successful run so the command sequence stays explicit and avoids a hidden
restore write.

Enable, disable, or query one analog channel display:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-display --resource "USB0::...::INSTR" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-display --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-display --resource "USB0::...::INSTR" --channel 1 --off --log-scpi
```

The `channel-display` command first queries `*IDN?` so the channel number can be
validated against the detected model before any channel display command is sent.
It prints the planned change or query, then performs one `:SYSTem:ERRor?`
post-check. `--query` only reads back the current display state with
`:CHANnel<n>:DISPlay?`; it should not change the oscilloscope screen.

Set or query one analog channel vertical scale:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-scale --resource "USB0::...::INSTR" --channel 1 --volts-per-division 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-scale --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Set or query one analog channel vertical offset:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-offset --resource "USB0::...::INSTR" --channel 1 --volts 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-offset --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Scale must be a positive finite number in volts per division. Offset must be a
finite number in volts. These commands first query `*IDN?` to validate the
channel number against the detected model, then perform one
`:SYSTem:ERRor?` post-check.

Set or query one analog channel input coupling:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-coupling --resource "USB0::...::INSTR" --channel 1 --coupling dc --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-coupling --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Set or query one analog channel probe attenuation ratio:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-probe --resource "USB0::...::INSTR" --channel 1 --ratio 10 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-probe --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
```

Enable, disable, or query one analog channel bandwidth limit:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-bandwidth-limit --resource "USB0::...::INSTR" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-bandwidth-limit --resource "USB0::...::INSTR" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-bandwidth-limit --resource "USB0::...::INSTR" --channel 1 --off --log-scpi
```

Channel coupling supports `ac` and `dc`. Probe ratio must be a positive finite
number. Bandwidth limit is a per-channel on/off setting. These commands first
query `*IDN?` to validate the channel number against the detected model, then
perform one `:SYSTem:ERRor?` post-check.

Set or query the horizontal timebase scale:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-scale --resource "USB0::...::INSTR" --seconds-per-division 0.001 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-scale --resource "USB0::...::INSTR" --query --log-scpi
```

Set or query the horizontal timebase position:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-position --resource "USB0::...::INSTR" --seconds 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-position --resource "USB0::...::INSTR" --query --log-scpi
```

Timebase scale must be a positive finite number in seconds per division.
Timebase position must be a finite number in seconds. These commands first
query `*IDN?` to verify the connected scope model is recognized, then perform
one `:SYSTem:ERRor?` post-check.

Configure or query analog edge trigger source, level, and slope:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli edge-trigger --resource "USB0::...::INSTR" --source-channel 1 --level 0.25 --slope positive --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli edge-trigger --resource "USB0::...::INSTR" --query --log-scpi
```

The configure command sends `:TRIGger:MODE EDGE`, then sets source, level, and
slope. Supported slopes are `positive`, `negative`, `either`, and `alternate`.
Only analog channel sources are supported in this first trigger slice. Trigger
level must be a finite number in volts.

Query read-only measurements:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item vpp --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item frequency --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item period --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item vavg --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item vrms --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item ac_rms --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item minimum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item maximum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item x_at_max --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item x_at_min --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item rise_time --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item fall_time --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item amplitude --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item top --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item base --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item overshoot --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item preshoot --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item positive_width --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_width --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item duty_cycle --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_duty_cycle --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item area --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item positive_edges --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_edges --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item positive_pulses --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item negative_pulses --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item y_at_x --time 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item time_at_edge --slope positive --occurrence 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --channel 1 --item time_at_value --level 0.5 --slope positive --occurrence 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --source-channel 1 --reference-channel 2 --item phase --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "USB0::...::INSTR" --source-channel 1 --reference-channel 2 --item delay --log-scpi
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

Collect a read-only diagnostic snapshot:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli doctor --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --json --log-scpi
```

`doctor` queries `*IDN?`, backend and timeout metadata, acquisition type and
count, every analog channel's display, scale, offset, coupling, probe ratio,
and bandwidth limit, horizontal scale and position, and analog edge trigger
source, level, and slope. It performs one final `:SYSTem:ERRor?` post-check and
does not drain the full error queue.

Sweep common measurements across channels:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-sweep --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel all --items vpp,frequency,period,vrms --json --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-sweep --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel all --items vpp,frequency,period,vrms,rise_time,fall_time --pair 1:2 --pair-items phase,delay --json --log-scpi
```

`measure-sweep` defaults to `--channel all` and
`--items vpp,frequency,period,vrms`. Repeat `--channel` for explicit channels,
or add `--pair SRC:REF` with `--pair-items phase,delay` for pair measurements.
Each measurement record preserves validity, value, unit, raw response, reason,
SCPI command, and system error result. Invalid sentinels or per-item query
errors do not stop the sweep; the command returns non-zero after completing if
any invalid or error records were observed.

Log a finite batch of measurements:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-log --resource "USB0::...::INSTR" --channel 1 --items vpp,frequency --count 10 --interval-seconds 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-log --resource "USB0::...::INSTR" --channel 1 --channel 2 --items vpp,frequency --pair 1:2 --pair-items phase --count 5 --output-dir data\measure_logs\ch1_ch2 --log-scpi
```

`measure-log` is a finite read-only measurement logger. It requires `--count`
or `--duration-seconds` so an agent cannot accidentally start an unbounded
recorder. It defaults to `--channel all`, `--items vpp,frequency`,
`--pair-items phase,delay`, and `--interval-seconds 1.0`; pair measurements
run only when `--pair SRC:REF` is supplied. The command opens one session,
queries `*IDN?`, validates channels and measurement items, then writes
`measurements.csv`, `manifest.json`, and `scpi.log` under
`data/measure_logs/YYYY-MM-DD-HH-mm-ss` unless `--output-dir` is supplied.
The output directory must not exist or must be empty.

Each CSV row contains `timestamp_iso`, `elapsed_seconds`, one column per
requested measurement, and `NaN` for invalid measurement sentinels or per-item
query failures. One `:SYSTem:ERRor?` post-check is read after each row and
recorded in the manifest. With `--stop-on-error`, the command stops after the
row that reports an instrument error, leaves existing files in place, and
returns non-zero. It does not send `*RST`, change acquisition mode, wait for a
trigger, change timeout defaults, use background threads, or perform
return-to-local behavior.

Run a capture-safe smoke check:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli smoke --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --json --log-scpi
```

`smoke` writes `report.json`, `scpi.log`, `capture.csv`,
`capture_meta.json`, and `screen.png` under
`data/hardware_smoke/YYYY-MM-DD-HH-mm-ss`, appending `-2`, `-3`, and so on if a
default directory already exists. Use `--output-dir DIR` to choose a directory;
it must not exist or must be empty. The default flow runs a doctor snapshot,
queries CH1 `vpp` and `vrms`, captures CH1 BYTE waveform data at 1000 points,
captures a black-background screenshot, and performs a final system error
post-check. Invalid measurement sentinels are warnings; capture, screenshot,
backend, output, or system-error failures make the command return non-zero.

Capture waveform data:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel 1 --points 10000 --csv data\ch1.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --csv data\ch1.csv --plot data\ch1.png --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel 1 --points 1000 --format word --csv data\ch1_word.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel 1 --channel 2 --points 1000 --csv data\ch1_ch2.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel 1 --channel 2 --points 1000 --csv data\ch1_ch2.csv --allow-time-axis-tolerance --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "USB0::...::INSTR" --channel all --points 1000 --csv data\all_channels.csv --log-scpi
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
aligned CSV. For `capture` only, `--allow-time-axis-tolerance` keeps sample
count checks strict but allows a small multi-channel time-axis drift when every
non-canonical channel is within half of CH1's sample interval at every point
when CH1 is included. The CSV still writes only the canonical `time_s` axis; the
command does not interpolate or resample. Metadata and `--json` output include
the canonical channel, max allowed delta, and per-channel max observed delta
when the opt-in tolerance is enabled.
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
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture-batch --resource "USB0::...::INSTR" --channel 1 --points 1000 --format byte --count 3 --interval-seconds 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture-batch --resource "USB0::...::INSTR" --channel 1 --channel 2 --points 1000 --format word --count 2 --output-dir data\captures\ch1_ch2_batch --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture-batch --resource "USB0::...::INSTR" --channel all --points 1000 --count 2
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

Additional DSO-X 4024A controls:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli cursor --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli cursor --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --x1 0 --x2 1e-3 --y1 0 --y2 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-holdoff --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --seconds 1e-6 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-stats --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --items vpp,frequency --mode all --reset --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli autoscale --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --source-channel 2 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli setup-save --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --slot 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli setup-recall --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --file "\usb\setup.scp" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli fft --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --function 1 --source-channel 1 --units decibel --window hanning --center-hz 1000 --span-hz 10000 --display on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli fft --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --function 1 --source-channel 1 --display off --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli fft --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --function 1 --query --log-scpi
```

These commands are explicit user actions and are never called by `doctor`,
`smoke`, or `acquisition-check`. Some change front-panel state, such as cursor,
holdoff, autoscale, setup, FFT, and front-panel measurement statistics.

Phase 6A `capture-batch` intentionally does not change acquisition mode, wait
for a trigger, poll for acquisition completion, change VISA timeout defaults,
perform return-to-local behavior, start background threads, or run an infinite
recorder loop.

Capture the current oscilloscope screen as a color PNG image:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli screenshot --resource "USB0::...::INSTR" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli screenshot --resource "USB0::...::INSTR" --output data\screen.png --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli screenshot --resource "USB0::...::INSTR" --background white --log-scpi
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
.\scripts\run-tests.ps1
```

This runs tests from all three areas: `tests/core`, `tests/cli`, and
`tests/webui`.

For a filtered hardware-free run, pass pytest arguments after the script path:

```powershell
.\scripts\run-tests.ps1 tests/cli -q
```

Do not pass `--basetemp`; the wrapper creates an isolated pytest temporary
directory and preserves it only when the run fails.

Real instrument checks are manual. Start with `--dry-run --json`, then
`--simulate --json`, and only use an explicit `--resource <RESOURCE>` or
`KEYSIGHT_SCOPE_RESOURCE` after an operator selects the instrument. `--live`
may be included for one-shot compatibility and remains required for live
worker startup. Live checks should begin with USB communication verification
before running state-changing or artifact-writing commands.

## Hardware Validation

The public test baseline is the hardware-free pytest suite. Live hardware
validation is opt-in and should confirm representative workflows for the target
instrument model and transport:

- `identify` and `check-error` for communication and error-queue behavior.
- Read-only measurement and diagnostic commands before configuration changes.
- Channel, acquisition, timebase, trigger, setup, and autoscale commands only
  when changing instrument state is acceptable.
- Waveform, screenshot, smoke, batch capture, and measurement logging commands
  with explicit output paths.

Do not scan or rotate through resources inside an active live workflow. Use one
explicit resource selected by the operator for the whole workflow.
