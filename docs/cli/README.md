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
- Load runtime-supported capability profiles.
- Read one or more entries from the system error queue with
  `:SYSTem:ERRor?`.
- Send basic acquisition control commands: `:STOP`, `:RUN`, and `:SINGle`.
- Configure or query acquisition type and average count with
  `:ACQuire:TYPE` and `:ACQuire:COUNt`.
- Query the current analog acquisition sample rate in Hz with
  `:ACQuire:SRATe?`.
- Query the current analog acquisition points with `:ACQuire:POINts?`.
  This command is read-only and separate from waveform transfer point count
  controlled by `capture --points`.
- Query the current analog acquisition record length with `:ACQuire:RLENgth?`.
  This command is read-only and separate from acquisition points and waveform
  transfer point count controlled by `capture --points`.
- Enable, disable, or query analog channel display state with
  `:CHANnel<n>:DISPlay`.
- Set or query analog channel labels with `:CHANnel<n>:LABel`. 2000X/3000X
  profiles allow up to 10 printable ASCII characters; 4000X profiles allow up
  to 32. Text is sent as supplied and is not uppercased or truncated.
- Set or query analog channel scale and offset with `:CHANnel<n>:SCALe` and
  `:CHANnel<n>:OFFSet`.
- Set or query analog channel coupling, probe ratio, and bandwidth limit with
  `:CHANnel<n>:COUPling`, `:CHANnel<n>:PROBe`, and
  `:CHANnel<n>:BWLimit`.
- Set or query analog channel impedance, invert, full-scale range, units,
  vernier, and probe skew with `:CHANnel<n>:IMPedance`,
  `:CHANnel<n>:INVert`, `:CHANnel<n>:RANGe`, `:CHANnel<n>:UNITs`,
  `:CHANnel<n>:VERNier`, and `:CHANnel<n>:PROBe:SKEW`.
- Set or query horizontal timebase scale and position with `:TIMebase:SCALe`
  and `:TIMebase:POSition`.
- Configure or query analog edge trigger source, level, and slope with
  `:TRIGger:MODE EDGE` and `:TRIGger:EDGE:*`.
- Configure or query common trigger sweep, noise reject, and high-frequency
  reject settings with `:TRIGger:SWEep`, `:TRIGger:NREJect`, and
  `:TRIGger:HFReject`.
- Configure or query analog-channel pulse-width trigger settings with
  `:TRIGger:MODE GLITch` and `:TRIGger:GLITch:*`.
- Configure or query analog-channel runt trigger settings with
  `:TRIGger:MODE RUNT`, `:TRIGger:RUNT:*`, and shared
  `:TRIGger:LEVel:LOW/HIGH` threshold commands.
- Configure or query analog-channel transition trigger settings with
  `:TRIGger:MODE TRANsition`, `:TRIGger:TRANsition:*`, and shared
  `:TRIGger:LEVel:LOW/HIGH` threshold commands.
- Configure or query DSO analog-channel Edge Then Edge / Delay trigger
  settings with `:TRIGger:MODE DELay` and `:TRIGger:DELay:*`.
- Configure or query DSO analog-channel setup-hold trigger settings with
  `:TRIGger:MODE SHOLd` and `:TRIGger:SHOLd:*`.
- Configure or query DSO analog-channel Nth Edge Burst trigger settings with
  `:TRIGger:MODE EBURst`, `:TRIGger:EBURst:*`, and optional source-qualified
  `:TRIGger:EDGE:LEVel`.
- Configure or query DSO analog-channel basic TV / video trigger settings with
  `:TRIGger:MODE TV` and `:TRIGger:TV:*`.
- Configure or query DSO analog ASCII pattern trigger settings with
  `:TRIGger:MODE PATTern`, `:TRIGger:PATTern:FORMat ASCii`,
  `:TRIGger:PATTern "<pattern>"`, and
  `:TRIGger:PATTern:QUALifier ENTered`.
- Configure or query DSO analog-only OR trigger settings with
  `:TRIGger:MODE OR` and `:TRIGger:OR "<pattern>"`. Pattern order follows
  Keysight OR trigger bit assignment: CH4, CH3, CH2, CH1 on 4-channel DSO
  models and CH2, CH1 on 2-channel DSO models.
- Enable, disable, or query display labels with `:DISPlay:LABel`; clear
  waveform display data with `:DISPlay:CLEar`; set/query display persistence,
  waveform intensity, and vector display with `:DISPlay:PERSistence`,
  `:DISPlay:INTensity:WAVeform`, and `:DISPlay:VECTors`; set, clear, or query
  display annotations with `:DISPlay:ANNotation`. 4000X annotation commands use
  indexed slots `1..10` and support `X1Position`/`Y1Position`.
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
  export CSV plus JSON metadata, with optional PNG plot output, an optional
  default timestamped CSV path under `data`, and optional explicit triggered
  capture via `capture --wait-trigger`.
- Capture a finite batch of waveforms with `capture-batch`, writing per-capture
  CSV and metadata files, `manifest.json`, and `scpi.log` into one run
  directory.
- Capture the current oscilloscope screen as a color PNG image, with an
  optional default timestamped output path under `data`.
- Provide hardware-free tests through `FakeBackend`.
- Force one trigger event explicitly with `force-trigger` / `:TRIGger:FORCe`,
  without changing the standalone `single` or default `capture` behavior.

The package does not send `*RST`, does not change VISA timeout defaults, and
does not perform return-to-local behavior. State-changing commands are exposed
only through explicit CLI commands; `doctor`, `smoke`, and `acquisition-check`
do not call the new cursor, holdoff, autoscale, setup, statistics, or FFT paths.

