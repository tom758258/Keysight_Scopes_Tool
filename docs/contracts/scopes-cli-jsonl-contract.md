# Scopes CLI JSON / JSONL Contract

Schema version: `1`

This document defines Scopes-specific CLI JSON and JSONL payloads. Shared
envelope rules are defined in
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md). Scopes worker
behavior and artifacts are defined in
[Scopes Worker Contract](scopes-worker-contract.md).

Common fields such as `event`, `schema_version`, `timestamp_utc`, `run_id`,
`ok`, `message`, `fatal_error`, and `exit_code` keep their Common meanings
when present. This document lists only the Scopes-specific event fields,
command result fields, client fields, and artifact fields currently emitted by
`keysight-scopes`.

## Worker JSONL Events

`keysight-scopes worker --format jsonl` writes one JSON object per stdout line.
Human diagnostics belong on stderr or in text mode. The worker emits:

- `ready`: emitted after `/command`, `/status`, and `/stop` are reachable.
- `job_started`: emitted when a queued job begins execution.
- `job_finished`: emitted after terminal `result.json` is written.
- `summary`: emitted when the worker process exits normally or fatally.

All runtime events include `schema_version: 1`, `timestamp_utc`, and the same
`run_id`. The Scopes `ready` event includes `service: "keysight-scopes"`,
`host`, `port`, `mode`, `model`, `resource`, `command_url`, `status_url`, and
`stop_url`; it means `/command`, `/status`, and `/stop` are reachable. It does
not include `trigger_url`.

`job_started` includes `job_id`, `worker_job_id`, `command`, and
`artifact_path`. `job_finished` includes `job_id`, `worker_job_id`, `command`,
`artifact_path`, `result_path`, `state`, `ok`, `exit_code`, and `error`.
`state` is one of `succeeded`, `failed`, or `cancelled`; only `succeeded` may
use `ok: true`. `summary` includes `accepted`, `succeeded`, `failed`,
`cancelled`, `ok`, `fatal_error`, and `exit_code`.

## Worker Client JSON

`keysight-scopes send-command`, `status`, `stop`, and `wait-ready` emit one
JSON object when called with `--json`.

All worker client JSON includes `schema_version: 1` and `timestamp_utc`.
`send-command` uses the worker command name in `command`; `status`, `stop`, and
`wait-ready` use the lifecycle CLI command name.

The Common client diagnostic fields from
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md) may appear
when knowable, including `client_command`, `method`, `url`, `endpoint`,
`timeout_ms`, `elapsed_ms`, `request_sent`, `reachable`, `http_status`, and
`error_phase`.

`send-command` sends the Common `/command` envelope with Scopes command names
from [Scopes Worker Contract](scopes-worker-contract.md). Successful responses
include the worker response fields, including `status`, `command`, `job_id`,
`worker_job_id`, and `artifact_path` when accepted. Validation and admission
failures merge the worker response envelope into client JSON, including
`command`, `job_id`, `reason`, `error`, and `message` when present.

`status` and `wait-ready` use the same status payload schema. Successful
responses include `service: "keysight-scopes"`, `status`, `run_id`, `mode`,
`model`, `resource`, `queue`, `active_job`, `last_job`, `urls`,
`fatal_error`, and `timestamp_utc`. `run_id` must match the `ready` event from
the same worker session.

The URL fields for `status` and `wait-ready` are only in the nested `urls`
object. The `urls` object must contain `command_url`, `status_url`, and
`stop_url`. Top-level `command_url`, `status_url`, and `stop_url` fields are
not supported in `status` or `wait-ready` JSON. The `urls` object must not
include `trigger_url`; Scopes workers do not expose a trigger endpoint.

Worker HTTP `400` is a validation failure and exits `2`. Runtime errors,
connection errors, timeouts, invalid responses, HTTP request failures, worker
HTTP `409`/`429`, and fatal worker failures exit `3`.
Accepted `/command` responses exit `0`, but accepted does not mean the Scopes
job succeeded; read worker `result.json` for the terminal result.

## Single-Response JSON

Commands that accept `--json` write exactly one JSON object to stdout. SCPI
debug logs from `--log-scpi` go to stderr and are not part of the JSON
contract.

Top-level fields currently used by Scopes:

- `schema_version`: integer schema version, currently `1`.
- `timestamp_utc`: UTC ISO 8601 timestamp with offset.
- `ok`: boolean result. `false` means the command failed or reported an
  instrument/system-error condition.
- `command`: CLI command name.
- `mode`: `dry_run`, `simulate`, or `live`.
- `resource`: VISA resource, simulator resource, dry-run resource, or
  environment-derived resource.
- `backend`: backend display name when known.
- `idn`: parsed `*IDN?` object when known.
- `capabilities`: model capability object when known.
- `scpi`: object with `planned` and `sent` command lists.
- `result`: command-specific structured result.
- `files`: list of artifact descriptors with `kind` and `path`.
- `system_error`: latest system error object when queried.
- `error`: structured error object with `type` and `message`, or `null`.

