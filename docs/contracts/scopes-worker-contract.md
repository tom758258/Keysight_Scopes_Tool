# Scopes Worker Contract

Schema version: `1`

This is the Scopes worker contract only. It follows
[Common Worker Protocol](common-worker-protocol.md) for lifecycle concepts and
defines the Scopes-specific command model, queue behavior, and artifacts.

## Cross-Instrument Compatibility

Scopes uses Common `POST /command` as the shared worker command envelope.
Cross-instrument orchestrators should depend only on the Common lifecycle:
process start, stdout JSONL observation, `ready`, `GET /status`,
`POST /command`, `POST /stop`, common command response fields, process exit
codes, and structured artifacts. Scopes-specific command names, simulator/VISA
session behavior, SCPI side effects, and waveform/measurement artifacts belong
to this document.

## Runtime

Start the worker with:

```text
keysight-scopes worker --host 127.0.0.1 --port 8765 --simulate --model DSOX4024A
keysight-scopes worker --host 127.0.0.1 --port 8765 --live --resource <RESOURCE> --model DSOX4024A
```

Arguments:

- `--host`: bind address, default `127.0.0.1`.
- `--port`: bind port, default `8765`; `0` requests an available port.
- `--simulate` or `--live`: required run mode. Live mode requires
  `--resource`.
- `--model`: capability profile used before opening a device, default
  `DSOX4024A`.
- `--resource`: live resource string, required with `--live`.
- `--artifact-root`: default `data/worker`.
- `--queue-max`: accepted pending job limit, default `32`.
- `--format`: `jsonl` or `text`, default `jsonl`.

The worker fixes run context at startup. Every accepted job opens its own
simulator or VISA session. Live jobs always use the startup `--resource` and
`--model`; command arguments cannot override them. Request validation happens
before enqueue, artifact creation, session open, or SCPI.

## Endpoints

`GET /status` is non-mutating. It returns `run_id`, mode, model, resource,
queue summary, active job, last job, command/status/stop URLs, `fatal_error`,
and `timestamp_utc`. It must not create artifacts, mutate the queue, open VISA, or
send SCPI. It does not include `trigger_url`.

`POST /command` is the Scopes worker-specific implementation of the Common
command envelope. It accepts exactly this JSON object:

```json
{"command": "identify", "arguments": {}, "job_id": "client-id"}
```

Allowed top-level fields are the Common fields `command`, `arguments`, and
`job_id`. `command` must be a known Scopes worker command, `arguments` must be
omitted or an object, and `job_id` must be omitted or a string. Unknown fields
and malformed bodies return HTTP `400` and are not enqueued.

Every `/command` response contains the Common fields `status`, `command`, and
`job_id`. A safely identifiable client command string and client job string are
echoed even when validation fails, including unknown commands and unknown
top-level fields. Malformed JSON, non-object bodies, missing commands, and
non-string command identities use `command: null`; omitted or non-string
`job_id` values use `job_id: null`.

Accepted responses use HTTP `202` and contain:

```json
{
  "status": "accepted",
  "command": "identify",
  "job_id": "client-id",
  "worker_job_id": "worker-generated-id",
  "artifact_path": "data/worker/<run_id>/<worker_job_id>"
}
```

`202 accepted` means the job was validated, assigned an artifact directory, and
enqueued. It does not mean the oscilloscope action succeeded.

Queue, stopping, rate, or other Scopes admission failures use
`status: "rejected"` and a Scopes-specific `reason`, for example:

```json
{
  "status": "rejected",
  "command": "identify",
  "job_id": "client-id",
  "reason": "queue_full"
}
```

Validation failures use HTTP `400`, `status: "error"`, the Common
`command`/`job_id` echo rules, `error: "validation_error"`, and `message`:

```json
{
  "status": "error",
  "command": "identify",
  "job_id": "client-id",
  "error": "validation_error",
  "message": "unknown request field: extra"
}
```

`POST /stop` does not enter the normal command queue. It sets cooperative stop,
rejects new commands, cancels queued jobs, writes terminal `result.json` for
cancelled jobs, and emits `job_finished` for each cancelled job. Running jobs
observe cancellation at worker checkpoints or after command return; a blocking
device read may not stop immediately.