No acquisition run-state query is currently exposed. `:RSTate?` timed out on
the DSO-X 4024A used for validation and is not used by the CLI.

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
`--dry-run`, `--model`, and `--live`. Use `--dry-run` to validate arguments and
inspect planned SCPI without opening VISA or writing files; add `--json` when
automation needs the machine-readable payload. Use `--simulate --json` to run
against the deterministic hardware-free simulator; capture workflows write fake
output files for offline validation. JSON payloads include `schema_version: 1`
and `timestamp_utc`.

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
one-shot command, an explicit `--resource <RESOURCE>` or
`KEYSIGHT_SCOPE_RESOURCE` opts in to that single live instrument. `--live`
remains accepted for one-shot compatibility, but is not required and cannot be
combined with `--simulate` or `--dry-run`. Live workers still require
`--live --resource`. SCPI debug logs from `--log-scpi` are written to stderr
and must not be parsed as JSON.

```powershell
uv run python -m keysight_scope_cli.cli identify --dry-run --json
uv run python -m keysight_scope_cli.cli identify --simulate --json
uv run python -m keysight_scope_cli.cli acquisition-points --query --dry-run --json --model DSOX4024A
uv run python -m keysight_scope_cli.cli acquisition-points --query --simulate --json --model DSOX4024A
uv run python -m keysight_scope_cli.cli record-length --query --simulate --json --model DSOX4024A
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
instrument is not currently reachable. Plain `list-resources` does not open
the listed resources or send SCPI.

List only resources that can be opened and queried with `*IDN?`:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli list-resources --live-only
```

This opens each listed resource and sends `*IDN?`. Resources that cannot be
opened or do not respond to `*IDN?` are omitted. Add `--log-scpi` to show the
verification query for each live check.

ASRL/RS-232 live checks use a bounded best-effort discovery path with a 1000 ms
open/query timeout so a stale serial port does not prevent later USB or TCPIP
resources from being checked. This compatibility check is only for live
discovery and does not mean the Scope runtime supports full RS-232 acquisition
or control workflows.

For ASRL live discovery only, serial termination can be set when needed for a
specific adapter or instrument:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli list-resources --live-only --serial-read-termination CRLF --serial-write-termination NONE
```

Supported values are `CRLF`, `LF`, `CR`, and `NONE`. Omitted options leave the
PyVISA session attributes unchanged; explicit `NONE` sets the corresponding
termination attribute to `None`.

Set the operator-selected live resource once in the current PowerShell session:

```powershell
$env:KEYSIGHT_SCOPE_RESOURCE = "USB0::...::INSTR"
```

The remaining live examples assume this environment variable is set. Replace
the placeholder with the resource string selected by the operator.

Verify that one resource can be opened and queried with `*IDN?`:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli identify --resource "$env:KEYSIGHT_SCOPE_RESOURCE"
```

Add `--log-scpi` to print the SCPI command log for manual hardware checks:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli identify --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
```

Read one system error queue entry:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli check-error --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
```

Drain the system error queue until no error is reported or the read limit is
hit:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli check-error --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --all --log-scpi
```

Send basic acquisition control commands:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli stop-acquisition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli run --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli single --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
```

The library methods `stop()`, `run()`, and `single()` each send only one SCPI
command. The CLI control commands additionally perform a transparent post-check
by querying one `:SYSTem:ERRor?` entry and printing the result. The
`:SYSTem:ERRor?` query removes the returned entry from the instrument error

Force one trigger event explicitly:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli force-trigger --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli force-trigger --dry-run --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli force-trigger --simulate --json --log-scpi
```

`force-trigger` is an explicit state-changing one-shot action. It first
queries `*IDN?`, then sends `:TRIGger:FORCe`, then performs one `:SYSTem:ERRor?`
post-check. It does not arm a single acquisition, does not wait for trigger
or acquisition completion, does not capture waveform data, and does not
change timebase, acquisition points, record length, acquisition mode,
sample-rate mode, waveform
points, waveform format, display state, VISA timeout, trigger source, trigger
level, trigger slope, trigger sweep, or return-to-local behavior. `force-trigger`
must not be combined with `capture`, `measure`, `doctor`, `smoke`,
`acquisition-check`, `single`, `run`, `stop-acquisition`, `autoscale`,
`setup-save`, or `setup-recall`. Worker `/command` support is available only
through the explicit `force-trigger` command with `arguments: {}`.
Triggered capture integration is available only through explicit
`capture --wait-trigger` options; the standalone `force-trigger` command
remains unchanged.

The long trigger force form is used for DSO-X 4000X firmware 07.20
compatibility.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command force-trigger --arguments-json "{}" --json
```

Configure or query acquisition type and average count:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --type normal --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --type average --count 16 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --type high_resolution --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --type peak --log-scpi
```

The `acquisition` command first queries `*IDN?`, then sends only the requested
`:ACQuire:TYPE` and optional `:ACQuire:COUNt` commands before one
`:SYSTem:ERRor?` post-check. `--query` reads back both acquisition type and
average count. `--count` is only valid with average acquisition mode and must be
between 2 and 65536. Type aliases include `norm`, `aver`, `avg`,
`high-resolution`, `hresolution`, `hres`, `peak_detect`, and `peak-detect`.
This command does not change timeout defaults, trigger wait strategy,
acquisition mode, run/stop state, or return-to-local behavior.

Query the current analog acquisition sample rate:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli sample-rate --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

Query the maximum analog acquisition sample rate:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli sample-rate --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --maximum --log-scpi
```

The `sample-rate` command is query-only and requires `--query`. It first
queries `*IDN?`, then sends `:ACQuire:SRATe?` for the current sample rate or
`:ACQuire:SRATe? MAXimum` when `--maximum` is supplied, and performs one
`:SYSTem:ERRor?` post-check. The response is parsed as an NR3 number and
reported in Hz together with the raw readback. Maximum queries report
`query_kind: "maximum"` and `maximum_sample_rate_hz` in JSON. This command does
not change timebase, acquisition points, record length, acquisition mode,
sample-rate auto/manual mode, waveform points, trigger settings, VISA timeout,
or return-to-local
behavior. The short query forms are used for DSO-X 4000X firmware 07.20
compatibility.