Single-response one-shot JSON does not include worker-only fields such as
`event`, `run_id`, `message`, `fatal_error`, or `exit_code` unless a future
command explicitly documents them. Consumers should use process return code
plus `ok` and command-specific status fields.

## Command Result Fields

Discovery and identification:

- `list-resources`: `backend`, `resources`, `live_only`, `live_resources`.
- `identify`: `idn`, `capabilities`, `backend`, `timeout_ms`.
- `check-error`: `drain`, `max_reads`, `entries`; top-level `system_error`
  records the latest queried entry.
- `doctor`: `backend`, `timeout_ms`, `acquisition`, `channels`, `timebase`,
  and `edge_trigger`.

Control and setup:

- `run`, `stop-acquisition`, `single`: `action`, `command`.
- `channel-*`: `channel`, `operation`, `command`, and the setting value such as
  `display`, `volts_per_division`, `volts`, `coupling`, `probe_ratio`, or
  `bandwidth_limit`.
- `timebase-*`: `operation`, `command`, and `seconds_per_division` or
  `position_seconds`.
- `edge-trigger`: `operation`, `commands`, `source_channel`, `level_volts`,
  `slope`.
- `trigger-holdoff`: `operation`, `command`, optional `commands`, `seconds`.
- `cursor`: `operation`, `commands`, `source_channel`, `x1_seconds`,
  `x2_seconds`, optional `y1_volts`, `y2_volts`, `auto_timebase`,
  `auto_vertical`, and `diagnostic`.
- `acquisition`: `operation`, `commands`, `type`, `scpi_type`, `count`.
- `autoscale`: `operation`, `commands`, `source_channels`, optional
  `fallback`.
- `setup-save` and `setup-recall`: `operation`, `command`, `slot`, `file`.
- `fft`: `operation`, `commands` or query fields, `function`,
  `source_channel`, `units`, `window`, `center_hz`, `span_hz`, `display`.
  `fft --query` reports the CLI action as `operation: "query"` and the
  instrument math operation as `fft_operation`.

Measurement and artifact-producing flows:

- `measure`: `item`, `channel`, optional `reference_channel`, `value`, `unit`,
  `valid`, `raw_value`, `reason`, `parameters`, and `command`.
- `measure-stats`: `channel`, `items`, `mode`, `reset`, `max_count`,
  `settle_seconds`, and `records`.
- `measure-sweep`: `channels`, `items`, `pairs`, `pair_items`,
  `measurements`, and `summary`.
- `measure-log`: `status`, `channels`, `items`, `pairs`, `pair_items`,
  `interval_seconds`, `requested_count`, `requested_duration_seconds`,
  `completed_rows`, `csv_path`, `manifest_path`, `scpi_log_path`, and compact
  row records. Measurement values are written to CSV.
- `capture`: `channels`, `requested_points`, `actual_points`, `format`,
  `files`, compact per-channel waveform summaries, and optional
  `time_axis_tolerance`.
- `capture-batch`: `status`, `channels`, `format`, `requested_count`,
  `completed_count`, `manifest_path`, `scpi_log_path`, and compact capture
  entries.
- `screenshot`: `format`, `palette`, `background`, `byte_count`,
  `timeout_ms`, `png_path`, and `files`.
- `smoke`: `status`, `output_dir`, `report_path`, `scpi_log_path`, `files`,
  `doctor`, `measurements`, `capture`, `screenshot`, `warnings`, and optional
  `error`.
- `acquisition-check`: `status`, `output_dir`, `report_path`, `scpi_log_path`,
  `average_count`, `check_only`, `stopped_on_error`, `initial_acquisition`,
  `restore`, `termination_reason`, `steps`, `final_acquisition`, and `files`.

Dry-run payloads include planned SCPI and planned artifact paths. Simulate and
live payloads include sent SCPI history when available. Raw waveform sample
arrays are intentionally omitted from top-level JSON; use artifact files for
raw data.

## Artifact JSON

Scopes artifact JSON is machine-readable and should be preferred over human
text:

- Capture metadata JSON records resource, IDN, waveform format, preamble, point
  counts, per-channel summaries, and optional time-axis tolerance.
- Capture-batch `manifest.json` uses `schema_version: 1` and records run
  status, resource, backend, IDN, channels, format, requested count, completed
  captures, artifact paths, and per-capture system error.
- Measure-log `manifest.json` uses `schema_version: 1` and records status,
  resource, backend, IDN, requested row constraints, completed rows, row
  metadata, and system errors.
- Smoke `report.json` uses `schema_version: 1` and records status, resource,
  backend, IDN, doctor data, measurement records, capture metadata, screenshot
  metadata, warnings, files, and errors.
- Acquisition-check `report.json` uses `schema_version: 1` and records status,
  resource, backend, IDN, initial/final acquisition state, restore metadata,
  step records, system errors, files, and errors.

## Compatibility Rules

Consumers must ignore unknown fields. New optional fields may be added under
schema version `1`. Removing required fields or changing required field types
requires a major schema version bump.

Human-readable stdout, stderr, Markdown summaries, and SCPI log text are
diagnostic output, not the agent contract.