The worker does not implement `/trigger`, `trigger_url`, or `soft-*` endpoints.

## Command Inventory

Worker `/command` supports the existing Scopes capability surface:

- `identify`, `check-error`, `doctor`
- `run`, `single`, `stop-acquisition`, `force-trigger`
- `acquisition`, `acquisition-check`, `sample-rate`, `acquisition-points`,
  `record-length`
- `capture`, `capture-batch`, `screenshot`, `smoke`
- `measure`, `measure-stats`, `measure-sweep`, `measure-log`
- `channel-display`, `channel-label`, `channel-scale`, `channel-offset`,
  `channel-coupling`, `channel-probe`, `channel-bandwidth-limit`,
  `channel-impedance`, `channel-invert`, `channel-range`, `channel-units`,
  `channel-vernier`, `channel-probe-skew`
- `display-label`, `display-clear`, `display-persistence`,
  `display-intensity`, `display-vectors`, `annotation`
- `timebase-scale`, `timebase-position`
- `edge-trigger`, `trigger-pulse-width`, `trigger-runt`,
  `trigger-transition`, `trigger-pattern`, `trigger-or`, `trigger-holdoff`, `cursor`,
  `autoscale`
- `setup-save`, `setup-recall`, `fft`

`list-resources` remains an explicit discovery command outside live worker
flows. `hardware-report` remains a local report renderer. They are not accepted
by worker `/command`.

Unsupported command names include `snapshot`, `restore`, `diff`, generic
`math`, and domain `status`. Worker status is reserved for lifecycle
`GET /status` and `keysight-scopes status`.

Arguments use the CLI option names without leading dashes and with underscores
accepted as JSON keys, for example:

```json
{
  "command": "capture",
  "arguments": {
    "channel": [1, 2],
    "points": 1000,
    "csv": "capture.csv",
    "plot": "plot.png"
  }
}
```

Triggered capture is an explicit opt-in extension of `capture`; it is not a new
worker command:

```json
{
  "command": "capture",
  "arguments": {
    "channel": [1],
    "points": 1000,
    "wait_trigger": true,
    "trigger_timeout_ms": 5000,
    "trigger_poll_interval_ms": 100,
    "force_trigger_on_timeout": true
  }
}
```

`wait_trigger` sends `:SINGle`, then polls only
`:OPERegister:CONDition?` before waveform capture. `trigger_timeout_ms` is
required when `wait_trigger` is true. `trigger_poll_interval_ms` must be
positive and less than or equal to the timeout. `force_trigger_on_timeout` is
valid only with `wait_trigger`; it sends `:TRIGger:FORCe` only after the first
finite wait times out, then repeats the finite poll window. The worker does not
use `:TRIGger:STATus?` or `*OPC?`. For DSO-X 2000X/3000X/4000X models,
operation-condition classification uses the Operation Status Condition Run bit:
Run set is pending, and Run clear is complete. Other live series remain
conservative until separately validated.

Query-only worker commands require the same explicit CLI query flag in JSON
form:

```json
{"command": "sample-rate", "arguments": {"query": true}}
```

```json
{"command": "sample-rate", "arguments": {"query": true, "maximum": true}}
```

```json
{"command": "acquisition-points", "arguments": {"query": true}}
```

```json
{"command": "record-length", "arguments": {"query": true}}
```

`force-trigger` is accepted only as an explicit command:

```json
{"command": "force-trigger", "arguments": {}}
```

`trigger-pulse-width` is accepted only as the canonical Pulse Width trigger
command. It uses the underlying Keysight `:TRIGger:GLITch...` SCPI family:

```json
{"command": "trigger-pulse-width", "arguments": {"query": true}}
```

```json
{
  "command": "trigger-pulse-width",
  "arguments": {
    "channel": 1,
    "polarity": "positive",
    "qualifier": "less_than",
    "time_seconds": 0.000001
  }
}
```

```json
{
  "command": "trigger-pulse-width",
  "arguments": {
    "channel": 1,
    "polarity": "negative",
    "qualifier": "greater_than",
    "time_seconds": 0.000005,
    "level_volts": 0.5
  }
}
```