Worker usage requires the same query-only intent:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command sample-rate --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command sample-rate --arguments-json "{\"query\":true,\"maximum\":true}" --json
```

Query the current analog acquisition points:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli acquisition-points --query --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
```

The `acquisition-points` command is query-only and requires `--query`. It first
queries `*IDN?`, then sends `:ACQuire:POINts?` and performs one
`:SYSTem:ERRor?` post-check. The response is parsed as an integer
representing the current analog acquisition points, together with the raw
readback. It does not configure acquisition points, record length, acquisition
mode, timebase, sample-rate, trigger settings, waveform format, waveform
points, VISA timeout, or return-to-local behavior. `acquisition-points --query`
is separate from `capture --points`, which controls waveform transfer point
count.

Worker usage requires the same query-only intent:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command acquisition-points --arguments-json "{\"query\":true}" --json
```

Query the current analog acquisition record length:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli record-length --query --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
```

The `record-length` command is query-only and requires `--query`. It first
queries `*IDN?`, then sends `:ACQuire:RLENgth?` and performs one
`:SYSTem:ERRor?` post-check. The response is parsed as an integer
representing the current analog acquisition record length, together with the
raw readback. It does not configure record length, acquisition points,
acquisition mode, timebase, sample-rate, trigger settings, waveform format,
waveform points, VISA timeout, or return-to-local behavior.
`record-length --query` is separate from `capture --points`, which controls
waveform transfer point count.

Worker usage requires the same query-only intent:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command record-length --arguments-json "{\"query\":true}" --json
```

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
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-display --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-display --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-display --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --off --log-scpi
```

The `channel-display` command first queries `*IDN?` so the channel number can be
validated against the detected model before any channel display command is sent.
It prints the planned change or query, then performs one `:SYSTem:ERRor?`
post-check. `--query` only reads back the current display state with
`:CHANnel<n>:DISPlay?`; it should not change the oscilloscope screen.

Set or query one analog channel vertical scale:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-scale --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --volts-per-division 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-scale --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
```

Set or query one analog channel vertical offset:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-offset --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --volts 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-offset --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
```

Scale must be a positive finite number in volts per division. Offset must be a
finite number in volts. These commands first query `*IDN?` to validate the
channel number against the detected model, then perform one
`:SYSTem:ERRor?` post-check.

Set or query one analog channel input coupling:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-coupling --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --coupling dc --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-coupling --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
```

Set or query one analog channel probe attenuation ratio:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-probe --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --ratio 10 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-probe --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
```

Enable, disable, or query one analog channel bandwidth limit:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-bandwidth-limit --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-bandwidth-limit --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-bandwidth-limit --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --off --log-scpi
```

Channel coupling supports `ac` and `dc`. Probe ratio must be a positive finite
number. Bandwidth limit is a per-channel on/off setting. These commands first
query `*IDN?` to validate the channel number against the detected model, then
perform one `:SYSTem:ERRor?` post-check.

Set or query additional analog channel settings:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-impedance --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --impedance one-meg --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-impedance --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --impedance fifty --allow-50-ohm --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-impedance --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-invert --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-invert --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-range --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --volts-full-scale 4 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-range --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-units --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --units volt --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-units --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-vernier --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --off --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-vernier --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-probe-skew --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --seconds 1e-9 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-probe-skew --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
```

These commands first query `*IDN?`, validate the channel number against the
detected model, send only the requested command or query, and then perform one
`:SYSTem:ERRor?` post-check. `channel-range --volts-full-scale` must be positive and
finite. `channel-probe-skew --seconds` must be finite and within
`-100e-9..100e-9`. Units are `volt` or `amp`; impedance is `one-meg` or
`fifty`. Setting `fifty` requires `--allow-50-ohm` before any backend is
opened. In this CLI, 50 ohm channel impedance is supported only on DSO-X 3000X
and 4000X profiles. DSO-X 2000X channel impedance is one-meg only; even with
`--allow-50-ohm`, a detected 2000X is rejected after `*IDN?` and before
`:CHANnel<n>:IMPedance FIFTy`.

Worker `/command` accepts these advanced channel commands using the same option
names as JSON keys without leading dashes. For example, `channel-range` uses
`volts_full_scale`, not `volts`.

Set or query one analog channel label:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-label --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --text "Input A" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli channel-label --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --query --log-scpi
```

Channel labels accept printable ASCII text without double quotes or control
characters. The CLI validates model-specific length before sending SCPI:
2000X/3000X allow up to 10 characters, and 4000X allows up to 32. Some
instruments may normalize returned label case; JSON reports the query readback
as returned by SCPI parsing.

Enable, disable, or query front-panel label display:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-label --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-label --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

Run common display one-shot commands:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-clear --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-persistence --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --mode minimum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-persistence --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --seconds 1.0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-persistence --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-intensity --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --value 75 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-intensity --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-vectors --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --on --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli display-vectors --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

These commands first query `*IDN?`, then send the target display command or
query, then perform one `:SYSTem:ERRor?` post-check. `display-clear` clears
waveform display data and resets associated measurements. Display persistence
accepts `minimum`, `infinite`, or finite seconds from `0.1` through `60.0`.
Waveform intensity accepts integer values from `0` through `100`.
`display-vectors` supports query and setting ON only; setting OFF is not part
of this common v1 surface. `display-persistence-clear` is intentionally not
implemented in this common pack; it may be considered later as a separately
guarded 2000X-only command with its own validation plan.

Set, clear, or query display annotations:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli annotation --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --on --text "Run note" --color white --background opaque --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli annotation --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli annotation --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --model DSOX4024A --slot 2 --text "Run note" --x 10 --y 20 --log-scpi
```

