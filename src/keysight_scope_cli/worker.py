"""HTTP worker runtime and lifecycle clients for Scopes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from queue import Full, Queue
import sys
import threading
import time
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from uuid import uuid4

from keysight_scope_core.errors import KeysightScopeError
from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.channel import validate_analog_channel

from . import cli as scope_cli


DOMAIN_COMMANDS = {
    "identify",
    "check-error",
    "doctor",
    "run",
    "single",
    "stop-acquisition",
    "force-trigger",
    "acquisition",
    "acquisition-check",
    "sample-rate",
    "acquisition-points",
    "record-length",
    "capture",
    "capture-batch",
    "screenshot",
    "smoke",
    "measure",
    "measure-stats",
    "measure-sweep",
    "measure-log",
    "channel-display",
    "channel-label",
    "channel-scale",
    "channel-offset",
    "channel-coupling",
    "channel-probe",
    "channel-bandwidth-limit",
    "channel-impedance",
    "channel-invert",
    "channel-range",
    "channel-units",
    "channel-vernier",
    "channel-probe-skew",
    "display-label",
    "display-clear",
    "display-persistence",
    "display-intensity",
    "display-vectors",
    "annotation",
    "timebase-scale",
    "timebase-position",
    "trigger-edge",
    "trigger-edge-source",
    "trigger-pulse-width",
    "trigger-runt",
    "trigger-transition",
    "trigger-delay",
    "trigger-setup-hold",
    "trigger-edge-burst",
    "trigger-tv",
    "trigger-pattern",
    "trigger-or",
    "trigger-sweep",
    "trigger-noise-reject",
    "trigger-hf-reject",
    "trigger-edge-coupling",
    "trigger-edge-reject",
    "trigger-holdoff",
    "cursor",
    "autoscale",
    "setup-save",
    "setup-recall",
    "fft",
}


@dataclass
class WorkerJob:
    command: str
    arguments: dict[str, Any]
    job_id: str | None
    worker_job_id: str
    artifact_path: Path
    request_time: str
    state: str = "queued"
    accepted_time: str | None = None
    started_time: str | None = None
    finished_time: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    exit_code: int | None = None
    cancel_requested: bool = False


@dataclass
class WorkerRuntime:
    host: str
    port: int
    mode: str
    model: str
    resource: str | None
    artifact_root: Path
    queue_max: int
    output_format: str
    run_id: str = field(default_factory=lambda: uuid4().hex)
    queue: Queue[WorkerJob] = field(init=False)
    jobs: dict[str, WorkerJob] = field(default_factory=dict)
    active_job_id: str | None = None
    last_job_id: str | None = None
    fatal_error: str | None = None
    stopping: bool = False
    accepted: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.queue = Queue(maxsize=self.queue_max)

    def emit(self, event: str, **values: Any) -> None:
        payload = _event_payload(self, event, **values)
        if self.output_format == "jsonl":
            print(json.dumps(payload, sort_keys=True), flush=True)
        else:
            print(f"{event}: {payload}", flush=True)

    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def status_payload(self) -> dict[str, Any]:
        with self.lock:
            active = self.jobs.get(self.active_job_id) if self.active_job_id else None
            last = self.jobs.get(self.last_job_id) if self.last_job_id else None
            queued = [
                {
                    "worker_job_id": job.worker_job_id,
                    "job_id": job.job_id,
                    "command": job.command,
                    "state": job.state,
                }
                for job in self.jobs.values()
                if job.state == "queued"
            ]
        return {
            "schema_version": 1,
            "service": "keysight-scopes",
            "status": "stopping" if self.stopping else "ready",
            "run_id": self.run_id,
            "mode": self.mode,
            "model": self.model,
            "resource": self.resource,
            "queue": {
                "max": self.queue_max,
                "size": self.queue.qsize(),
                "jobs": queued,
            },
            "active_job": _job_summary(active),
            "last_job": _job_summary(last),
            "urls": {
                "command_url": f"{self.base_url()}/command",
                "status_url": f"{self.base_url()}/status",
                "stop_url": f"{self.base_url()}/stop",
            },
            "fatal_error": self.fatal_error,
            "timestamp_utc": _now(),
        }


def dispatch_lifecycle_command(args: argparse.Namespace) -> int:
    if args.command == "worker":
        return run_worker(args)
    if args.command == "send-command":
        return client_send_command(args)
    if args.command == "status":
        return client_get(args, "/status")
    if args.command == "stop":
        return client_post(args, "/stop", {})
    if args.command == "wait-ready":
        return client_wait_ready(args)
    raise KeysightScopeError("unknown lifecycle command")


def run_worker(args: argparse.Namespace) -> int:
    mode = "simulate" if args.simulate else "live"
    if mode == "live" and not args.resource:
        raise KeysightScopeError("worker --live requires --resource")
    runtime = WorkerRuntime(
        host=args.host,
        port=args.port,
        mode=mode,
        model=args.model,
        resource=args.resource,
        artifact_root=Path(args.artifact_root),
        queue_max=args.queue_max,
        output_format=args.format,
    )
    handler = _make_handler(runtime)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    runtime.port = server.server_port
    worker_thread = threading.Thread(target=_job_loop, args=(runtime,), daemon=True)
    worker_thread.start()
    runtime.emit(
        "ready",
        status_url=f"{runtime.base_url()}/status",
        command_url=f"{runtime.base_url()}/command",
        stop_url=f"{runtime.base_url()}/stop",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        runtime.stopping = True
        runtime.emit("summary", ok=False, fatal_error="interrupted", exit_code=130)
        return 130
    except Exception as exc:
        runtime.fatal_error = str(exc)
        runtime.emit("summary", ok=False, fatal_error=runtime.fatal_error, exit_code=3)
        return 3
    finally:
        server.server_close()
    runtime.queue.join()
    runtime.emit(
        "summary",
        ok=runtime.fatal_error is None,
        fatal_error=runtime.fatal_error,
        exit_code=0 if runtime.fatal_error is None else 3,
    )
    return 0 if runtime.fatal_error is None else 3


def client_send_command(args: argparse.Namespace) -> int:
    try:
        arguments = json.loads(args.arguments_json)
    except json.JSONDecodeError as exc:
        return _client_error(args, 2, "invalid arguments JSON", exc)
    if not isinstance(arguments, dict):
        return _client_error(args, 2, "--arguments-json must decode to an object")
    body = {"command": args.worker_command, "arguments": arguments}
    if args.job_id is not None:
        body["job_id"] = args.job_id
    if args.dry_run:
        response = {
            "ok": True,
            "status": "dry_run",
            "command": args.worker_command,
            "request": body,
        }
        _client_print(args, response)
        return 0
    return client_post(args, "/command", body)


def client_get(args: argparse.Namespace, path: str) -> int:
    try:
        response, status = _http_request(args, path, method="GET")
    except Exception as exc:
        return _client_error(args, 3, "worker request failed", exc)
    _client_print(args, response)
    return 0 if 200 <= status < 300 else _status_exit(status)


def client_post(args: argparse.Namespace, path: str, body: dict[str, Any]) -> int:
    try:
        response, status = _http_request(args, path, method="POST", body=body)
    except Exception as exc:
        return _client_error(args, 3, "worker request failed", exc)
    _client_print(args, response)
    return 0 if 200 <= status < 300 else _status_exit(status)


def client_wait_ready(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + (args.timeout_ms / 1000)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response, status = _http_request(args, "/status", method="GET")
            if status == 200:
                _client_print(args, response)
                return 0
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    return _client_error(args, 3, "worker did not become ready", last_error)


def validate_command_request(body: Any) -> tuple[str, dict[str, Any], str | None]:
    if not isinstance(body, dict):
        raise KeysightScopeError("request body must be a JSON object")
    unknown = set(body) - {"command", "arguments", "job_id"}
    if unknown:
        raise KeysightScopeError(f"unknown request field: {sorted(unknown)[0]}")
    command = body.get("command")
    if not isinstance(command, str) or not command:
        raise KeysightScopeError("command must be a non-empty string")
    if command not in DOMAIN_COMMANDS:
        raise KeysightScopeError(f"unknown command: {command}")
    arguments = body.get("arguments", {})
    if not isinstance(arguments, dict):
        raise KeysightScopeError("arguments must be a JSON object")
    job_id = body.get("job_id")
    if job_id is not None and not isinstance(job_id, str):
        raise KeysightScopeError("job_id must be a string when provided")
    return command, arguments, job_id


def parse_domain_command(
    command: str,
    arguments: dict[str, Any],
    runtime: WorkerRuntime,
    job_dir: Path | None = None,
) -> argparse.Namespace:
    _validate_display_worker_arguments(command, arguments)
    arguments = _normalize_trigger_edge_worker_arguments(command, arguments)
    arguments = _normalize_trigger_edge_source_worker_arguments(
        command, arguments, runtime
    )
    arguments = _normalize_trigger_glitch_worker_arguments(command, arguments)
    arguments = _normalize_trigger_runt_worker_arguments(command, arguments)
    arguments = _normalize_trigger_transition_worker_arguments(command, arguments)
    arguments = _normalize_trigger_delay_worker_arguments(command, arguments)
    arguments = _normalize_trigger_setup_hold_worker_arguments(command, arguments)
    arguments = _normalize_trigger_edge_burst_worker_arguments(command, arguments)
    arguments = _normalize_trigger_tv_worker_arguments(command, arguments)
    arguments = _normalize_trigger_pattern_worker_arguments(command, arguments)
    arguments = _normalize_trigger_or_worker_arguments(command, arguments)
    arguments = _normalize_trigger_holdoff_worker_arguments(command, arguments)
    arguments = _normalize_trigger_common_worker_arguments(command, arguments)
    argv = [command, *arguments_to_argv(arguments)]
    if runtime.mode == "simulate":
        argv += ["--simulate", "--model", runtime.model]
    else:
        argv += ["--live", "--resource", runtime.resource or "", "--model", runtime.model]
    argv.append("--json")
    parser = scope_cli._build_parser()
    try:
        parsed = parser.parse_args(argv)
    except SystemExit as exc:
        raise KeysightScopeError(f"invalid arguments for {command}") from exc
    scope_cli._resolve_cli_mode(parsed)
    scope_cli._validate_pre_open_args(parsed)
    if job_dir is not None:
        _apply_worker_job_paths(parsed, job_dir)
        if runtime.mode == "live":
            setattr(parsed, "_worker_expected_model", runtime.model)
    dry_args = argparse.Namespace(
        **{**vars(parsed), "dry_run": True, "simulate": False, "live": False}
    )
    scope_cli._dry_run_payload(dry_args)
    return parsed


def _validate_display_worker_arguments(command: str, arguments: dict[str, Any]) -> None:
    allowed_by_command = {
        "display-clear": set(),
        "display-persistence": {"query", "mode", "seconds"},
        "display-intensity": {"query", "value"},
        "display-vectors": {"query", "on"},
    }
    if command not in allowed_by_command:
        return
    allowed = allowed_by_command[command]
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for {command}: {sorted(unknown)[0]}")
    if command == "display-clear" and arguments:
        raise KeysightScopeError("display-clear does not accept arguments")
    for key in ("query", "on"):
        if key in arguments and arguments[key] is not True:
            raise KeysightScopeError(f"{command} argument {key} must be exactly true")


def _normalize_trigger_edge_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-edge":
        return arguments
    allowed = {"query", "source_channel", "level", "slope"}
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-edge: {sorted(unknown)[0]}")
    if "query" in arguments:
        if arguments["query"] is not True:
            raise KeysightScopeError("trigger-edge argument query must be exactly true")
        configure_keys = {"source_channel", "level", "slope"} & set(arguments)
        if configure_keys:
            raise KeysightScopeError(
                "trigger-edge query cannot be combined with configure arguments"
            )
        return dict(arguments)
    return dict(arguments)


def _normalize_trigger_edge_source_worker_arguments(
    command: str,
    arguments: dict[str, Any],
    runtime: WorkerRuntime,
) -> dict[str, Any]:
    if command != "trigger-edge-source":
        return arguments
    allowed = {"query", "source", "source_channel"}
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(
            f"unknown argument for trigger-edge-source: {sorted(unknown)[0]}"
        )
    if "query" in arguments:
        if arguments["query"] is not True:
            raise KeysightScopeError(
                "trigger-edge-source argument query must be exactly true"
            )
        if {"source", "source_channel"} & set(arguments):
            raise KeysightScopeError(
                "trigger-edge-source query cannot be combined with configure arguments"
            )
        return {"query": True}
    has_source = "source" in arguments
    has_channel = "source_channel" in arguments
    if has_source == has_channel:
        raise KeysightScopeError(
            "trigger-edge-source configure requires exactly one of source or source_channel"
        )
    if has_source:
        source = arguments["source"]
        if not isinstance(source, str):
            raise KeysightScopeError("trigger-edge-source argument source must be a string")
        if source not in {"external", "line"}:
            raise KeysightScopeError(
                "trigger-edge-source argument source must be one of: external, line"
            )
        return {"source": source}
    source_channel = arguments["source_channel"]
    if isinstance(source_channel, bool) or not isinstance(source_channel, int):
        raise KeysightScopeError(
            "trigger-edge-source argument source_channel must be an integer"
        )
    try:
        source_channel = validate_analog_channel(
            source_channel, capabilities_for_model(runtime.model)
        )
    except KeysightScopeError as exc:
        raise KeysightScopeError(
            f"trigger-edge-source argument source_channel is invalid: {exc}"
        ) from exc
    return {"source_channel": source_channel}


def _normalize_trigger_glitch_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-pulse-width":
        return arguments
    allowed = {
        "query",
        "channel",
        "polarity",
        "qualifier",
        "time_seconds",
        "min_time_seconds",
        "max_time_seconds",
        "level_volts",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-pulse-width: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-pulse-width argument query must be exactly true")
    normalized = dict(arguments)
    qualifier = normalized.get("qualifier")
    if qualifier == "greater_than":
        normalized["qualifier"] = "greater-than"
    elif qualifier == "less_than":
        normalized["qualifier"] = "less-than"
    return normalized


def _normalize_trigger_runt_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-runt":
        return arguments
    allowed = {
        "query",
        "channel",
        "polarity",
        "qualifier",
        "time_seconds",
        "low_level_volts",
        "high_level_volts",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-runt: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-runt argument query must be exactly true")
    normalized = dict(arguments)
    qualifier = normalized.get("qualifier")
    if qualifier == "greater_than":
        normalized["qualifier"] = "greater-than"
    elif qualifier == "less_than":
        normalized["qualifier"] = "less-than"
    return normalized


def _normalize_trigger_transition_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-transition":
        return arguments
    allowed = {
        "query",
        "channel",
        "slope",
        "qualifier",
        "time_seconds",
        "low_level_volts",
        "high_level_volts",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-transition: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-transition argument query must be exactly true")
    normalized = dict(arguments)
    qualifier = normalized.get("qualifier")
    if qualifier == "greater_than":
        normalized["qualifier"] = "greater-than"
    elif qualifier == "less_than":
        normalized["qualifier"] = "less-than"
    return normalized


def _normalize_trigger_delay_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-delay":
        return arguments
    allowed = {
        "query",
        "arm_channel",
        "arm_slope",
        "trigger_channel",
        "trigger_slope",
        "time_seconds",
        "count",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-delay: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-delay argument query must be exactly true")
    return dict(arguments)


def _normalize_trigger_setup_hold_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-setup-hold":
        return arguments
    allowed = {
        "query",
        "clock_channel",
        "data_channel",
        "slope",
        "setup_time",
        "hold_time",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(
            f"unknown argument for trigger-setup-hold: {sorted(unknown)[0]}"
        )
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-setup-hold argument query must be exactly true")
    return dict(arguments)


def _normalize_trigger_edge_burst_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-edge-burst":
        return arguments
    allowed = {
        "query",
        "source_channel",
        "slope",
        "count",
        "idle_time",
        "level_volts",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(
            f"unknown argument for trigger-edge-burst: {sorted(unknown)[0]}"
        )
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-edge-burst argument query must be exactly true")
    return dict(arguments)


def _normalize_trigger_tv_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-tv":
        return arguments
    allowed = {
        "query",
        "source_channel",
        "standard",
        "mode",
        "line",
        "polarity",
    }
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-tv: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-tv argument query must be exactly true")
    return dict(arguments)


def _normalize_trigger_pattern_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-pattern":
        return arguments
    allowed = {"query", "pattern"}
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-pattern: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-pattern argument query must be exactly true")
    return dict(arguments)


def _normalize_trigger_or_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-or":
        return arguments
    allowed = {"query", "pattern"}
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(f"unknown argument for trigger-or: {sorted(unknown)[0]}")
    if "query" in arguments and arguments["query"] is not True:
        raise KeysightScopeError("trigger-or argument query must be exactly true")
    return dict(arguments)


def _normalize_trigger_holdoff_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command != "trigger-holdoff":
        return arguments
    allowed = {"query", "seconds"}
    unknown = set(arguments) - allowed
    if unknown:
        raise KeysightScopeError(
            f"unknown argument for trigger-holdoff: {sorted(unknown)[0]}"
        )
    if not arguments:
        raise KeysightScopeError("trigger-holdoff requires query or seconds")
    if "query" in arguments:
        if arguments["query"] is not True:
            raise KeysightScopeError(
                "trigger-holdoff argument query must be exactly true"
            )
        if "seconds" in arguments:
            raise KeysightScopeError(
                "trigger-holdoff query cannot be combined with configure arguments"
            )
        return dict(arguments)
    if set(arguments) != {"seconds"}:
        raise KeysightScopeError("trigger-holdoff requires query or seconds")
    seconds = arguments["seconds"]
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        raise KeysightScopeError("trigger-holdoff argument seconds must be a JSON number")
    if not math.isfinite(float(seconds)):
        raise KeysightScopeError("trigger-holdoff argument seconds must be finite")
    return dict(arguments)


def _normalize_trigger_common_worker_arguments(
    command: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if command == "trigger-sweep":
        allowed = {"query", "mode"}
        unknown = set(arguments) - allowed
        if unknown:
            raise KeysightScopeError(
                f"unknown argument for trigger-sweep: {sorted(unknown)[0]}"
            )
        if "query" in arguments:
            if arguments["query"] is not True:
                raise KeysightScopeError(
                    "trigger-sweep argument query must be exactly true"
                )
            if "mode" in arguments:
                raise KeysightScopeError(
                    "trigger-sweep query cannot be combined with configure arguments"
                )
            return dict(arguments)
        return dict(arguments)

    if command in {"trigger-noise-reject", "trigger-hf-reject"}:
        allowed = {"query", "enabled"}
        unknown = set(arguments) - allowed
        if unknown:
            raise KeysightScopeError(
                f"unknown argument for {command}: {sorted(unknown)[0]}"
            )
        if "query" in arguments:
            if arguments["query"] is not True:
                raise KeysightScopeError(f"{command} argument query must be exactly true")
            if "enabled" in arguments:
                raise KeysightScopeError(
                    f"{command} query cannot be combined with configure arguments"
                )
            return dict(arguments)
        normalized = dict(arguments)
        if "enabled" in normalized:
            if not isinstance(normalized["enabled"], bool):
                raise KeysightScopeError(f"{command} argument enabled must be a boolean")
            normalized["enabled"] = "true" if normalized["enabled"] else "false"
        return normalized

    if command == "trigger-edge-coupling":
        allowed = {"query", "coupling"}
        unknown = set(arguments) - allowed
        if unknown:
            raise KeysightScopeError(
                f"unknown argument for trigger-edge-coupling: {sorted(unknown)[0]}"
            )
        if "query" in arguments:
            if arguments["query"] is not True:
                raise KeysightScopeError("trigger-edge-coupling argument query must be exactly true")
            if "coupling" in arguments:
                raise KeysightScopeError(
                    "trigger-edge-coupling query cannot be combined with configure arguments"
                )
            return dict(arguments)
        if "coupling" not in arguments:
            raise KeysightScopeError("trigger-edge-coupling configure requires coupling")
        coupling = arguments["coupling"]
        if not isinstance(coupling, str):
            raise KeysightScopeError("trigger-edge-coupling argument coupling must be a string")
        if coupling not in {"ac", "dc", "lf-reject"}:
            raise KeysightScopeError(
                "trigger-edge-coupling argument coupling must be one of: ac, dc, lf-reject"
            )
        return {"coupling": coupling}

    if command == "trigger-edge-reject":
        allowed = {"query", "reject"}
        unknown = set(arguments) - allowed
        if unknown:
            raise KeysightScopeError(
                f"unknown argument for trigger-edge-reject: {sorted(unknown)[0]}"
            )
        if "query" in arguments:
            if arguments["query"] is not True:
                raise KeysightScopeError("trigger-edge-reject argument query must be exactly true")
            if "reject" in arguments:
                raise KeysightScopeError(
                    "trigger-edge-reject query cannot be combined with configure arguments"
                )
            return dict(arguments)
        if "reject" not in arguments:
            raise KeysightScopeError("trigger-edge-reject configure requires reject")
        reject = arguments["reject"]
        if not isinstance(reject, str):
            raise KeysightScopeError("trigger-edge-reject argument reject must be a string")
        if reject not in {"off", "lf-reject", "hf-reject"}:
            raise KeysightScopeError(
                "trigger-edge-reject argument reject must be one of: off, lf-reject, hf-reject"
            )
        return {"reject": reject}

    return arguments


def arguments_to_argv(arguments: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    for key, value in arguments.items():
        option = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                argv.append(option)
            continue
        if isinstance(value, list):
            for item in value:
                argv.extend([option, str(item)])
            continue
        if value is None:
            continue
        argv.extend([option, str(value)])
    return argv


def _make_handler(runtime: WorkerRuntime):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            print(fmt % args, file=sys.stderr, flush=True)

        def do_GET(self) -> None:
            if self.path != "/status":
                self._send(404, {"status": "error", "error": {"message": "not found"}})
                return
            self._send(200, runtime.status_payload())

        def do_POST(self) -> None:
            if self.path == "/command":
                self._handle_command()
                return
            if self.path == "/stop":
                self._handle_stop()
                return
            self._send(404, {"status": "error", "error": {"message": "not found"}})

        def _handle_command(self) -> None:
            command_echo: str | None = None
            job_id_echo: str | None = None
            try:
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(raw.decode("utf-8") if raw else "{}")
                command_echo, job_id_echo = _command_identity(body)
                command, arguments, job_id = validate_command_request(body)
                parse_domain_command(command, arguments, runtime)
            except json.JSONDecodeError as exc:
                self._send(
                    400,
                    _command_error_envelope(
                        "malformed JSON",
                        command_echo,
                        job_id_echo,
                        exc,
                    ),
                )
                return
            except KeysightScopeError as exc:
                self._send(
                    400,
                    _command_error_envelope(str(exc), command_echo, job_id_echo, exc),
                )
                return
            if runtime.stopping:
                self._send(
                    409,
                    _command_rejected_envelope(
                        "worker_stopping", command_echo, job_id_echo
                    ),
                )
                return
            if runtime.queue.full():
                self._send(
                    429,
                    _command_rejected_envelope("queue_full", command_echo, job_id_echo),
                )
                return
            worker_job_id = uuid4().hex
            artifact_path = runtime.artifact_root / runtime.run_id / worker_job_id
            job = WorkerJob(
                command=command,
                arguments=arguments,
                job_id=job_id,
                worker_job_id=worker_job_id,
                artifact_path=artifact_path,
                request_time=_now(),
                accepted_time=_now(),
            )
            try:
                artifact_path.mkdir(parents=True, exist_ok=False)
                _atomic_json(artifact_path / "request.json", body)
                with runtime.lock:
                    runtime.jobs[worker_job_id] = job
                runtime.queue.put_nowait(job)
                with runtime.lock:
                    runtime.accepted += 1
            except Full:
                with runtime.lock:
                    runtime.jobs.pop(worker_job_id, None)
                self._send(
                    429,
                    _command_rejected_envelope("queue_full", command_echo, job_id_echo),
                )
                return
            response = {
                "status": "accepted",
                "command": command,
                "job_id": job_id,
                "worker_job_id": worker_job_id,
                "artifact_path": str(artifact_path),
            }
            self._send(202, response)

        def _handle_stop(self) -> None:
            runtime.stopping = True
            cancelled = []
            with runtime.lock:
                for job in runtime.jobs.values():
                    if job.state == "queued":
                        _finish_cancelled_job(runtime, job, started=False)
                        cancelled.append(job.worker_job_id)
                    elif job.state == "running":
                        job.cancel_requested = True
            self._send(
                202,
                {
                    "status": "accepted",
                    "run_id": runtime.run_id,
                    "cancelled_jobs": cancelled,
                    "active_job": runtime.active_job_id,
                },
            )
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _job_loop(runtime: WorkerRuntime) -> None:
    while True:
        job = runtime.queue.get()
        with runtime.lock:
            if job.state == "cancelled":
                runtime.queue.task_done()
                continue
            job.state = "running"
            job.started_time = _now()
            runtime.active_job_id = job.worker_job_id
        runtime.emit("job_started", worker_job_id=job.worker_job_id, command=job.command)
        try:
            parsed = parse_domain_command(job.command, job.arguments, runtime)
            parsed = parse_domain_command(
                job.command, job.arguments, runtime, job.artifact_path
            )
            _guard_no_overwrite(parsed, job.artifact_path)
            payload, exit_code = scope_cli._execute_json_command(parsed)
            job.result = payload
            job.exit_code = exit_code
            job.state = (
                "cancelled"
                if job.cancel_requested or runtime.stopping
                else "succeeded" if exit_code == 0 else "failed"
            )
            if job.state == "cancelled":
                job.exit_code = 3
                job.error = {"type": "cancelled", "message": "cancelled by stop"}
            if not payload.get("ok", False):
                err = payload.get("error")
                job.error = err if isinstance(err, dict) else None
        except Exception as exc:
            job.exit_code = 3
            job.state = "failed"
            job.error = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            job.finished_time = _now()
            _write_result(runtime, job)
            with runtime.lock:
                runtime.active_job_id = None
                runtime.last_job_id = job.worker_job_id
                if job.state == "succeeded":
                    runtime.succeeded += 1
                elif job.state == "cancelled":
                    runtime.cancelled += 1
                else:
                    runtime.failed += 1
            runtime.emit(
                "job_finished",
                worker_job_id=job.worker_job_id,
                command=job.command,
                state=job.state,
                ok=job.state == "succeeded",
                exit_code=job.exit_code,
                job_id=job.job_id,
                artifact_path=str(job.artifact_path),
                result_path=str(job.artifact_path / "result.json"),
                error=job.error,
            )
            runtime.queue.task_done()


def _write_result(runtime: WorkerRuntime, job: WorkerJob) -> None:
    files: list[Any] = []
    result: Any = None
    if isinstance(job.result, dict):
        files_value = job.result.get("files")
        if isinstance(files_value, list):
            files = _existing_files(files_value)
        result = job.result.get("result")
    payload = {
        "schema_version": 1,
        "run_id": runtime.run_id,
        "worker_job_id": job.worker_job_id,
        "job_id": job.job_id,
        "command": job.command,
        "state": job.state,
        "ok": job.state == "succeeded",
        "accepted_at": job.accepted_time,
        "started_at": job.started_time,
        "finished_at": job.finished_time,
        "result": result,
        "files": files,
        "error": job.error,
        "exit_code": job.exit_code,
    }
    _atomic_json(job.artifact_path / "result.json", payload)


def _event_payload(runtime: WorkerRuntime, event: str, **values: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "event": event,
        "run_id": runtime.run_id,
        "timestamp_utc": _now(),
        **values,
    }
    if event == "ready":
        payload.update(
            {
                "service": "keysight-scopes",
                "host": runtime.host,
                "port": runtime.port,
                "mode": runtime.mode,
                "model": runtime.model,
                "resource": runtime.resource,
            }
        )
        payload.pop("trigger_url", None)
    elif event == "job_started":
        job = runtime.jobs.get(str(payload.get("worker_job_id")))
        payload.setdefault("job_id", None if job is None else job.job_id)
        payload.setdefault(
            "artifact_path", None if job is None else str(job.artifact_path)
        )
    elif event == "job_finished":
        state = payload.get("state")
        if state not in {"succeeded", "failed", "cancelled"}:
            raise ValueError(f"invalid job_finished state: {state}")
        if payload.get("ok") is True and state != "succeeded":
            raise ValueError("only succeeded job_finished events may use ok=true")
        payload.setdefault("error", None)
    elif event == "summary":
        payload.setdefault("ok", runtime.fatal_error is None)
        payload.setdefault("fatal_error", runtime.fatal_error)
        payload.update(
            {
                "accepted": runtime.accepted,
                "succeeded": runtime.succeeded,
                "failed": runtime.failed,
                "cancelled": runtime.cancelled,
            }
        )
    return payload


def _finish_cancelled_job(
    runtime: WorkerRuntime, job: WorkerJob, *, started: bool
) -> None:
    job.state = "cancelled"
    job.started_time = job.started_time if started else None
    job.finished_time = _now()
    job.exit_code = 3
    job.error = {"type": "cancelled", "message": "cancelled by stop"}
    _write_result(runtime, job)
    runtime.cancelled += 1
    runtime.last_job_id = job.worker_job_id
    runtime.emit(
        "job_finished",
        worker_job_id=job.worker_job_id,
        job_id=job.job_id,
        command=job.command,
        state=job.state,
        ok=False,
        exit_code=job.exit_code,
        artifact_path=str(job.artifact_path),
        result_path=str(job.artifact_path / "result.json"),
        error=job.error,
    )


def _apply_worker_job_paths(args: argparse.Namespace, job_dir: Path) -> None:
    command = args.command
    if command == "capture":
        csv_path = _worker_path(job_dir, getattr(args, "csv_path", None), "capture.csv")
        meta_value = getattr(args, "meta_path", None)
        meta_path = _worker_path(job_dir, meta_value, "capture_meta.json")
        setattr(args, "csv_path", str(csv_path))
        setattr(args, "meta_path", str(meta_path))
        plot_value = getattr(args, "plot_path", None)
        if plot_value is not None:
            setattr(args, "plot_path", str(_worker_path(job_dir, plot_value, None)))
    elif command == "screenshot":
        output_path = _worker_path(job_dir, getattr(args, "output_path", None), "screen.png")
        setattr(args, "output_path", str(output_path))
    elif command in {"capture-batch", "measure-log", "smoke", "acquisition-check"}:
        output_dir = _worker_path(job_dir, getattr(args, "output_dir", None), ".")
        setattr(args, "output_dir", str(output_dir))


def _worker_path(job_dir: Path, value: Any, default_name: str | None) -> Path:
    if value is None:
        if default_name is None:
            raise KeysightScopeError("worker output path default is unavailable")
        return job_dir if default_name == "." else job_dir / default_name
    path = Path(str(value))
    return path if path.is_absolute() else job_dir / path


def _guard_no_overwrite(args: argparse.Namespace, job_dir: Path) -> None:
    for path in _planned_artifact_paths(args):
        if path == job_dir / "request.json" or path == job_dir / "result.json":
            continue
        if path.exists():
            raise KeysightScopeError(f"output path already exists: {path}")


def _planned_artifact_paths(args: argparse.Namespace) -> list[Path]:
    command = args.command
    if command == "capture":
        paths = [Path(args.csv_path), Path(args.meta_path)]
        if args.plot_path is not None:
            paths.append(Path(args.plot_path))
        return paths
    if command == "screenshot":
        return [Path(args.output_path)]
    if command == "capture-batch":
        output_dir = Path(args.output_dir)
        return [output_dir / "manifest.json", output_dir / "scpi.log"]
    if command == "measure-log":
        output_dir = Path(args.output_dir)
        return [
            output_dir / "measurements.csv",
            output_dir / "manifest.json",
            output_dir / "scpi.log",
        ]
    if command == "smoke":
        output_dir = Path(args.output_dir)
        return [
            output_dir / "report.json",
            output_dir / "scpi.log",
            output_dir / "capture.csv",
            output_dir / "capture_meta.json",
            output_dir / "screen.png",
        ]
    if command == "acquisition-check":
        output_dir = Path(args.output_dir)
        return [output_dir / "report.json", output_dir / "scpi.log"]
    return []


def _existing_files(files: list[Any]) -> list[Any]:
    existing = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if isinstance(path, str) and Path(path).exists():
            existing.append(entry)
    return existing


def _job_summary(job: WorkerJob | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "worker_job_id": job.worker_job_id,
        "job_id": job.job_id,
        "command": job.command,
        "state": job.state,
        "artifact_path": str(job.artifact_path),
        "exit_code": job.exit_code,
    }


def _http_request(
    args: argparse.Namespace,
    path: str,
    *,
    method: str,
    body: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    url = f"http://{args.host}:{args.port}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    timeout = args.timeout_ms / 1000
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), response.status
    except urlerror.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return payload, exc.code


def _client_print(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if getattr(args, "client_json", False) or getattr(args, "format", None) == "json":
        scope_cli._write_json(_client_json_payload(args, payload))
        return
    status = payload.get("status", "ok")
    print(f"status: {status}")
    for key in ("command", "job_id", "worker_job_id", "artifact_path", "run_id"):
        if key in payload and payload[key] is not None:
            print(f"{key}: {payload[key]}")


def _client_error(
    args: argparse.Namespace,
    exit_code: int,
    message: str,
    exc: Exception | None = None,
) -> int:
    payload = {
        "ok": False,
        "status": "error",
        "command": getattr(args, "worker_command", None)
        if getattr(args, "command", None) == "send-command"
        else getattr(args, "command", None),
        "error": {
            "type": type(exc).__name__ if exc is not None else "ClientError",
            "message": message if exc is None else f"{message}: {exc}",
        },
    }
    _client_print(args, payload)
    return exit_code


def _client_json_payload(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.setdefault("schema_version", 1)
    result.setdefault("timestamp_utc", _now())
    if getattr(args, "command", None) == "send-command":
        result.setdefault("command", getattr(args, "worker_command", None))
    else:
        result.setdefault("command", getattr(args, "command", None))
    return result


def _status_exit(status: int) -> int:
    return 2 if status == 400 else 3


def _command_identity(body: Any) -> tuple[str | None, str | None]:
    if not isinstance(body, dict):
        return None, None
    command = body.get("command")
    job_id = body.get("job_id")
    return (
        command if isinstance(command, str) else None,
        job_id if isinstance(job_id, str) else None,
    )


def _command_error_envelope(
    message: str,
    command: str | None,
    job_id: str | None,
    exc: Exception | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "command": command,
        "job_id": job_id,
        "error": "validation_error",
        "message": message,
        "error_detail": {
            "type": type(exc).__name__ if exc is not None else "ValidationError",
            "message": message,
        },
    }


def _command_rejected_envelope(
    reason: str, command: str | None, job_id: str | None
) -> dict[str, Any]:
    return {
        "status": "rejected",
        "command": command,
        "job_id": job_id,
        "reason": reason,
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