```json
{
  "command": "trigger-pulse-width",
  "arguments": {
    "channel": 1,
    "polarity": "positive",
    "qualifier": "range",
    "min_time_seconds": 0.000001,
    "max_time_seconds": 0.00001
  }
}
```

Worker JSON may use `greater_than` and `less_than` qualifier values; they are
converted to the CLI `greater-than` and `less-than` values before parsing.
Configure mode is analog-channel-only and changes trigger settings. Query mode
must use `query: true` without configure keys. The worker does not accept
aliases such as `trigger-glitch`, `trigger-pulse`, `pulse-width`,
`glitch-trigger`, or `trigger-width`.

`trigger-runt` is accepted only as the canonical Runt trigger command. It uses
the underlying Keysight `:TRIGger:RUNT...` SCPI family plus shared
`:TRIGger:LEVel:LOW/HIGH` thresholds:

```json
{"command": "trigger-runt", "arguments": {"query": true}}
```

```json
{
  "command": "trigger-runt",
  "arguments": {
    "channel": 1,
    "polarity": "either",
    "qualifier": "none",
    "low_level_volts": -0.5,
    "high_level_volts": 0.5
  }
}
```

```json
{
  "command": "trigger-runt",
  "arguments": {
    "channel": 1,
    "polarity": "positive",
    "qualifier": "greater_than",
    "time_seconds": 0.000005,
    "low_level_volts": -0.25,
    "high_level_volts": 0.75
  }
}
```

Worker JSON may use `greater_than` and `less_than` qualifier values; they are
converted to the CLI `greater-than` and `less-than` values before parsing.
Configure mode is analog-channel-only and changes trigger settings. Query mode
must use `query: true` without configure keys. `qualifier: "none"` rejects
`time_seconds`; timed qualifiers require it. The worker does not accept aliases
such as `runt-trigger` or `trigger-runt-width`.

`trigger-transition` is accepted only as the canonical Transition trigger
command. It uses the underlying Keysight `:TRIGger:TRANsition...` SCPI family
plus shared `:TRIGger:LEVel:LOW/HIGH` thresholds:

```json
{"command": "trigger-transition", "arguments": {"query": true}}
```

```json
{
  "command": "trigger-transition",
  "arguments": {
    "channel": 1,
    "slope": "positive",
    "qualifier": "greater_than",
    "time_seconds": 0.000005,
    "low_level_volts": -0.5,
    "high_level_volts": 0.5
  }
}
```

```json
{
  "command": "trigger-transition",
  "arguments": {
    "channel": 1,
    "slope": "negative",
    "qualifier": "less_than",
    "time_seconds": 0.000002,
    "low_level_volts": -0.25,
    "high_level_volts": 0.75
  }
}
```

Worker JSON may use `greater_than` and `less_than` qualifier values; they are
converted to the CLI `greater-than` and `less-than` values before parsing.
Configure mode is analog-channel-only and changes trigger settings. Query mode
must use `query: true` without configure keys. Configure mode requires
`channel`, `slope`, `qualifier`, `time_seconds`, `low_level_volts`, and
`high_level_volts`; slope is `positive` or `negative`, qualifier is
`greater-than` or `less-than`, `time_seconds` must be positive finite, and low
level must be less than high level. The worker does not accept digital/MSO or
external source configuration, and it does not accept aliases such as
`transition-trigger`, `trigger-rise-fall`, or `trigger-rise-time`.

`trigger-pattern` is accepted only as the canonical Pattern trigger command.
It uses the DSO analog ASCII entered-pattern `:TRIGger:PATTern...` SCPI
surface:

```json
{"command": "trigger-pattern", "arguments": {"query": true}}
```

```json
{"command": "trigger-pattern", "arguments": {"pattern": "XXX1"}}
```