`annotation --query` cannot be combined with setters. Non-query annotation
commands require at least one setter/action. `--clear` sends an empty annotation
text string and cannot be combined with `--text`. 2000X/3000X annotation uses
the unindexed `:DISPlay:ANNotation` commands and does not send or query X/Y
position; JSON query results still include `x: null` and `y: null`. 4000X uses
indexed `:DISPlay:ANNotation<n>` slots from 1 through 10 and validates `--x`
as 0 through 800 and `--y` as 0 through 480 before sending
`:X1Position`/`:Y1Position` SCPI. Annotation background values are `opaque`,
`inverted`, and `transparent`; annotation color values are `ch1`, `ch2`,
`ch3`, `ch4`, `dig`, `math`, `ref`, `marker`, `white`, and `red`.
Annotation text accepts printable ASCII text up to 254 characters and must not
contain double quotes or control characters.
Annotation value forms are distinct:

- CLI input aliases: `white`, `marker`, and `transparent`.
- SCPI command tokens: `WHITE`, `MARKer`, and `OPAQ`.
- Query canonical enums: `WHITE`, `MARK`, `DIG`, `OPAQ`, and `TRAN`.

Annotation query results preserve instrument semantics using canonical SCPI
enum values. Color readback abbreviations such as `WHIT` are accepted and
normalized to stable canonical values such as `WHITE`; background readback
canonical values remain `OPAQ`, `INV`, and `TRAN`.

These one-shot commands are also accepted by the worker `/command` interface
using the same argument names as the CLI options without leading dashes.

Set or query the horizontal timebase scale:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-scale --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --seconds-per-division 0.001 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-scale --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

Set or query the horizontal timebase position:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-position --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --seconds 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli timebase-position --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

Timebase scale must be a positive finite number in seconds per division.
Timebase position must be a finite number in seconds. These commands first
query `*IDN?` to verify the connected scope model is recognized, then perform
one `:SYSTem:ERRor?` post-check.

Configure or query analog edge trigger source, level, and slope with the
canonical `trigger-edge` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --level 0.25 --slope positive --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge --dry-run --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge --simulate --json --model DSOX4024A --source-channel 1 --level 0.5 --slope positive
```

The configure command sends `:TRIGger:MODE EDGE`, then sets source, level, and
slope. Supported slopes are `positive`, `negative`, `either`, and `alternate`.
Only DSO analog channel sources are supported. Trigger level must be a finite
number in volts. External trigger, digital/MSO source, trigger coupling/reject,
and broader trigger-tree expansion are not included. The old `edge-trigger`
command name is not accepted.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-edge --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-edge --arguments-json "{\"source_channel\":1,\"level\":0.5,\"slope\":\"positive\"}" --json
```

Worker JSON for `trigger-edge` accepts only `query`, `source_channel`,
`level`, and `slope`. Aliases and unknown fields are rejected before enqueue,
artifact creation, simulator/VISA session open, or SCPI.

Configure or query common trigger general settings:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-sweep --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-sweep --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --mode auto --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-sweep --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --mode normal --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-noise-reject --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-noise-reject --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --enabled true --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-noise-reject --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --enabled false --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-hf-reject --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-hf-reject --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --enabled true --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-hf-reject --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --enabled false --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-sweep --dry-run --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-noise-reject --simulate --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-hf-reject --simulate --json --model DSOX4024A --enabled true
```

`trigger-sweep` uses `:TRIGger:SWEep` and accepts only `--mode auto` or
`--mode normal`. Query mode sends `:TRIGger:SWEep?` and reports normalized
`mode` plus `raw_value` in JSON. `trigger-noise-reject` uses
`:TRIGger:NREJect`; `trigger-hf-reject` uses `:TRIGger:HFReject`. Both reject
commands accept only `--enabled true` or `--enabled false`; query mode
normalizes `0`/`1` readback to boolean `enabled` and preserves `raw_value`.
Each command rejects `--query` combined with configure options and rejects
missing configure options when not querying.

These commands are explicit one-shot state changes or queries. They do not
change trigger holdoff, do not add generic trigger settings APIs, do not run,
stop, single, force trigger, wait for trigger, capture waveform data, or change
WebUI runtime behavior. This v1 package has hardware-free CLI/Core/simulator
and worker validation only; live CLI, worker live, LAN, WebUI runtime, DSO-X
2000X/3000X/4024A/4034A live validation, and prior trigger pack live status
changes have not been run or made. Phase 10 `trigger-edge` live validation
remains pending and is not abandoned.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-sweep --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-sweep --arguments-json "{\"mode\":\"normal\"}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-noise-reject --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-noise-reject --arguments-json "{\"enabled\":false}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-hf-reject --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-hf-reject --arguments-json "{\"enabled\":true}" --json
```

Worker JSON for `trigger-sweep` accepts only `query` or `mode`. Worker JSON for
`trigger-noise-reject` and `trigger-hf-reject` accepts only `query` or
`enabled`. `query` must be exactly JSON `true`; `enabled` must be a JSON
boolean. Unknown fields and aliases such as `sweep`, `sweep_mode`,
`trigger_sweep`, `noise_reject`, `nreject`, `nrej`, `state`, `on`, `enable`,
`hf_reject`, `hfreject`, and `high_frequency_reject` are rejected before
enqueue, artifact creation, simulator/VISA session open, or SCPI.

Configure or query Keysight pulse-width trigger settings with the canonical
`trigger-pulse-width` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pulse-width --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --polarity positive --qualifier less-than --time-seconds 1e-6 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pulse-width --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --polarity negative --qualifier greater-than --time-seconds 5e-6 --level-volts 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pulse-width --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --polarity positive --qualifier range --min-time-seconds 1e-6 --max-time-seconds 10e-6 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pulse-width --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

