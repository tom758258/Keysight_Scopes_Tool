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
- `run`, `single`, `stop-acquisition`
- `acquisition`, `acquisition-check`
- `capture`, `capture-batch`, `screenshot`, `smoke`
- `measure`, `measure-stats`, `measure-sweep`, `measure-log`
- `channel-display`, `channel-scale`, `channel-offset`, `channel-coupling`,
  `channel-probe`, `channel-bandwidth-limit`
- `timebase-scale`, `timebase-position`
- `edge-trigger`, `trigger-holdoff`, `cursor`, `autoscale`
- `setup-save`, `setup-recall`, `fft`

`list-resources` remains an explicit discovery command outside live worker
flows. `hardware-report` remains a local report renderer. They are not accepted
by worker `/command`.

Unsupported command names include `force-trigger`, `sample-rate`,
`memory-depth`, `snapshot`, `restore`, `diff`, generic `math`, and domain
`status`. Worker status is reserved for lifecycle `GET /status` and
`keysight-scopes status`.

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

Validation errors must reject before enqueue and before any artifact, VISA, or
SCPI side effect.

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
  plot is created only when a path string is supplied.
- `screenshot`: `screen.png` in the job directory.
- `capture-batch`, `measure-log`, `smoke`, and `acquisition-check`: the job
  directory is the default `output_dir`.

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