Configure mode changes trigger settings and sends `:TRIGger:MODE PATTern`,
`:TRIGger:PATTern:FORMat ASCii`, `:TRIGger:PATTern "<pattern>"`, and
`:TRIGger:PATTern:QUALifier ENTered`. The pattern is a raw string using only
`0`, `1`, and `X`; lowercase input is normalized by the CLI/Core path. Empty
strings, whitespace, commas, quotes, `R`, `F`, `0x...`, and other characters
are rejected before enqueue, artifact creation, VISA open, or SCPI. Pattern
length must match the selected model profile analog channel count.

Query mode must use `query: true` without configure keys and reads
`:TRIGger:MODE?`, `:TRIGger:PATTern:FORMat?`, `:TRIGger:PATTern?`, and
`:TRIGger:PATTern:QUALifier?`. Result JSON normalizes common ASCII/HEX format
and entered qualifier readbacks while preserving raw pattern response,
edge-source, and edge fields.

The worker does not accept `source`, `level`, `format`, `edge`, `edge_source`,
`qualifier`, `time_seconds`, `greater_than_seconds`, `less_than_seconds`,
`range_min_seconds`, or `range_max_seconds` for this v1 command. It does not
support HEX configure mode, digital/MSO pattern configuration, `R`/`F`,
optional edge parameters, duration qualifiers, pattern range commands,
source/level commands, aliases such as `pattern-trigger`, or generic
trigger-tree behavior. Worker support has hardware-free validation only; live
CLI, worker live, LAN, WebUI, DSO-X 2000X/3000X/4024A/4034A, MSO/digital, and
broader trigger-tree validation have not been run.

`trigger-or` is accepted only as the canonical OR trigger command. It uses the
DSO analog-only `:TRIGger:OR` SCPI surface:

```json
{"command": "trigger-or", "arguments": {"query": true}}
```

```json
{"command": "trigger-or", "arguments": {"pattern": "XXXR"}}
```

Configure mode changes trigger settings and sends `:TRIGger:MODE OR` and
`:TRIGger:OR "<pattern>"`. The pattern is a raw edge string using only `R`,
`F`, `E`, and `X`; lowercase input is normalized by the CLI/Core path. Empty
strings, whitespace, commas, quotes, digits `0`/`1`, `0x...`, and other
characters are rejected before enqueue, artifact creation, VISA open, or SCPI.
Pattern length must match the selected model profile analog channel count.

For DSO analog-only mapping, string order follows Keysight OR trigger bit
assignment: CH4, CH3, CH2, CH1 on 4-channel DSO models and CH2, CH1 on
2-channel DSO models. Examples: `XXXR` means CH1 rising only on a 4-channel
DSO, `XXFR` means CH1 rising OR CH2 falling on a 4-channel DSO, `EEEE` means
any analog channel either edge on a 4-channel DSO, and `XR` means CH1 rising
only on a 2-channel DSO.

Query mode must use `query: true` without configure keys and reads
`:TRIGger:MODE?` and `:TRIGger:OR?`. Result JSON preserves raw mode and raw OR
readbacks, normalizes common quoted or unquoted valid OR patterns, and does not
fail solely because the current trigger mode is not OR.

The worker does not accept `mask`, `channels`, alias fields, source/level,
format, edge, qualifier, timing, digital/MSO, or generic trigger-tree arguments
for this v1 command. It does not accept aliases such as `or-trigger` or
`trigger-or-mask`. Worker support has hardware-free validation only; live CLI,
worker live, LAN, WebUI, DSO-X 2000X/3000X/4024A/4034A, MSO/digital, and
broader trigger-tree validation have not been run.

### Advanced Channel Commands

The worker supports the same one-shot advanced analog channel commands as the
CLI:

- `channel-impedance`
- `channel-invert`
- `channel-range`
- `channel-units`
- `channel-vernier`
- `channel-probe-skew`

Arguments use CLI option names without leading dashes:

```json
{"command": "channel-impedance", "arguments": {"channel": 1, "query": true}}
```

```json
{
  "command": "channel-impedance",
  "arguments": {"channel": 1, "impedance": "fifty", "allow_50_ohm": true}
}
```

```json
{"command": "channel-invert", "arguments": {"channel": 1, "on": true}}
```

```json
{"command": "channel-range", "arguments": {"channel": 1, "volts_full_scale": 4}}
```