`trigger-pulse-width` configures and queries the Keysight Pulse Width trigger
using the underlying `:TRIGger:GLITch...` SCPI family. Configure mode is
state-changing: it selects Pulse Width trigger mode, sets an analog source
channel, optionally sets the trigger level, then sets
polarity and the selected pulse-width qualifier. Range configure maps
`--max-time-seconds` to the first SCPI `RANGe` parameter and
`--min-time-seconds` to the second parameter. Query mode preserves raw source
and level responses and tolerates current instrument state such as digital,
external, or `NONE` source readback.

This slice is analog-channel-only for configure mode. It does not run, stop,
single, force trigger, wait for a trigger, capture waveform data, or implement
pattern, delay, TV, USB, serial bus, digital/MSO, zone, or other trigger types.
Hardware-free tests cover this command; broader live validation remains opt-in
and model/transport-specific.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-pulse-width --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-pulse-width --arguments-json "{\"channel\":1,\"polarity\":\"positive\",\"qualifier\":\"less_than\",\"time_seconds\":0.000001}" --json
```

Configure or query analog runt trigger settings with the canonical
`trigger-runt` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-runt --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --polarity either --qualifier none --low-level-volts -0.5 --high-level-volts 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-runt --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --polarity positive --qualifier greater-than --time-seconds 5e-6 --low-level-volts -0.25 --high-level-volts 0.75 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-runt --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

`trigger-runt` configures and queries the Keysight Runt trigger using
`:TRIGger:MODE RUNT`, `:TRIGger:RUNT:*`, and shared
`:TRIGger:LEVel:LOW/HIGH` threshold commands. Configure mode is
state-changing: it selects Runt trigger mode, sets an analog source channel,
sets low and high analog thresholds, then sets polarity and qualifier. The
qualifier is `greater-than`, `less-than`, or `none`; only the timed qualifiers
send `:TRIGger:RUNT:TIME`. `none` rejects `--time-seconds`. Query mode reads
mode, source, polarity, qualifier, and stored runt time first, then reads
LOW/HIGH levels only when the source readback safely parses as an analog
`CHAN<n>` or `CHANnel<n>` source. Non-analog or unrecognized source readbacks
are preserved in JSON with `channel`, `low_level_volts`, and
`high_level_volts` set to `null`.

This slice is analog-channel-only for configure mode. It does not run, stop,
single, force trigger, wait for a trigger, capture waveform data, or implement
generic trigger configuration, transition, pattern, search, wait, force,
run/stop, capture, waveform, or WebUI runtime behavior. Hardware-free tests
cover the CLI, Core, simulator, and worker paths; live hardware validation has
not been run for `trigger-runt`.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-runt --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-runt --arguments-json "{\"channel\":1,\"polarity\":\"either\",\"qualifier\":\"none\",\"low_level_volts\":-0.5,\"high_level_volts\":0.5}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-runt --arguments-json "{\"channel\":1,\"polarity\":\"positive\",\"qualifier\":\"greater_than\",\"time_seconds\":0.000005,\"low_level_volts\":-0.25,\"high_level_volts\":0.75}" --json
```

Configure or query analog transition trigger settings with the canonical
`trigger-transition` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-transition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --slope positive --qualifier greater-than --time-seconds 5e-6 --low-level-volts -0.5 --high-level-volts 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-transition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --slope negative --qualifier less-than --time-seconds 2e-6 --low-level-volts -0.25 --high-level-volts 0.75 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-transition --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
```

`trigger-transition` configures and queries the Keysight Transition trigger
using `:TRIGger:MODE TRANsition`, `:TRIGger:TRANsition:*`, and shared
`:TRIGger:LEVel:LOW/HIGH` threshold commands. Configure mode is
state-changing: it selects Transition trigger mode, sets an analog source
channel, sets low and high analog thresholds, then sets slope, time, and
qualifier. The slope is `positive` or `negative`; the qualifier is
`greater-than` or `less-than`; `--time-seconds`, `--low-level-volts`, and
`--high-level-volts` are required, and low must be less than high.

Query mode reads mode, source, slope, qualifier, and transition time first,
then reads LOW/HIGH levels only when the source readback safely parses as an
analog `CHAN<n>` or `CHANnel<n>` source. Non-analog or unrecognized source
readbacks are preserved in JSON with `channel`, `low_level_volts`, and
`high_level_volts` set to `null`.

This v1 slice is analog-channel-only for configure mode. It does not configure
digital/MSO or external transition sources, add aliases, run, stop, single,
force trigger, wait for a trigger, capture waveform data, or implement generic
trigger-tree behavior. Hardware-free tests cover the CLI, Core, simulator, and
worker paths. Live CLI validation, worker live validation, LAN validation,
WebUI validation, DSO-X 2000X/3000X/4024A/4034A live validation, digital/MSO
source validation, and broader trigger-tree validation have not been run.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-transition --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-transition --arguments-json "{\"channel\":1,\"slope\":\"positive\",\"qualifier\":\"greater_than\",\"time_seconds\":0.000005,\"low_level_volts\":-0.5,\"high_level_volts\":0.5}" --json
```

Configure or query analog-channel Edge Then Edge / Delay trigger settings with
the canonical `trigger-delay` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-delay --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --arm-channel 1 --arm-slope positive --trigger-channel 2 --trigger-slope negative --time-seconds 1e-6 --count 2 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-delay --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-delay --dry-run --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-delay --simulate --json --query
```

`trigger-delay` v1 configures and queries the Keysight Edge Then Edge / Delay
trigger using `:TRIGger:MODE DELay` and the `:TRIGger:DELay:*` SCPI family.
Configure mode is state-changing and DSO analog-channel-only: it sets an
analog arm source channel, arm slope, delay time, Nth trigger edge count,
analog trigger source channel, and trigger slope. Public slope values are only
`positive` and `negative`; aliases such as `pos`, `neg`, `rising`, `falling`,
`either`, and `alternate` are rejected. `--time-seconds` must be from `4e-9`
through `10.0`, and `--count` must be an integer at least `1`.

Query mode reads `:TRIGger:MODE?`,
`:TRIGger:DELay:ARM:SOURce?`, `:TRIGger:DELay:ARM:SLOPe?`,
`:TRIGger:DELay:TDELay:TIME?`,
`:TRIGger:DELay:TRIGger:COUNt?`,
`:TRIGger:DELay:TRIGger:SOURce?`, and
`:TRIGger:DELay:TRIGger:SLOPe?`. It preserves raw readbacks and tolerates
digital or unknown source state; configure mode does not accept digital,
external, level-volts, threshold, source-alias, or generic trigger-tree
arguments. Every live or simulated command performs one `:SYSTem:ERRor?`
post-check. This slice has hardware-free CLI, Core, simulator, and worker
validation only; no live hardware validation, LAN validation, worker live
validation, DSO-X 2000X/3000X/4024A/4034A live validation, or WebUI runtime
validation is implied. It does not add run, stop, single, force-trigger,
wait-trigger, or capture integration.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-delay --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-delay --arguments-json "{\"arm_channel\":1,\"arm_slope\":\"positive\",\"trigger_channel\":2,\"trigger_slope\":\"negative\",\"time_seconds\":0.000001,\"count\":2}" --json
```

Configure or query DSO analog-channel setup-hold trigger settings with the
canonical `trigger-setup-hold` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-setup-hold --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --clock-channel 1 --data-channel 2 --slope positive --setup-time 1e-9 --hold-time 1e-9 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-setup-hold --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-setup-hold --dry-run --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-setup-hold --simulate --json --query
```

`trigger-setup-hold` v1 configures and queries the Keysight Setup and Hold
trigger using `:TRIGger:MODE SHOLd` and the `:TRIGger:SHOLd:*` SCPI family.
Configure mode is state-changing and DSO analog-channel-only: it sets analog
clock and data source channels, clock slope, setup time, and hold time. Public
slope values are only `positive` and `negative`; aliases such as `pos`, `neg`,
`rising`, and `falling` are rejected. `--setup-time` and `--hold-time` are
plain seconds values and must be positive finite numbers. v1 does not parse
time suffixes.

Query mode reads `:TRIGger:MODE?`,
`:TRIGger:SHOLd:SOURce:CLOCk?`, `:TRIGger:SHOLd:SOURce:DATA?`,
`:TRIGger:SHOLd:SLOPe?`, `:TRIGger:SHOLd:TIME:SETup?`, and
`:TRIGger:SHOLd:TIME:HOLD?`. Query JSON preserves raw mode/source/slope/time
readbacks, normalizes `SHOL`/`SHOLD` mode readbacks to `setup-hold`, normalizes
common analog channel and positive/negative slope readbacks, and tolerates
digital or unknown source readback by leaving the parsed analog channel null.
Query does not fail only because the current trigger mode is not setup-hold.

Configure mode rejects partial configure requests, `--query` combined with
configure options, non-integer channels, channels outside the selected model
profile, digital/MSO source aliases such as `D0`, `DIG0`, `digital0`, `pod`, or
`bus`, unknown source aliases, invalid slopes, and non-finite, zero, negative,
or nonnumeric setup/hold times before instrument access. MSO/digital and
external setup-hold sources are intentionally unsupported in v1 even though
the instrument SCPI family may support digital sources on MSO models. This
command does not implement threshold/level convenience helpers, run, stop,
single, force trigger, wait-trigger, capture integration, actual
signal-trigger validation, or a generic trigger-tree framework.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-setup-hold --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-setup-hold --arguments-json "{\"clock_channel\":1,\"data_channel\":2,\"slope\":\"positive\",\"setup_time\":0.000000001,\"hold_time\":0.000000001}" --json
```

Worker JSON uses canonical keys `setup_time` and `hold_time`, matching the CLI
`--setup-time` and `--hold-time` options. Focused DSO-X 4034A USB CLI live
validation passed on 2026-07-08. Worker live, LAN, WebUI, DSO-X
2000X/3000X/4024A live validation, additional DSO-X 4034A live validation,
MSO/digital source validation, actual signal-trigger behavior, and broader
trigger-tree validation have not been run for `trigger-setup-hold`.

Configure or query DSO analog-channel Nth Edge Burst trigger settings with the
canonical `trigger-edge-burst` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge-burst --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --slope positive --count 3 --idle-time 1e-6 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge-burst --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --slope positive --count 3 --idle-time 1e-6 --level-volts 0.5 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge-burst --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge-burst --dry-run --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge-burst --dry-run --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-edge-burst --simulate --json --query
```

`trigger-edge-burst` v1 configures and queries the Keysight Nth Edge Burst
trigger using `:TRIGger:MODE EBURst`,
`:TRIGger:EBURst:SOURce`, `:TRIGger:EBURst:SLOPe`,
`:TRIGger:EBURst:COUNt`, and `:TRIGger:EBURst:IDLE`.
Configure mode is state-changing and DSO analog-channel-only: it accepts
`--source-channel`, `--slope positive|negative`, `--count`, `--idle-time`, and
optional `--level-volts`. When `--level-volts` is provided, the command sends
`:TRIGger:EDGE:LEVel <level>, CHANnel<n>` after the EBURst fields; when it is
omitted, no level write is sent.

Query mode reads EBURst mode/source/slope/count/idle fields. It reads analog
edge level only when the source readback safely parses as analog `CHAN<n>` or
`CHANnel<n>`. Digital, `NONE`, and unknown source readbacks are preserved in
raw fields and do not fail query solely because the current source is outside
this v1 configure surface.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-edge-burst --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-edge-burst --arguments-json "{\"source_channel\":1,\"slope\":\"positive\",\"count\":3,\"idle_time\":0.000001}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-edge-burst --arguments-json "{\"source_channel\":1,\"slope\":\"positive\",\"count\":3,\"idle_time\":0.000001,\"level_volts\":0.5}" --json
```