```json
{"command": "channel-units", "arguments": {"channel": 1, "units": "amp"}}
```

```json
{"command": "channel-vernier", "arguments": {"channel": 1, "off": true}}
```

```json
{"command": "channel-probe-skew", "arguments": {"channel": 1, "seconds": 1e-9}}
```

`channel-range` uses `volts_full_scale`, matching CLI
`--volts-full-scale`. Worker-only aliases such as `volts` and `range_volts`
are not supported. `channel-offset` still uses its existing `volts` argument.

Setting `channel-impedance` to `fifty` requires `allow_50_ohm: true`.
Requests without that opt-in are rejected before enqueue, artifact creation,
VISA open, or SCPI. The model capability guard remains in force after opt-in:
DSO-X 2000X profiles reject `fifty` before `:CHANnel<n>:IMPedance FIFTy` can
be sent.

Worker support for these commands has hardware-free validation only. Live
worker validation, LAN validation, WebUI integration, and DSO-X 2000X/3000X
hardware validation have not been run.

### Common Display Commands

The worker supports four shared display one-shot commands:

- `display-clear`
- `display-persistence`
- `display-intensity`
- `display-vectors`

Arguments use CLI option names without leading dashes:

```json
{"command": "display-clear", "arguments": {}}
```

```json
{"command": "display-persistence", "arguments": {"query": true}}
```

```json
{"command": "display-persistence", "arguments": {"mode": "minimum"}}
```

```json
{"command": "display-persistence", "arguments": {"seconds": 1.0}}
```

```json
{"command": "display-intensity", "arguments": {"query": true}}
```

```json
{"command": "display-intensity", "arguments": {"value": 75}}
```

```json
{"command": "display-vectors", "arguments": {"query": true}}
```

```json
{"command": "display-vectors", "arguments": {"on": true}}
```

`display-clear` accepts no argument keys. `display-persistence` accepts only
`query`, `mode`, and `seconds`; `mode` is `minimum` or `infinite`, and
`seconds` must be from `0.1` through `60.0`. Persistence result JSON uses
`mode: "minimum"` or `mode: "infinite"` for enum states and `mode: null` with
numeric `seconds` for finite seconds. `display-intensity` accepts only `query`
and `value`, with integer `value` from `0` through `100`, and uses the shared
`:DISPlay:INTensity:WAVeform` SCPI path.
`display-vectors` accepts only `query` and `on`; setting OFF is unsupported in
this common v1 surface.

For these commands, unknown keys are rejected before enqueue, artifact
creation, VISA open, or SCPI. Boolean `query` and `on` keys must be exactly
`true`; false or null values are rejected instead of being ignored.
`display-persistence-clear` is not a v1 common worker command.

### Label And Annotation Commands

The worker supports the same one-shot label and annotation commands as the CLI:

- `channel-label`
- `display-label`
- `annotation`

Arguments use CLI option names without leading dashes:

```json
{"command": "channel-label", "arguments": {"channel": 1, "text": "Input A"}}
```

```json
{"command": "channel-label", "arguments": {"channel": 1, "query": true}}
```

```json
{"command": "display-label", "arguments": {"on": true}}
```

```json
{"command": "display-label", "arguments": {"off": true}}
```

```json
{"command": "display-label", "arguments": {"query": true}}
```

```json
{
  "command": "annotation",
  "arguments": {
    "slot": 1,
    "on": true,
    "text": "Run note",
    "color": "white",
    "background": "opaque"
  }
}
```

```json
{
  "command": "annotation",
  "arguments": {
    "slot": 2,
    "text": "Run note",
    "x": 10,
    "y": 20
  }
}
```

```json
{"command": "annotation", "arguments": {"slot": 2, "query": true}}
```

These are one-shot worker commands and may change front-panel display state.
They do not add digital labels, bus labels, `:DISPlay:LABList`
import/export, label position, or annotation batch operations.

`annotation` follows the CLI validation rules: `query` is mutually exclusive
with setters, `on` and `off` are mutually exclusive, `clear` and `text` are
mutually exclusive, and non-query requests require at least one setter/action.
4000X models support indexed annotation slots 1 through 10 and X/Y position.
2000X/3000X models use unindexed annotation slot 1 and do not support X/Y.
Annotation text accepts printable ASCII text up to 254 characters and must not
contain double quotes or control characters.