Worker support has hardware-free validation only. It accepts only `query`,
`source_channel`, `slope`, `count`, `idle_time`, and optional `level_volts`;
aliases such as `channel`, `source`, `edge_count`, `idle_time_seconds`,
`time_seconds`, `trigger_level`, and `level` are not accepted. Focused DSO-X
4034A USB CLI live validation passed on 2026-07-09. Worker live, LAN, WebUI,
DSO-X 2000X/3000X/4024A, additional DSO-X 4034A, MSO/digital source
validation, actual signal-trigger behavior, broader trigger-tree behavior, and
capture/wait-trigger/run/stop/single workflow integration have not been run or
implemented for `trigger-edge-burst`.

Configure or query DSO analog-channel basic TV / video trigger settings with
the canonical `trigger-tv` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-tv --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-tv --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --standard ntsc --mode field1 --polarity negative --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-tv --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --standard ntsc --mode line-field1 --line 20 --polarity negative --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-tv --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 2 --standard pal --mode line-field2 --line 400 --polarity positive --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-tv --dry-run --json --model DSOX4024A --query
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-tv --simulate --json --query
```

`trigger-tv` v1 configures and queries the common Keysight TV trigger subtree
using `:TRIGger:MODE TV`, `:TRIGger:TV:SOURce`,
`:TRIGger:TV:STANdard`, `:TRIGger:TV:MODE`, optional
`:TRIGger:TV:LINE`, and `:TRIGger:TV:POLarity`. Configure mode is
state-changing and DSO analog-channel-only: it accepts `--source-channel`,
`--standard ntsc|pal|palm|secam`, `--mode field1|field2|all-fields|all-lines|line-field1|line-field2|line-alternate`,
`--polarity positive|negative`, and optional `--line` only for line modes.
Extended video standards, UDTV commands, 3000X/4000X-only `LINE` mode,
digital/MSO, external, USB, NFC, serial/bus, and zone trigger configuration
are not part of this v1 surface.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-tv --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-tv --arguments-json "{\"source_channel\":1,\"standard\":\"ntsc\",\"mode\":\"field1\",\"polarity\":\"negative\"}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-tv --arguments-json "{\"source_channel\":1,\"standard\":\"ntsc\",\"mode\":\"line-field1\",\"line\":20,\"polarity\":\"negative\"}" --json
```

Worker support has hardware-free validation only. It accepts only `query`,
`source_channel`, `standard`, `mode`, `line`, and `polarity`; aliases such as
`channel`, `source`, `tv_source`, `tv_standard`, `trigger_standard`, `tv_mode`,
`trigger_mode`, `line_number`, `field`, `pol`, `trigger_polarity`,
`polarity_raw`, `sourceChannel`, and `source_channel_number` are not accepted.
Live CLI, worker live, LAN, WebUI, DSO-X 2000X/3000X/4024A/4034A live
validation, MSO/digital source validation, extended video/UDTV, actual
signal-trigger behavior, and capture/wait-trigger/run/stop/single workflow
integration have not been run or implemented for `trigger-tv`.

Configure or query DSO analog ASCII pattern trigger settings with the canonical
`trigger-pattern` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pattern --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --pattern XXX1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pattern --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pattern --dry-run --json --pattern XXX1
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-pattern --simulate --json --query
```

`trigger-pattern` v1 configures and queries the Keysight Pattern trigger using
the DSO analog ASCII entered-pattern surface only. Configure mode is
state-changing and sends `:TRIGger:MODE PATTern`,
`:TRIGger:PATTern:FORMat ASCii`, `:TRIGger:PATTern "<pattern>"`, and
`:TRIGger:PATTern:QUALifier ENTered`. The pattern is a raw ASCII string using
only `0`, `1`, and `X`; lowercase input is normalized to uppercase. The CLI
rejects empty strings, whitespace, commas, quotes, `R`, `F`, `0x...`, and other
characters before opening an instrument. Pattern length must match the selected
model profile analog channel count.

Query mode reads `:TRIGger:MODE?`, `:TRIGger:PATTern:FORMat?`,
`:TRIGger:PATTern?`, and `:TRIGger:PATTern:QUALifier?`. JSON normalizes common
readbacks such as `ASC`/`ASCii` to `ascii`, `HEX` to `hex`, and
`ENT`/`ENTered` to `entered`, while preserving raw pattern response,
edge-source, and edge readback fields.

This v1 slice does not support HEX configure mode, digital/MSO pattern
configuration, `R`/`F`, edge source/edge configure parameters, duration
qualifiers, pattern range commands, source commands, level commands, aliases,
or generic trigger-tree behavior. Hardware-free Core/CLI/simulator/worker
tests cover this command. No live hardware validation was run because no
instrument is currently available. Pending validation includes live CLI,
worker live, LAN, WebUI, DSO-X 2000X/3000X/4024A/4034A live validation,
MSO/digital validation, and broader trigger-tree validation.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-pattern --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-pattern --arguments-json "{\"pattern\":\"XXX1\"}" --json
```