Validation errors must reject before enqueue and before any artifact, VISA, or
SCPI side effect.

Triggered capture `result.json.result.trigger` records raw operation-condition
poll values and the classified outcome. Only `natural` and `forced` outcomes
write capture artifacts. `timeout` and `unknown` outcomes return non-zero and
write no command artifacts. Unsupported live operation-condition values remain
unclassified and do not allow capture.

## Artifacts

Each accepted job creates:

```text
data/worker/<run_id>/<worker_job_id>/request.json
data/worker/<run_id>/<worker_job_id>/result.json
```

`request.json` is written before the `202` response. `result.json` is written
only for terminal states using a temp file and atomic replace.

`result.json` contains:

- `schema_version`
- `run_id`
- `worker_job_id`
- client `job_id`
- `command`
- terminal `state`: `succeeded`, `failed`, or `cancelled`
- `ok`
- accepted/started/finished timestamps
- command `result`
- `files`
- `error`
- `exit_code`

Command artifacts keep existing Scopes meanings: CSV waveform data, PNG plots
or screenshots, metadata JSON, manifests, reports, and `scpi.log` files.
Worker `result.json` is the orchestrator machine source of truth; human output
is diagnostic only.

Worker path resolution applies only inside worker job execution. Direct
one-shot CLI commands keep their normal path semantics. For worker jobs,
relative output paths are resolved under
`data/worker/<run_id>/<worker_job_id>/`; absolute output paths are allowed and
recorded as absolute paths. Default worker outputs are:

- `capture`: `capture.csv` and `capture_meta.json` in the job directory; a
  plot is created only when a path string is supplied. With `wait_trigger`,
  these artifacts are written only when the trigger outcome allows capture.
- `screenshot`: `screen.png` in the job directory.
- `capture-batch`, `measure-log`, `smoke`, and `acquisition-check`: the job
  directory is the default `output_dir`.

`sample-rate`, `acquisition-points`, `record-length`, `force-trigger`,
`trigger-pulse-width`, `trigger-runt`, `trigger-transition`,
`trigger-pattern`, `trigger-or`, `display-clear`, `display-persistence`,
`display-intensity`, and `display-vectors` do not create command artifacts.
Their terminal `result.json.result` contains the existing one-shot structured
`result` fields for that command. For `sample-rate` maximum queries, that
includes `query_kind: "maximum"` and `maximum_sample_rate_hz`.

Directory-output commands may use the worker job directory even though
`request.json` already exists there. Other pre-existing command artifact paths
are rejected before simulator/VISA open or SCPI execution. `result.json.files`
lists only command artifact paths that actually exist.

Live worker jobs validate identity before command-specific SCPI. The worker
opens the startup `resource`, sets a fixed `2000 ms` timeout, queries `*IDN?`,
and compares the normalized IDN model with the startup `model`. A mismatch
fails the job with structured `error.type: "identity_mismatch"`,
`expected_model`, and `actual_idn`; the worker control plane remains alive.

## Client Commands

Lifecycle clients:

- `keysight-scopes send-command --host 127.0.0.1 --port 8765 --command identify --arguments-json {}`
- `keysight-scopes status --host 127.0.0.1 --port 8765`
- `keysight-scopes stop --host 127.0.0.1 --port 8765`
- `keysight-scopes wait-ready --host 127.0.0.1 --port 8765`

Client exit codes are `0` for accepted/lifecycle success/dry-run success, `2`
for usage, local validation, or HTTP `400`, and `3` for runtime error,
connection error, timeout, invalid response, HTTP request failure, HTTP
`409`/`429`, or fatal worker failure.

## Safety

Live worker startup requires explicit `--resource`. Discovery is separate and
must not happen inside active live workflows. The worker does not guess,
rotate, or scan resources. This worker requirement is stricter than one-shot
CLI live selection, where an explicit resource is sufficient and `--live` is
only a compatibility flag.