Configure or query DSO analog-only OR trigger settings with the canonical
`trigger-or` command:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-or --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --pattern XXXR --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-or --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --query --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-or --dry-run --json --pattern XXXR
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli trigger-or --simulate --json --query
```

`trigger-or` v1 configures and queries the Keysight OR trigger using the DSO
analog-only `:TRIGger:OR` surface. Configure mode is state-changing and sends
`:TRIGger:MODE OR` followed by `:TRIGger:OR "<pattern>"`. The pattern is a raw
edge string using only `R` for rising edge, `F` for falling edge, `E` for
either edge, and `X` for don't care; lowercase input is normalized to
uppercase. The CLI rejects empty strings, whitespace, commas, quotes, digits
`0`/`1`, `0x...`, and other characters before opening an instrument. Pattern
length must match the selected model profile analog channel count.

For DSO analog-only mapping, string order follows Keysight OR trigger bit
assignment. On 4-channel DSO models, positions are CH4, CH3, CH2, CH1, so CH1
rising only is `XXXR`, CH1 rising OR CH2 falling is `XXFR`, and any analog
channel either edge is `EEEE`. On 2-channel DSO models, positions are CH2,
CH1, so CH1 rising only is `XR`.

Query mode reads `:TRIGger:MODE?` and `:TRIGger:OR?`. JSON preserves
`raw_mode` and `raw_pattern`, normalizes common quoted or unquoted valid
readbacks to uppercase `pattern`, and tolerates non-OR current trigger mode
without failing solely because the mode is not OR.

This v1 slice does not implement MSO/digital OR trigger mapping, aliases,
generic trigger-tree behavior, run, stop, single, force trigger, wait for a
trigger, capture waveform data, or WebUI runtime behavior. Hardware-free
Core/CLI/simulator/worker tests cover this command. No live hardware
validation was run. Worker support is hardware-free only until separately
live-tested.

Worker usage:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-or --arguments-json "{\"query\":true}" --json
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli send-command --port 8765 --command trigger-or --arguments-json "{\"pattern\":\"XXXR\"}" --json
```

Query read-only measurements:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item vpp --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item frequency --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item period --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item vavg --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item vrms --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item ac_rms --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item minimum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item maximum --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item x_at_max --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item x_at_min --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item rise_time --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item fall_time --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item amplitude --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item top --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item base --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item overshoot --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item preshoot --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item positive_width --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item negative_width --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item duty_cycle --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item negative_duty_cycle --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item area --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item positive_edges --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item negative_edges --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item positive_pulses --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item negative_pulses --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item y_at_x --time 0 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item time_at_edge --slope positive --occurrence 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --item time_at_value --level 0.5 --slope positive --occurrence 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --reference-channel 2 --item phase --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --source-channel 1 --reference-channel 2 --item delay --log-scpi
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
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-log --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --items vpp,frequency --count 10 --interval-seconds 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli measure-log --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --channel 2 --items vpp,frequency --pair 1:2 --pair-items phase --count 5 --output-dir data\measure_logs\ch1_ch2 --log-scpi
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
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 1000 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 10000 --csv data\ch1.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 1000 --csv data\ch1.csv --plot data\ch1.png --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 1000 --format word --csv data\ch1_word.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --channel 2 --points 1000 --csv data\ch1_ch2.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --channel 2 --points 1000 --csv data\ch1_ch2.csv --allow-time-axis-tolerance --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel all --points 1000 --csv data\all_channels.csv --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 1000 --wait-trigger --trigger-timeout-ms 5000 --trigger-poll-interval-ms 100 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 1000 --wait-trigger --trigger-timeout-ms 5000 --force-trigger-on-timeout --log-scpi
```

The current capture slice supports BYTE and WORD waveform formats with 1000,
5000, and 10000 requested points. BYTE remains the default. WORD capture sets
`:WAVeform:BYTeorder MSBFirst` and `:WAVeform:UNSigned ON` before reading data.
Capability flags describe the runtime-supported and guarded feature surface,
not whether each feature has completed live validation on every model.
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
timeout, acquisition mode, waveform point mode, or return-to-local behavior. If
the CSV or metadata file cannot be written because it is open in another
program or the folder is not writable, the CLI reports a plain `error:` message
instead of a Python traceback.

`capture --wait-trigger` is an explicit state-changing triggered capture mode.
It sends `:SINGle`, then polls only `:OPERegister:CONDition?` before waveform
readout. `--trigger-timeout-ms` is required with `--wait-trigger`.
`--trigger-poll-interval-ms` defaults to 100 ms and must be less than or equal
to the timeout. `--force-trigger-on-timeout` is valid only with
`--wait-trigger`; after the first finite wait times out it sends
`:TRIGger:FORCe`, then repeats the same finite poll window before capture. The
command does not use `:TRIGger:STATus?` or `*OPC?`.
For DSO-X 2000X/3000X/4000X models, operation-condition classification uses
the Operation Status Condition Run bit: Run set is pending, and Run clear is
complete. Other live series remain conservative until separately validated.

Triggered capture JSON adds `result.trigger`. Outcomes are `natural`, `forced`,
`timeout`, or `unknown`. Only `natural` and `forced` write waveform artifacts.
`timeout`, unsupported poll query, parse failure, or unclassified operation
condition state returns non-zero, writes no capture artifacts, records raw poll
values in `raw_values` and `condition_values`, and still performs one
`:SYSTem:ERRor?` post-check when possible. Unsupported live operation-condition
values remain unclassified and do not allow capture.

Capture a finite waveform batch:

```powershell
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture-batch --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --points 1000 --format byte --count 3 --interval-seconds 1 --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture-batch --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel 1 --channel 2 --points 1000 --format word --count 2 --output-dir data\captures\ch1_ch2_batch --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli capture-batch --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --channel all --points 1000 --count 2
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
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli screenshot --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli screenshot --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --output data\screen.png --log-scpi
.\.venv\Scripts\python.exe -m keysight_scope_cli.cli screenshot --resource "$env:KEYSIGHT_SCOPE_RESOURCE" --background white --log-scpi
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
