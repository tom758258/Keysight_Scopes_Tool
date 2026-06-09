"""Command line interface for oscilloscope checks."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Sequence

from .acquisition import (
    acquisition_count_command,
    acquisition_count_query,
    acquisition_type_command,
    acquisition_type_query,
    normalize_acquisition_type,
    validate_acquisition_count,
)
from .batch import (
    BatchManifest,
    batch_capture_paths,
    batch_iso_timestamp,
    capture_actual_points,
    capture_batch_scpi_logging,
    idn_manifest_dict,
    prepare_batch_output_dir,
    relative_manifest_path,
    system_error_manifest_dict,
    write_batch_manifest,
)
from .capabilities import ScopeCapabilities, capabilities_for_model
from .channel import (
    channel_bandwidth_limit_command,
    channel_bandwidth_limit_query,
    channel_coupling_command,
    channel_coupling_query,
    channel_display_command,
    channel_display_query,
    channel_offset_command,
    channel_offset_query,
    channel_probe_ratio_command,
    channel_probe_ratio_query,
    channel_scale_command,
    channel_scale_query,
    normalize_channel_coupling,
    validate_analog_channel,
    validate_channel_offset,
    validate_channel_scale,
    validate_probe_ratio,
)
from .errors import KeysightScopeError
from .idn import parse_idn
from .measurements import (
    MEASUREMENT_ITEM_CHOICES,
    is_pair_measurement_item,
    measurement_query,
    normalize_measurement_item,
    pair_measurement_query,
)
from .screenshot import (
    DEFAULT_SCREENSHOT_BACKGROUND,
    SCREENSHOT_TIMEOUT_MS,
    hardcopy_inksaver_command,
    hardcopy_inksaver_for_background,
    screenshot_data_query,
    write_screenshot_png,
)
from .scope import KeysightScope
from .simulator_backend import SimulatorBackend, simulator_idn
from .timebase import (
    timebase_position_command,
    timebase_position_query,
    timebase_scale_command,
    timebase_scale_query,
    validate_timebase_position,
    validate_timebase_scale,
)
from .trigger import (
    edge_trigger_level_command,
    edge_trigger_level_query,
    edge_trigger_slope_command,
    edge_trigger_slope_query,
    edge_trigger_source_command,
    edge_trigger_source_query,
    normalize_edge_slope,
    trigger_mode_edge_command,
    validate_trigger_level,
)
from .visa_backend import list_visa_resources
from .waveform import (
    MultiChannelWaveformCapture,
    SUPPORTED_WAVEFORM_POINTS,
    WORD_BYTE_ORDER,
    WORD_UNSIGNED,
    WaveformCapture,
    waveform_byte_order_command,
    validate_waveform_channels,
    validate_waveform_points,
    waveform_data_query,
    waveform_format_byte_command,
    waveform_format_word_command,
    waveform_points_command,
    waveform_preamble_query,
    waveform_source_command,
    waveform_unsigned_command,
    write_waveform_csv,
    write_waveform_metadata,
    write_waveforms_csv,
    write_waveforms_metadata,
)

_CONTROL_COMMANDS = {
    "run": ("run", ":RUN"),
    "stop": ("stop", ":STOP"),
    "single": ("single", ":SINGle"),
}
_CAPTURE_DEFAULT_TIMEZONE = timezone(timedelta(hours=8), name="UTC+8")
_JSON_RECORD: dict[str, object] | None = None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `scope-tool` command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "json_output", False):
        return _run_json_command(args)

    try:
        return _dispatch_command(args)
    except KeysightScopeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("missing command")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scope-tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_resources_parser = subparsers.add_parser(
        "list-resources",
        help="list VISA resource strings reported by the selected backend",
    )
    list_resources_parser.add_argument(
        "--visa-library",
        default=None,
        help="optional PyVISA library argument, such as @py",
    )
    list_resources_parser.add_argument(
        "--live-only",
        action="store_true",
        help="only print resources that open and respond to *IDN?",
    )
    list_resources_parser.add_argument(
        "--log-scpi",
        action="store_true",
        help="write SCPI command and response logs to stderr when --live-only is used",
    )
    list_resources_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="write a single machine-readable JSON object to stdout",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="open one resource and verify basic communication with *IDN?",
    )
    _add_scope_connection_args(verify_parser)

    check_error_parser = subparsers.add_parser(
        "check-error",
        help="read the oscilloscope system error queue",
    )
    _add_scope_connection_args(check_error_parser)
    check_error_parser.add_argument(
        "--all",
        dest="drain",
        action="store_true",
        help="read until no error is returned or --max-reads is reached",
    )
    check_error_parser.add_argument(
        "--max-reads",
        type=_positive_int,
        default=30,
        help="maximum reads when --all is used",
    )

    run_parser = subparsers.add_parser("run", help="start repetitive acquisitions")
    _add_scope_connection_args(run_parser)

    stop_parser = subparsers.add_parser("stop", help="stop acquisitions")
    _add_scope_connection_args(stop_parser)

    single_parser = subparsers.add_parser(
        "single",
        help="start one single acquisition without waiting",
    )
    _add_scope_connection_args(single_parser)

    channel_display_parser = subparsers.add_parser(
        "channel-display",
        help="enable, disable, or query one analog channel display",
    )
    _add_scope_connection_args(channel_display_parser)
    channel_display_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    display_action = channel_display_parser.add_mutually_exclusive_group(required=True)
    display_action.add_argument(
        "--on",
        dest="display_action",
        action="store_const",
        const="on",
        help="turn the channel display on",
    )
    display_action.add_argument(
        "--off",
        dest="display_action",
        action="store_const",
        const="off",
        help="turn the channel display off",
    )
    display_action.add_argument(
        "--query",
        dest="display_action",
        action="store_const",
        const="query",
        help="query the channel display state",
    )

    channel_scale_parser = subparsers.add_parser(
        "channel-scale",
        help="set or query one analog channel vertical scale",
    )
    _add_scope_connection_args(channel_scale_parser)
    channel_scale_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    scale_action = channel_scale_parser.add_mutually_exclusive_group(required=True)
    scale_action.add_argument(
        "--volts-per-division",
        dest="scale_value",
        type=_positive_float,
        help="vertical scale in volts per division",
    )
    scale_action.add_argument(
        "--query",
        dest="scale_query",
        action="store_true",
        help="query the channel vertical scale",
    )

    channel_offset_parser = subparsers.add_parser(
        "channel-offset",
        help="set or query one analog channel vertical offset",
    )
    _add_scope_connection_args(channel_offset_parser)
    channel_offset_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    offset_action = channel_offset_parser.add_mutually_exclusive_group(required=True)
    offset_action.add_argument(
        "--volts",
        dest="offset_value",
        type=_finite_float,
        help="vertical offset in volts",
    )
    offset_action.add_argument(
        "--query",
        dest="offset_query",
        action="store_true",
        help="query the channel vertical offset",
    )

    channel_coupling_parser = subparsers.add_parser(
        "channel-coupling",
        help="set or query one analog channel input coupling",
    )
    _add_scope_connection_args(channel_coupling_parser)
    channel_coupling_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    coupling_action = channel_coupling_parser.add_mutually_exclusive_group(required=True)
    coupling_action.add_argument(
        "--coupling",
        dest="coupling_value",
        choices=("ac", "dc"),
        help="input coupling",
    )
    coupling_action.add_argument(
        "--query",
        dest="coupling_query",
        action="store_true",
        help="query the channel input coupling",
    )

    channel_probe_parser = subparsers.add_parser(
        "channel-probe",
        help="set or query one analog channel probe ratio",
    )
    _add_scope_connection_args(channel_probe_parser)
    channel_probe_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    probe_action = channel_probe_parser.add_mutually_exclusive_group(required=True)
    probe_action.add_argument(
        "--ratio",
        dest="probe_ratio",
        type=_probe_ratio_float,
        help="probe attenuation ratio, such as 1, 10, or 100",
    )
    probe_action.add_argument(
        "--query",
        dest="probe_query",
        action="store_true",
        help="query the channel probe ratio",
    )

    channel_bandwidth_limit_parser = subparsers.add_parser(
        "channel-bandwidth-limit",
        help="enable, disable, or query one analog channel bandwidth limit",
    )
    _add_scope_connection_args(channel_bandwidth_limit_parser)
    channel_bandwidth_limit_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    bandwidth_action = channel_bandwidth_limit_parser.add_mutually_exclusive_group(
        required=True
    )
    bandwidth_action.add_argument(
        "--on",
        dest="bandwidth_action",
        action="store_const",
        const="on",
        help="turn the channel bandwidth limit on",
    )
    bandwidth_action.add_argument(
        "--off",
        dest="bandwidth_action",
        action="store_const",
        const="off",
        help="turn the channel bandwidth limit off",
    )
    bandwidth_action.add_argument(
        "--query",
        dest="bandwidth_action",
        action="store_const",
        const="query",
        help="query the channel bandwidth limit state",
    )

    timebase_scale_parser = subparsers.add_parser(
        "timebase-scale",
        help="set or query horizontal scale",
    )
    _add_scope_connection_args(timebase_scale_parser)
    scale_action = timebase_scale_parser.add_mutually_exclusive_group(required=True)
    scale_action.add_argument(
        "--seconds-per-division",
        dest="timebase_scale_value",
        type=_positive_timebase_float,
        help="horizontal scale in seconds per division",
    )
    scale_action.add_argument(
        "--query",
        dest="timebase_scale_query",
        action="store_true",
        help="query the horizontal scale",
    )

    timebase_position_parser = subparsers.add_parser(
        "timebase-position",
        help="set or query horizontal position",
    )
    _add_scope_connection_args(timebase_position_parser)
    position_action = timebase_position_parser.add_mutually_exclusive_group(required=True)
    position_action.add_argument(
        "--seconds",
        dest="timebase_position_value",
        type=_finite_timebase_float,
        help="horizontal position in seconds",
    )
    position_action.add_argument(
        "--query",
        dest="timebase_position_query",
        action="store_true",
        help="query the horizontal position",
    )

    edge_trigger_parser = subparsers.add_parser(
        "edge-trigger",
        help="configure or query analog edge trigger settings",
    )
    _add_scope_connection_args(edge_trigger_parser)
    edge_trigger_parser.add_argument(
        "--query",
        dest="edge_query",
        action="store_true",
        help="query analog edge trigger source, level, and slope",
    )
    edge_trigger_parser.add_argument(
        "--source-channel",
        type=_positive_int,
        default=None,
        help="analog channel used as the edge trigger source",
    )
    edge_trigger_parser.add_argument(
        "--level",
        type=_trigger_level_float,
        default=None,
        help="edge trigger level in volts",
    )
    edge_trigger_parser.add_argument(
        "--slope",
        choices=("positive", "negative", "either", "alternate"),
        default=None,
        help="edge trigger slope",
    )

    measure_parser = subparsers.add_parser(
        "measure",
        help="query one read-only measurement item for one or two analog channels",
    )
    _add_scope_connection_args(measure_parser)
    measure_parser.add_argument(
        "--channel",
        type=_positive_int,
        default=None,
        help="analog channel number, validated against the detected scope model",
    )
    measure_parser.add_argument(
        "--source-channel",
        type=_positive_int,
        default=None,
        help="source analog channel number; --channel is a compatibility alias",
    )
    measure_parser.add_argument(
        "--reference-channel",
        type=_positive_int,
        default=None,
        help="reference analog channel number for phase or delay measurements",
    )
    measure_parser.add_argument(
        "--item",
        choices=MEASUREMENT_ITEM_CHOICES,
        required=True,
        help="measurement item to query",
    )
    measure_parser.add_argument(
        "--time",
        dest="time_s",
        type=_measurement_finite_float,
        default=None,
        help="trigger-relative time in seconds for y_at_x",
    )
    measure_parser.add_argument(
        "--level",
        type=_measurement_finite_float,
        default=None,
        help="voltage level for time_at_value",
    )
    measure_parser.add_argument(
        "--slope",
        choices=("positive", "negative"),
        default=None,
        help="edge or crossing slope for time_at_edge and time_at_value",
    )
    measure_parser.add_argument(
        "--occurrence",
        type=_positive_int,
        default=None,
        help="positive edge or crossing occurrence for time_at_edge and time_at_value",
    )

    capture_parser = subparsers.add_parser(
        "capture",
        help="capture one or more analog channel waveforms to CSV and metadata JSON",
    )
    _add_scope_connection_args(capture_parser)
    capture_parser.add_argument(
        "--channel",
        type=_capture_channel_arg,
        action="append",
        required=True,
        help=(
            "analog channel number; repeat for aligned multi-channel CSV output, "
            "or use all for every analog channel on the detected model"
        ),
    )
    capture_parser.add_argument(
        "--points",
        type=_waveform_points_arg,
        default=1000,
        help="waveform point count; supported values: 1000, 5000, 10000",
    )
    capture_parser.add_argument(
        "--format",
        dest="waveform_format",
        choices=("byte", "word"),
        default="byte",
        help="waveform transfer format; defaults to byte",
    )
    capture_parser.add_argument(
        "--csv",
        dest="csv_path",
        default=None,
        help="output CSV path; defaults to data/<UTC+8 timestamp>.csv",
    )
    capture_parser.add_argument(
        "--meta",
        dest="meta_path",
        default=None,
        help="output metadata JSON path; defaults to <csv stem>_meta.json",
    )

    capture_batch_parser = subparsers.add_parser(
        "capture-batch",
        help="capture a finite batch of analog waveforms into one output directory",
    )
    _add_scope_connection_args(capture_batch_parser)
    capture_batch_parser.add_argument(
        "--channel",
        type=_capture_channel_arg,
        action="append",
        required=True,
        help=(
            "analog channel number; repeat for aligned multi-channel CSV output, "
            "or use all for every analog channel on the detected model"
        ),
    )
    capture_batch_parser.add_argument(
        "--points",
        type=_waveform_points_arg,
        default=1000,
        help="waveform point count; supported values: 1000, 5000, 10000",
    )
    capture_batch_parser.add_argument(
        "--format",
        dest="waveform_format",
        choices=("byte", "word"),
        default="byte",
        help="waveform transfer format; defaults to byte",
    )
    capture_batch_parser.add_argument(
        "--count",
        type=_positive_int,
        required=True,
        help="finite number of waveform captures to run",
    )
    capture_batch_parser.add_argument(
        "--interval-seconds",
        type=_nonnegative_finite_float,
        default=0.0,
        help="seconds to sleep between captures; defaults to 0",
    )
    capture_batch_parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "output directory; defaults to data/captures/<UTC+8 timestamp>. "
            "If provided, it must not exist or must be empty"
        ),
    )

    screenshot_parser = subparsers.add_parser(
        "screenshot",
        help="capture the current oscilloscope screen to a PNG file",
    )
    _add_scope_connection_args(screenshot_parser)
    screenshot_parser.add_argument(
        "--output",
        dest="output_path",
        default=None,
        help="output PNG path; defaults to data/<UTC+8 timestamp>.png",
    )
    screenshot_parser.add_argument(
        "--background",
        choices=("black", "white"),
        default=DEFAULT_SCREENSHOT_BACKGROUND,
        help="screenshot background color; defaults to black",
    )

    acquisition_parser = subparsers.add_parser(
        "acquisition",
        help="configure or query acquisition type and average count",
    )
    _add_scope_connection_args(acquisition_parser)
    acquisition_parser.add_argument(
        "--query",
        dest="acq_query",
        action="store_true",
        help="query acquisition type and average count",
    )
    acquisition_parser.add_argument(
        "--type",
        dest="acq_type",
        default=None,
        help=(
            "acquisition type: normal/norm, average/aver/avg, "
            "high_resolution/high-resolution/hresolution/hres, peak/peak_detect/peak-detect"
        ),
    )
    acquisition_parser.add_argument(
        "--count",
        dest="acq_count",
        type=_positive_int,
        default=None,
        help="average count (only valid with --type average)",
    )
    return parser


def _add_scope_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--resource",
        default=None,
        help="VISA resource string. Defaults to KEYSIGHT_SCOPE_RESOURCE.",
    )
    parser.add_argument(
        "--visa-library",
        default=None,
        help="optional PyVISA library argument, such as @py",
    )
    parser.add_argument(
        "--log-scpi",
        action="store_true",
        help="write SCPI command and response logs to stderr",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="write a single machine-readable JSON object to stdout",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="use the deterministic hardware-free simulator backend",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate arguments and report the planned SCPI without opening a backend",
    )
    parser.add_argument(
        "--model",
        default="DSOX4024A",
        help="model profile used by --simulate or --dry-run; defaults to DSOX4024A",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="explicitly opt in to real instrument access for agent workflows",
    )


def _dispatch_command(args: argparse.Namespace) -> int:
    if args.command == "list-resources":
        return _cmd_list_resources(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "check-error":
        return _cmd_check_error(args)
    if args.command in _CONTROL_COMMANDS:
        return _cmd_control(args)
    if args.command == "channel-display":
        return _cmd_channel_display(args)
    if args.command == "channel-scale":
        return _cmd_channel_scale(args)
    if args.command == "channel-offset":
        return _cmd_channel_offset(args)
    if args.command == "channel-coupling":
        return _cmd_channel_coupling(args)
    if args.command == "channel-probe":
        return _cmd_channel_probe(args)
    if args.command == "channel-bandwidth-limit":
        return _cmd_channel_bandwidth_limit(args)
    if args.command == "timebase-scale":
        return _cmd_timebase_scale(args)
    if args.command == "timebase-position":
        return _cmd_timebase_position(args)
    if args.command == "edge-trigger":
        return _cmd_edge_trigger(args)
    if args.command == "measure":
        return _cmd_measure(args)
    if args.command == "capture":
        return _cmd_capture(args)
    if args.command == "capture-batch":
        return _cmd_capture_batch(args)
    if args.command == "screenshot":
        return _cmd_screenshot(args)
    if args.command == "acquisition":
        return _cmd_acquisition(args)
    raise KeysightScopeError("missing command")



_LAST_BACKEND = None


def _resolve_cli_mode(args: argparse.Namespace) -> str:
    if getattr(args, "simulate", False) and getattr(args, "dry_run", False):
        raise KeysightScopeError("--simulate cannot be combined with --dry-run")
    if getattr(args, "simulate", False):
        capabilities_for_model(args.model)
        return "simulate"
    if getattr(args, "dry_run", False):
        capabilities_for_model(args.model)
        return "dry_run"
    return "live"


def _open_scope(args: argparse.Namespace, resource: str) -> KeysightScope:
    global _LAST_BACKEND
    mode = _resolve_cli_mode(args)
    if mode == "simulate":
        backend = SimulatorBackend(model=args.model, resource_name=resource)
        _LAST_BACKEND = backend
        return KeysightScope(backend)
    scope = KeysightScope.open(resource, visa_library=args.visa_library)
    _LAST_BACKEND = getattr(scope, "backend", None)
    if _JSON_RECORD is not None:
        _JSON_RECORD["backend"] = getattr(scope.backend, "backend", None)
    return scope


def _run_json_command(args: argparse.Namespace) -> int:
    global _JSON_RECORD
    try:
        mode = _resolve_cli_mode(args)
        if mode == "dry_run":
            payload = _dry_run_payload(args)
            _write_json(payload)
            return 0

        _JSON_RECORD = {"result": {}, "files": [], "system_error": None}
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = _dispatch_command(args)
        payload = _json_envelope(args, ok=(code == 0), mode=mode)
        _apply_json_record(payload)
        result = payload.setdefault("result", {})
        if isinstance(result, dict):
            result["human_output"] = buffer.getvalue().splitlines()
        payload["scpi"]["sent"] = _backend_history()
        _write_json(payload)
        return code
    except KeysightScopeError as exc:
        payload = _json_envelope(args, ok=False, mode=_safe_mode(args))
        _apply_json_record(payload)
        payload["error"] = {"type": type(exc).__name__, "message": str(exc)}
        payload["scpi"]["sent"] = _backend_history()
        _write_json(payload)
        return 1
    finally:
        _JSON_RECORD = None


def _safe_mode(args: argparse.Namespace) -> str:
    try:
        return _resolve_cli_mode(args)
    except KeysightScopeError:
        return "dry_run" if getattr(args, "dry_run", False) else "simulate" if getattr(args, "simulate", False) else "live"


def _json_envelope(args: argparse.Namespace, *, ok: bool, mode: str) -> dict[str, object]:
    resource = None
    if hasattr(args, "resource"):
        resource = args.resource or (f"SIM::{args.model}::INSTR" if mode == "simulate" else f"DRY::{args.model}::INSTR" if mode == "dry_run" else os.environ.get("KEYSIGHT_SCOPE_RESOURCE"))
    idn = None
    capabilities = None
    if mode in {"simulate", "dry_run"} and hasattr(args, "model"):
        idn = _idn_json(simulator_idn(args.model))
        try:
            capabilities = _capabilities_json(capabilities_for_model(args.model))
        except KeysightScopeError:
            capabilities = None
    return {
        "ok": ok,
        "command": args.command,
        "mode": mode,
        "resource": resource,
        "backend": "Keysight simulator" if mode == "simulate" else None,
        "idn": idn,
        "capabilities": capabilities,
        "scpi": {"planned": [], "sent": []},
        "result": {},
        "files": [],
        "system_error": None,
        "error": None,
    }


def _dry_run_payload(args: argparse.Namespace) -> dict[str, object]:
    payload = _json_envelope(args, ok=True, mode="dry_run")
    capabilities = capabilities_for_model(args.model)
    planned, files, result = _dry_run_plan(args, capabilities)
    payload["scpi"]["planned"] = planned
    payload["files"] = files
    payload["result"] = result
    return payload


def _dry_run_plan(args: argparse.Namespace, capabilities: ScopeCapabilities) -> tuple[list[str], list[dict[str, str]], dict[str, object]]:
    command = args.command
    if command == "verify":
        return ["*IDN?"], [], {
            "idn": _idn_json(simulator_idn(args.model)),
            "capabilities": _capabilities_json(capabilities),
            "backend": None,
            "timeout_ms": None,
        }
    if command == "check-error":
        count = args.max_reads if args.drain else 1
        return [":SYSTem:ERRor?"] * count, [], {"drain": bool(args.drain), "max_reads": count, "entries": []}
    if command in _CONTROL_COMMANDS:
        action, scpi = _CONTROL_COMMANDS[command]
        return [scpi, ":SYSTem:ERRor?"], [], {"action": action, "command": scpi}
    if command == "channel-display":
        channel = validate_analog_channel(args.channel, capabilities)
        query = args.display_action == "query"
        enabled = None if query else args.display_action == "on"
        planned = [channel_display_query(channel)] if query else [channel_display_command(channel, enabled)]
        return planned + [":SYSTem:ERRor?"], [], {"channel": channel, "operation": "query" if query else "set", "command": planned[0], "display": enabled}
    if command == "channel-scale":
        channel = validate_analog_channel(args.channel, capabilities)
        scale = None if args.scale_query else validate_channel_scale(args.scale_value)
        planned = [channel_scale_query(channel)] if args.scale_query else [channel_scale_command(channel, scale)]
        return planned + [":SYSTem:ERRor?"], [], {"channel": channel, "operation": "query" if args.scale_query else "set", "command": planned[0], "volts_per_division": scale}
    if command == "channel-offset":
        channel = validate_analog_channel(args.channel, capabilities)
        offset = None if args.offset_query else validate_channel_offset(args.offset_value)
        planned = [channel_offset_query(channel)] if args.offset_query else [channel_offset_command(channel, offset)]
        return planned + [":SYSTem:ERRor?"], [], {"channel": channel, "operation": "query" if args.offset_query else "set", "command": planned[0], "volts": offset}
    if command == "channel-coupling":
        channel = validate_analog_channel(args.channel, capabilities)
        coupling = None if args.coupling_query else normalize_channel_coupling(args.coupling_value)
        planned = [channel_coupling_query(channel)] if args.coupling_query else [channel_coupling_command(channel, coupling)]
        return planned + [":SYSTem:ERRor?"], [], {"channel": channel, "operation": "query" if args.coupling_query else "set", "command": planned[0], "coupling": coupling}
    if command == "channel-probe":
        channel = validate_analog_channel(args.channel, capabilities)
        ratio = None if args.probe_query else validate_probe_ratio(args.probe_ratio)
        planned = [channel_probe_ratio_query(channel)] if args.probe_query else [channel_probe_ratio_command(channel, ratio)]
        return planned + [":SYSTem:ERRor?"], [], {"channel": channel, "operation": "query" if args.probe_query else "set", "command": planned[0], "probe_ratio": ratio}
    if command == "channel-bandwidth-limit":
        channel = validate_analog_channel(args.channel, capabilities)
        query = args.bandwidth_action == "query"
        enabled = None if query else args.bandwidth_action == "on"
        planned = [channel_bandwidth_limit_query(channel)] if query else [channel_bandwidth_limit_command(channel, enabled)]
        return planned + [":SYSTem:ERRor?"], [], {"channel": channel, "operation": "query" if query else "set", "command": planned[0], "bandwidth_limit": enabled}
    if command == "timebase-scale":
        scale = None if args.timebase_scale_query else validate_timebase_scale(args.timebase_scale_value)
        planned = [timebase_scale_query()] if args.timebase_scale_query else [timebase_scale_command(scale)]
        return planned + [":SYSTem:ERRor?"], [], {"operation": "query" if args.timebase_scale_query else "set", "command": planned[0], "seconds_per_division": scale}
    if command == "timebase-position":
        position = None if args.timebase_position_query else validate_timebase_position(args.timebase_position_value)
        planned = [timebase_position_query()] if args.timebase_position_query else [timebase_position_command(position)]
        return planned + [":SYSTem:ERRor?"], [], {"operation": "query" if args.timebase_position_query else "set", "command": planned[0], "position_seconds": position}
    if command == "edge-trigger":
        if args.edge_query:
            commands = [edge_trigger_source_query(), edge_trigger_level_query(), edge_trigger_slope_query()]
            return commands + [":SYSTem:ERRor?"], [], {"operation": "query", "commands": commands}
        if args.source_channel is None or args.level is None or args.slope is None:
            raise KeysightScopeError("edge-trigger configure requires --source-channel, --level, and --slope")
        channel = validate_analog_channel(args.source_channel, capabilities)
        slope = normalize_edge_slope(args.slope)
        commands = [trigger_mode_edge_command(), edge_trigger_source_command(channel), edge_trigger_level_command(args.level), edge_trigger_slope_command(slope)]
        return commands + [":SYSTem:ERRor?"], [], {"operation": "set", "commands": commands, "source_channel": channel, "level_volts": args.level, "slope": slope}
    if command == "measure":
        item = normalize_measurement_item(args.item)
        kwargs = _measurement_query_kwargs(args, item)
        result: dict[str, object] = {"item": item, "parameters": kwargs}
        if is_pair_measurement_item(item):
            source, reference = _resolve_pair_measurement_channels(args, capabilities, item)
            planned = [pair_measurement_query(item, source, reference, capabilities=capabilities, **kwargs)]
            result.update({"channel": source, "reference_channel": reference})
        else:
            channel = _resolve_single_measurement_channel(args, capabilities)
            planned = [measurement_query(item, channel, capabilities=capabilities, **kwargs)]
            result["channel"] = channel
        return planned + [":SYSTem:ERRor?"], [], result
    if command in {"capture", "capture-batch"}:
        channels = _resolve_capture_channels(args.channel, capabilities)
        points = validate_waveform_points(args.points, capabilities)
        planned = _planned_waveform_scpi(channels, args.waveform_format, points) + [":SYSTem:ERRor?"]
        files = _planned_capture_files(args, command)
        result = {"channels": list(channels), "points": points, "format": args.waveform_format.upper(), "files": files}
        if command == "capture":
            result["requested_points"] = points
        else:
            result.update({"status": "planned", "requested_count": args.count, "completed_count": 0, "captures": [], "manifest_path": files[0]["path"], "scpi_log_path": files[1]["path"]})
        return planned, files, result
    if command == "screenshot":
        png_path = Path(args.output_path) if args.output_path else _default_screenshot_path()
        files = [{"kind": "png", "path": str(png_path)}]
        return [hardcopy_inksaver_command(hardcopy_inksaver_for_background(args.background)), screenshot_data_query(), ":SYSTem:ERRor?"], files, {"format": "PNG", "background": args.background, "timeout_ms": SCREENSHOT_TIMEOUT_MS, "files": files, "png_path": str(png_path)}
    if command == "acquisition":
        if args.acq_query and (args.acq_type is not None or args.acq_count is not None):
            raise KeysightScopeError("--query cannot be combined with --type or --count")
        if args.acq_query:
            commands = [acquisition_type_query(), acquisition_count_query()]
            return commands + [":SYSTem:ERRor?"], [], {"operation": "query", "commands": commands}
        if args.acq_type is None:
            raise KeysightScopeError("acquisition command requires --query or --type")
        normalized = normalize_acquisition_type(args.acq_type)
        planned = [acquisition_type_command(normalized)]
        count = None
        if args.acq_count is not None:
            count = validate_acquisition_count(args.acq_count)
            planned.append(acquisition_count_command(count))
        return planned + [":SYSTem:ERRor?"], [], {"operation": "set", "commands": planned, "type": args.acq_type, "scpi_type": normalized, "count": count}
    return [], [], {}


def _planned_waveform_scpi(channels: Sequence[int], waveform_format: str, points: int) -> list[str]:
    planned: list[str] = []
    for channel in channels:
        planned.append(waveform_source_command(channel))
        if waveform_format == "word":
            planned.extend([waveform_format_word_command(), waveform_byte_order_command(WORD_BYTE_ORDER), waveform_unsigned_command(WORD_UNSIGNED)])
        else:
            planned.append(waveform_format_byte_command())
        planned.extend([waveform_points_command(points), waveform_preamble_query(), waveform_data_query()])
    return planned


def _planned_capture_files(args: argparse.Namespace, command: str) -> list[dict[str, str]]:
    if command == "capture":
        csv_path = Path(args.csv_path) if args.csv_path is not None else _default_capture_csv_path()
        meta_path = Path(args.meta_path) if args.meta_path is not None else csv_path.with_name(f"{csv_path.stem}_meta.json")
        return [{"kind": "csv", "path": str(csv_path)}, {"kind": "metadata", "path": str(meta_path)}]
    output_dir = Path(args.output_dir) if args.output_dir is not None else Path("data") / "captures" / "DRY-RUN"
    files = [{"kind": "manifest", "path": str(output_dir / "manifest.json")}, {"kind": "scpi_log", "path": str(output_dir / "scpi.log")}]
    for index in range(1, args.count + 1):
        csv_path, meta_path = batch_capture_paths(output_dir, index, args.count)
        files.extend([{"kind": "csv", "path": str(csv_path)}, {"kind": "metadata", "path": str(meta_path)}])
    return files


def _backend_history() -> list[str]:
    if _LAST_BACKEND is None:
        return []
    return list(getattr(_LAST_BACKEND, "history", []))


def _capabilities_json(capabilities: ScopeCapabilities | None) -> dict[str, object] | None:
    if capabilities is None:
        return None
    return {
        "series": capabilities.series,
        "analog_channels": capabilities.analog_channels,
        "default_waveform_points": capabilities.default_waveform_points,
        "safe_max_waveform_points": capabilities.safe_max_waveform_points,
        "supports_screenshot": capabilities.supports_screenshot,
    }


def _idn_json(raw: str) -> dict[str, str | None]:
    idn = parse_idn(raw)
    return {"raw": idn.raw, "vendor": idn.vendor, "model": idn.model, "serial": idn.serial, "firmware": idn.firmware, "series": idn.series}


def _write_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _apply_json_record(payload: dict[str, object]) -> None:
    if _JSON_RECORD is None:
        return
    result = _JSON_RECORD.get("result")
    if isinstance(result, dict):
        payload_result = payload.setdefault("result", {})
        if isinstance(payload_result, dict):
            payload_result.update(result)
    for key in ("idn", "capabilities", "backend", "system_error"):
        if key in _JSON_RECORD:
            payload[key] = _JSON_RECORD[key]
    files = _JSON_RECORD.get("files")
    if isinstance(files, list):
        payload["files"] = files


def _json_update_result(**values: object) -> None:
    if _JSON_RECORD is None:
        return
    result = _JSON_RECORD.setdefault("result", {})
    if isinstance(result, dict):
        result.update(values)


def _json_set_files(files: list[dict[str, object]]) -> None:
    if _JSON_RECORD is not None:
        _JSON_RECORD["files"] = files


def _json_record_scope(scope: KeysightScope, idn) -> None:
    if _JSON_RECORD is None:
        return
    _JSON_RECORD["idn"] = _idn_object_json(idn)
    _JSON_RECORD["capabilities"] = _capabilities_json(scope.capabilities)
    _JSON_RECORD["backend"] = getattr(scope.backend, "backend", None)


def _json_record_system_error(entry) -> None:
    data = _system_error_json(entry)
    if _JSON_RECORD is not None:
        _JSON_RECORD["system_error"] = data


def _system_error_json(entry) -> dict[str, object]:
    return {
        "code": entry.code,
        "message": entry.message,
        "raw": entry.raw,
        "is_error": entry.is_error,
    }


def _idn_object_json(idn) -> dict[str, str | None]:
    return {
        "raw": idn.raw,
        "vendor": idn.vendor,
        "model": idn.model,
        "serial": idn.serial,
        "firmware": idn.firmware,
        "series": idn.series,
    }


def _scope_backend_json(scope: KeysightScope) -> dict[str, object]:
    return {
        "backend": getattr(scope.backend, "backend", None),
        "timeout_ms": getattr(scope.backend, "timeout", None),
    }


def _measurement_result_json(result, *, parameters: dict[str, object]) -> dict[str, object]:
    return {
        "item": result.item,
        "channel": result.channel,
        "reference_channel": result.reference_channel,
        "value": result.value,
        "unit": result.unit,
        "valid": result.valid,
        "raw_value": result.raw_value,
        "reason": result.reason,
        "parameters": parameters,
    }


def _waveform_preamble_json(preamble) -> dict[str, object]:
    return {
        "raw": preamble.raw,
        "format_code": preamble.format_code,
        "type_code": preamble.type_code,
        "points": preamble.points,
        "count": preamble.count,
        "x_increment": preamble.x_increment,
        "x_origin": preamble.x_origin,
        "x_reference": preamble.x_reference,
        "y_increment": preamble.y_increment,
        "y_origin": preamble.y_origin,
        "y_reference": preamble.y_reference,
    }


def _waveform_capture_summary(capture: WaveformCapture | MultiChannelWaveformCapture) -> dict[str, object]:
    if isinstance(capture, MultiChannelWaveformCapture):
        summaries = [_single_waveform_capture_summary(item) for item in capture.captures]
        return {
            "actual_points": {f"CH{item['channel']}": item["actual_points"] for item in summaries},
            "captures": summaries,
        }
    single = _single_waveform_capture_summary(capture)
    return {"actual_points": single["actual_points"], "captures": [single]}


def _single_waveform_capture_summary(capture: WaveformCapture) -> dict[str, object]:
    return {
        "channel": capture.channel,
        "requested_points": capture.requested_points,
        "actual_points": len(capture.raw_samples),
        "format": capture.format_name,
        "preamble": _waveform_preamble_json(capture.preamble),
        "byte_order": capture.byte_order,
        "unsigned": capture.unsigned,
    }


def _cmd_list_resources(args: argparse.Namespace) -> int:
    listing = list_visa_resources(visa_library=args.visa_library)
    print(f"PyVISA backend: {listing.backend}")
    _json_update_result(
        backend=listing.backend,
        resources=list(listing.resources),
        live_only=bool(args.live_only),
        live_resources=[],
    )
    if _JSON_RECORD is not None:
        _JSON_RECORD["backend"] = listing.backend
    if args.live_only:
        _configure_scpi_logging(args)
        return _print_live_resources(listing.resources, visa_library=args.visa_library)

    print("Resources:")
    if not listing.resources:
        print("  <none>")
        return 0

    for resource in listing.resources:
        print(f"  {resource}")
    return 0


def _print_live_resources(resources: tuple[str, ...], visa_library: str | None) -> int:
    print("Live resources:")
    live_count = 0
    live_resources = []
    for resource in resources:
        try:
            with KeysightScope.open(resource, visa_library=visa_library) as scope:
                idn = scope.query_idn()
        except KeysightScopeError:
            continue

        live_count += 1
        live_resources.append({"resource": resource, "idn": _idn_object_json(idn)})
        print(f"  {resource}")
        print(f"    IDN: {idn.raw}")

    if live_count == 0:
        print("  <none>")
    _json_update_result(live_resources=live_resources)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _json_update_result(idn=_idn_object_json(idn), capabilities=_capabilities_json(scope.capabilities), **_scope_backend_json(scope))
        _print_session_header(scope, resource)
        print(f"Raw IDN: {idn.raw}")
        print(f"Vendor: {idn.vendor}")
        print(f"Model: {idn.model}")
        print(f"Serial: {idn.serial}")
        print(f"Firmware: {idn.firmware}")
        print(f"Series: {idn.series or 'unknown'}")
        _print_capabilities(scope.capabilities)
    return 0


def _cmd_check_error(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        _print_session_header(scope, resource)
        if args.drain:
            entries = scope.drain_system_errors(max_reads=args.max_reads)
            entry_json = [_system_error_json(entry) for entry in entries]
            _json_update_result(drain=True, max_reads=args.max_reads, entries=entry_json)
            if entries:
                _json_record_system_error(entries[-1])
            for index, entry in enumerate(entries, start=1):
                print(f"System error {index}: {entry.format()}")
            return 1 if any(entry.is_error for entry in entries) else 0

        entry = scope.query_system_error()
        _json_update_result(drain=False, max_reads=1, entries=[_system_error_json(entry)])
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_control(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)
    method_name, command = _CONTROL_COMMANDS[args.command]

    with _open_scope(args, resource) as scope:
        _print_session_header(scope, resource)
        getattr(scope, method_name)()
        _json_update_result(action=method_name, command=command)
        print(f"Command: {command}")
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_display(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        if args.display_action == "query":
            command = channel_display_query(channel)
            print(f"Planned query: CH{channel} display state")
            enabled = scope.query_channel_display(channel)
            _json_update_result(channel=channel, operation="query", command=command, display=enabled)
            print(f"Command: {command}")
            print(f"Display: {'ON' if enabled else 'OFF'}")
        else:
            enabled = args.display_action == "on"
            command = channel_display_command(channel, enabled)
            print(f"Planned change: CH{channel} display {'ON' if enabled else 'OFF'}")
            scope.set_channel_display(channel, enabled)
            _json_update_result(channel=channel, operation="set", command=command, display=enabled)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_scale(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        if args.scale_query:
            command = channel_scale_query(channel)
            print(f"Planned query: CH{channel} scale")
            scale = scope.query_channel_scale(channel)
            _json_update_result(channel=channel, operation="query", command=command, volts_per_division=scale)
            print(f"Command: {command}")
            print(f"Scale V/div: {scale:.12g}")
        else:
            scale = validate_channel_scale(args.scale_value)
            command = channel_scale_command(channel, scale)
            print(f"Planned change: CH{channel} scale {scale:.12g} V/div")
            scope.set_channel_scale(channel, scale)
            _json_update_result(channel=channel, operation="set", command=command, volts_per_division=scale)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_offset(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        if args.offset_query:
            command = channel_offset_query(channel)
            print(f"Planned query: CH{channel} offset")
            offset = scope.query_channel_offset(channel)
            _json_update_result(channel=channel, operation="query", command=command, volts=offset)
            print(f"Command: {command}")
            print(f"Offset V: {offset:.12g}")
        else:
            offset = validate_channel_offset(args.offset_value)
            command = channel_offset_command(channel, offset)
            print(f"Planned change: CH{channel} offset {offset:.12g} V")
            scope.set_channel_offset(channel, offset)
            _json_update_result(channel=channel, operation="set", command=command, volts=offset)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_coupling(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        if args.coupling_query:
            command = channel_coupling_query(channel)
            print(f"Planned query: CH{channel} coupling")
            coupling = scope.query_channel_coupling(channel)
            _json_update_result(channel=channel, operation="query", command=command, coupling=coupling)
            print(f"Command: {command}")
            print(f"Coupling: {coupling.upper()}")
        else:
            coupling = normalize_channel_coupling(args.coupling_value)
            command = channel_coupling_command(channel, coupling)
            print(f"Planned change: CH{channel} coupling {coupling.upper()}")
            scope.set_channel_coupling(channel, coupling)
            _json_update_result(channel=channel, operation="set", command=command, coupling=coupling)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_probe(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        if args.probe_query:
            command = channel_probe_ratio_query(channel)
            print(f"Planned query: CH{channel} probe ratio")
            ratio = scope.query_channel_probe_ratio(channel)
            _json_update_result(channel=channel, operation="query", command=command, probe_ratio=ratio)
            print(f"Command: {command}")
            print(f"Probe ratio: {ratio:.12g}")
        else:
            ratio = validate_probe_ratio(args.probe_ratio)
            command = channel_probe_ratio_command(channel, ratio)
            print(f"Planned change: CH{channel} probe ratio {ratio:.12g}")
            scope.set_channel_probe_ratio(channel, ratio)
            _json_update_result(channel=channel, operation="set", command=command, probe_ratio=ratio)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_bandwidth_limit(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        if args.bandwidth_action == "query":
            command = channel_bandwidth_limit_query(channel)
            print(f"Planned query: CH{channel} bandwidth limit")
            enabled = scope.query_channel_bandwidth_limit(channel)
            _json_update_result(channel=channel, operation="query", command=command, bandwidth_limit=enabled)
            print(f"Command: {command}")
            print(f"Bandwidth limit: {'ON' if enabled else 'OFF'}")
        else:
            enabled = args.bandwidth_action == "on"
            command = channel_bandwidth_limit_command(channel, enabled)
            state = "ON" if enabled else "OFF"
            print(f"Planned change: CH{channel} bandwidth limit {state}")
            scope.set_channel_bandwidth_limit(channel, enabled)
            _json_update_result(channel=channel, operation="set", command=command, bandwidth_limit=enabled)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_timebase_scale(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        if args.timebase_scale_query:
            command = timebase_scale_query()
            print("Planned query: timebase scale")
            scale = scope.query_timebase_scale()
            _json_update_result(operation="query", command=command, seconds_per_division=scale)
            print(f"Command: {command}")
            print(f"Timebase scale s/div: {scale:.12g}")
        else:
            scale = validate_timebase_scale(args.timebase_scale_value)
            command = timebase_scale_command(scale)
            print(f"Planned change: timebase scale {scale:.12g} s/div")
            scope.set_timebase_scale(scale)
            _json_update_result(operation="set", command=command, seconds_per_division=scale)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_timebase_position(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        if args.timebase_position_query:
            command = timebase_position_query()
            print("Planned query: timebase position")
            position = scope.query_timebase_position()
            _json_update_result(operation="query", command=command, position_seconds=position)
            print(f"Command: {command}")
            print(f"Timebase position s: {position:.12g}")
        else:
            position = validate_timebase_position(args.timebase_position_value)
            command = timebase_position_command(position)
            print(f"Planned change: timebase position {position:.12g} s")
            scope.set_timebase_position(position)
            _json_update_result(operation="set", command=command, position_seconds=position)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_edge_trigger(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        if args.edge_query:
            if any(value is not None for value in (args.source_channel, args.level, args.slope)):
                raise KeysightScopeError(
                    "--query cannot be combined with --source-channel, --level, or --slope"
                )
            print("Planned query: edge trigger source, level, and slope")
            state = scope.query_edge_trigger()
            _json_update_result(
                operation="query",
                commands=[edge_trigger_source_query(), edge_trigger_level_query(), edge_trigger_slope_query()],
                source_channel=state.source_channel,
                level_volts=state.level_volts,
                slope=state.slope,
            )
            print(f"Command: {edge_trigger_source_query()}")
            print(f"Source: CH{state.source_channel}")
            print(f"Command: {edge_trigger_level_query()}")
            print(f"Level V: {state.level_volts:.12g}")
            print(f"Command: {edge_trigger_slope_query()}")
            print(f"Slope: {state.slope}")
        else:
            if args.source_channel is None or args.level is None or args.slope is None:
                raise KeysightScopeError(
                    "edge-trigger requires --source-channel, --level, and --slope unless --query is used"
                )
            channel = validate_analog_channel(args.source_channel, scope.capabilities)
            level = validate_trigger_level(args.level)
            slope = normalize_edge_slope(args.slope)
            print(
                f"Planned change: edge trigger CH{channel}, level {level:.12g} V, "
                f"slope {args.slope}"
            )
            scope.configure_edge_trigger(channel, level, slope)
            _json_update_result(
                operation="set",
                commands=[trigger_mode_edge_command(), edge_trigger_source_command(channel), edge_trigger_level_command(level), edge_trigger_slope_command(slope)],
                source_channel=channel,
                level_volts=level,
                slope=slope,
            )
            print(f"Command: {trigger_mode_edge_command()}")
            print(f"Command: {edge_trigger_source_command(channel)}")
            print(f"Command: {edge_trigger_level_command(level)}")
            print(f"Command: {edge_trigger_slope_command(slope)}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_measure(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        item = normalize_measurement_item(args.item)
        measurement_kwargs = _measurement_query_kwargs(args, item)
        if is_pair_measurement_item(item):
            source_channel, reference_channel = _resolve_pair_measurement_channels(
                args, scope.capabilities, item
            )
            command = pair_measurement_query(
                item,
                source_channel,
                reference_channel,
                capabilities=scope.capabilities,
                **measurement_kwargs,
            )
            print(
                f"Planned query: CH{source_channel} to CH{reference_channel} "
                f"{item} measurement"
            )
            result = scope.query_pair_measurement(source_channel, reference_channel, item)
        else:
            channel = _resolve_single_measurement_channel(args, scope.capabilities)
            command = measurement_query(
                item,
                channel,
                capabilities=scope.capabilities,
                **measurement_kwargs,
            )
            print(
                f"Planned query: CH{channel} {item} measurement"
                f"{_format_measurement_parameters(measurement_kwargs)}"
            )
            result = scope.query_measurement(channel, item, **measurement_kwargs)

        _json_update_result(command=command, **_measurement_result_json(result, parameters=measurement_kwargs))
        print(f"Command: {command}")
        print(f"Measurement: {result.item}")
        print(f"Channel: {result.channel}")
        if result.reference_channel is not None:
            print(f"Reference channel: {result.reference_channel}")
        print(f"Valid: {'true' if result.valid else 'false'}")
        if result.valid:
            value = result.value
            if value is None:
                raise KeysightScopeError("measurement result was marked valid without a numeric value")
            print(f"Value {result.unit}: {value:.12g}")
        else:
            print("Value: unavailable")
        print(f"Raw response: {result.raw_value}")
        if result.reason is not None:
            print(f"Reason: {result.reason}")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error or not result.valid else 0


def _cmd_capture(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    csv_path = Path(args.csv_path) if args.csv_path is not None else _default_capture_csv_path()
    meta_path = Path(args.meta_path) if args.meta_path is not None else csv_path.with_name(
        f"{csv_path.stem}_meta.json"
    )

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channels = _resolve_capture_channels(args.channel, scope.capabilities)
        points = validate_waveform_points(args.points, scope.capabilities)
        waveform_format = args.waveform_format.upper()
        if len(channels) == 1:
            channel = channels[0]
            print(f"Planned capture: CH{channel}, {points} points, {waveform_format} format")
            if args.waveform_format == "word":
                capture: WaveformCapture | MultiChannelWaveformCapture = (
                    scope.capture_waveform_word(channel, points=points)
                )
            else:
                capture = scope.capture_waveform_byte(channel, points=points)
        else:
            print(
                f"Planned capture: {_format_channel_list(channels)}, "
                f"{points} points, {waveform_format} format"
            )
            if args.waveform_format == "word":
                capture = scope.capture_waveforms_word(channels, points=points)
            else:
                capture = scope.capture_waveforms_byte(channels, points=points)
        _print_waveform_capture_commands(channels, args.waveform_format, points)
        written_csv = _write_capture_csv(capture, csv_path)
        written_meta = _write_capture_metadata(capture, meta_path, idn=idn, resource=resource)
        files = [{"kind": "csv", "path": str(written_csv)}, {"kind": "metadata", "path": str(written_meta)}]
        _json_set_files(files)
        _json_update_result(
            channels=list(channels),
            requested_points=points,
            format=waveform_format,
            files=files,
            **_waveform_capture_summary(capture),
        )
        print(_format_actual_points(capture))
        print(f"CSV: {written_csv}")
        print(f"Metadata: {written_meta}")
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_capture_batch(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    output_dir = prepare_batch_output_dir(args.output_dir)
    manifest_path = output_dir / "manifest.json"
    scpi_log_path = output_dir / "scpi.log"
    manifest = BatchManifest(
        start_time=batch_iso_timestamp(),
        end_time=None,
        status="running",
        resource=resource,
        backend=None,
        timeout_ms=None,
        idn=None,
        channels=[],
        points=args.points,
        format=args.waveform_format.upper(),
        requested_count=args.count,
        interval_seconds=args.interval_seconds,
    )

    try:
        with capture_batch_scpi_logging(
            scpi_log_path,
            echo_to_stderr=args.log_scpi,
        ):
            with _open_scope(args, resource) as scope:
                idn = scope.query_idn()
                _json_record_scope(scope, idn)
                manifest.backend = getattr(scope.backend, "backend", None)
                manifest.timeout_ms = getattr(scope.backend, "timeout", None)
                manifest.idn = idn_manifest_dict(idn)

                _print_session_header(scope, resource)
                print(f"Model: {idn.model}")
                print(f"Series: {idn.series or 'unknown'}")
                if scope.capabilities is None:
                    print("Capabilities: unavailable for this model")
                    manifest.status = "error"
                    manifest.error = "Capabilities unavailable for this model"
                    manifest.end_time = batch_iso_timestamp()
                    _write_batch_manifest(manifest, manifest_path)
                    print(f"Output directory: {output_dir}")
                    print(f"SCPI log: {scpi_log_path}")
                    print(f"Manifest: {manifest_path}")
                    return 1

                channels = _resolve_capture_channels(args.channel, scope.capabilities)
                points = validate_waveform_points(args.points, scope.capabilities)
                waveform_format = args.waveform_format.upper()
                manifest.channels = list(channels)
                manifest.points = points
                manifest.format = waveform_format

                _json_set_files([
                    {"kind": "manifest", "path": str(manifest_path)},
                    {"kind": "scpi_log", "path": str(scpi_log_path)},
                ])
                _json_update_result(
                    status="running",
                    channels=list(channels),
                    format=waveform_format,
                    points=points,
                    requested_count=args.count,
                    completed_count=0,
                    manifest_path=str(manifest_path),
                    scpi_log_path=str(scpi_log_path),
                    captures=[],
                )
                print(
                    f"Planned batch capture: {_format_channel_list(channels)}, "
                    f"{points} points, {waveform_format} format, "
                    f"{args.count} captures"
                )
                print(f"Interval seconds: {args.interval_seconds}")
                print(f"Output directory: {output_dir}")
                _print_waveform_capture_commands(channels, args.waveform_format, points)

                for index in range(1, args.count + 1):
                    print(f"Capture {index}/{args.count}:")
                    capture = _capture_waveform(scope, channels, args.waveform_format, points)
                    csv_path, meta_path = batch_capture_paths(output_dir, index, args.count)
                    written_csv = _write_capture_csv(capture, csv_path)
                    written_meta = _write_capture_metadata(
                        capture,
                        meta_path,
                        idn=idn,
                        resource=resource,
                    )
                    entry = scope.query_system_error()
                    _json_record_system_error(entry)
                    capture_entry = {
                        "index": index,
                        "csv": relative_manifest_path(written_csv, output_dir),
                        "metadata": relative_manifest_path(written_meta, output_dir),
                        "actual_points": capture_actual_points(capture),
                        "system_error": system_error_manifest_dict(entry),
                    }
                    manifest.captures.append(capture_entry)
                    if _JSON_RECORD is not None:
                        result = _JSON_RECORD.setdefault("result", {})
                        if isinstance(result, dict):
                            entries = result.setdefault("captures", [])
                            if isinstance(entries, list):
                                json_capture_entry = dict(capture_entry)
                                if isinstance(capture, WaveformCapture):
                                    json_capture_entry["actual_points"] = {f"CH{capture.channel}": len(capture.raw_samples)}
                                entries.append(json_capture_entry)
                            result["completed_count"] = len(entries) if isinstance(entries, list) else index
                        files = _JSON_RECORD.setdefault("files", [])
                        if isinstance(files, list):
                            files.extend([
                                {"kind": "csv", "path": str(written_csv)},
                                {"kind": "metadata", "path": str(written_meta)},
                            ])
                    print(_format_actual_points(capture))
                    print(f"CSV: {written_csv}")
                    print(f"Metadata: {written_meta}")
                    print(f"System error: {entry.format()}")
                    if entry.is_error:
                        manifest.status = "instrument_error"
                        manifest.end_time = batch_iso_timestamp()
                        _json_update_result(status=manifest.status, manifest_path=str(manifest_path), scpi_log_path=str(scpi_log_path))
                        _write_batch_manifest(manifest, manifest_path)
                        print(f"SCPI log: {scpi_log_path}")
                        print(f"Manifest: {manifest_path}")
                        return 1
                    if index < args.count and args.interval_seconds > 0:
                        time.sleep(args.interval_seconds)

                manifest.status = "completed"
                manifest.end_time = batch_iso_timestamp()
                _json_update_result(status=manifest.status, completed_count=len(manifest.captures), manifest_path=str(manifest_path), scpi_log_path=str(scpi_log_path))
                _write_batch_manifest(manifest, manifest_path)
                print(f"SCPI log: {scpi_log_path}")
                print(f"Manifest: {manifest_path}")
                return 0
    except KeyboardInterrupt:
        manifest.status = "interrupted"
        manifest.end_time = batch_iso_timestamp()
        manifest.error = "KeyboardInterrupt"
        _json_update_result(status=manifest.status, error=manifest.error, completed_count=len(manifest.captures))
        _write_batch_manifest_best_effort(manifest, manifest_path)
        print("error: interrupted", file=sys.stderr)
        return 130
    except KeysightScopeError as exc:
        if manifest.status == "running":
            manifest.status = "error"
            manifest.end_time = batch_iso_timestamp()
            manifest.error = str(exc)
            _json_update_result(status=manifest.status, error=manifest.error, completed_count=len(manifest.captures))
            _write_batch_manifest_best_effort(manifest, manifest_path)
        raise
    except OSError as exc:
        manifest.status = "error"
        manifest.end_time = batch_iso_timestamp()
        manifest.error = str(exc)
        _write_batch_manifest_best_effort(manifest, manifest_path)
        raise KeysightScopeError(
            _format_plain_output_file_error("SCPI log", scpi_log_path, exc)
        ) from exc


def _cmd_screenshot(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    output_path = (
        Path(args.output_path) if args.output_path is not None else _default_screenshot_path()
    )

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        background = args.background
        print(f"Planned capture: current screen PNG image with {background} background")
        print(f"Screenshot timeout ms: {SCREENSHOT_TIMEOUT_MS} (temporary)")
        capture = scope.capture_screenshot_png(background=background)
        print(f"Command: {hardcopy_inksaver_command(hardcopy_inksaver_for_background(background))}")
        print(f"Command: {screenshot_data_query()}")
        written_png = _write_screenshot_png(capture, output_path)
        files = [{"kind": "png", "path": str(written_png)}]
        _json_set_files(files)
        _json_update_result(
            format=capture.format_name,
            palette=capture.palette,
            background=capture.background,
            byte_count=len(capture.data),
            timeout_ms=SCREENSHOT_TIMEOUT_MS,
            png_path=str(written_png),
            files=files,
        )
        print(f"Format: {capture.format_name}")
        print(f"Palette: {capture.palette}")
        print(f"Background: {capture.background}")
        print(f"Bytes: {len(capture.data)}")
        print(f"PNG: {written_png}")
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_acquisition(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    if args.acq_query and (args.acq_type is not None or args.acq_count is not None):
        raise KeysightScopeError("--query cannot be combined with --type or --count")

    if args.acq_count is not None:
        if args.acq_type is None:
            raise KeysightScopeError("--count can only be used with --type average")
        if normalize_acquisition_type(args.acq_type) != "AVERage":
            raise KeysightScopeError("--count can only be used with --type average")

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        if args.acq_query:
            print("Planned query: acquisition type and average count")
            config = scope.query_acquisition_config()
            _json_update_result(operation="query", type=config.type, count=config.count, commands=[acquisition_type_query(), acquisition_count_query()])
            print(f"Acquisition type: {config.type}")
            print(f"Average count: {config.count}")
            print(f"Command: {acquisition_type_query()}")
            print(f"Command: {acquisition_count_query()}")
        elif args.acq_type is not None:
            normalized_type = normalize_acquisition_type(args.acq_type)
            print(f"Planned change: acquisition type {args.acq_type}")
            print(f"Command: {acquisition_type_command(normalized_type)}")
            scope.set_acquisition_type(args.acq_type)
            _json_update_result(operation="set", type=args.acq_type, scpi_type=normalized_type, count=None, commands=[acquisition_type_command(normalized_type)])
            if args.acq_count is not None:
                validated_count = validate_acquisition_count(args.acq_count)
                print(f"Planned change: acquisition average count {validated_count}")
                print(f"Command: {acquisition_count_command(validated_count)}")
                scope.set_acquisition_count(validated_count)
                _json_update_result(operation="set", type=args.acq_type, scpi_type=normalized_type, count=validated_count, commands=[acquisition_type_command(normalized_type), acquisition_count_command(validated_count)])
        else:
            raise KeysightScopeError("acquisition command requires --query or --type")

        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _default_capture_csv_path(now: datetime | None = None) -> Path:
    if now is None:
        capture_time = datetime.now(_CAPTURE_DEFAULT_TIMEZONE)
    elif now.tzinfo is None:
        capture_time = now.replace(tzinfo=_CAPTURE_DEFAULT_TIMEZONE)
    else:
        capture_time = now.astimezone(_CAPTURE_DEFAULT_TIMEZONE)

    return Path("data") / capture_time.strftime("%Y-%m-%d-%H-%M-%S.csv")


def _default_screenshot_path(now: datetime | None = None) -> Path:
    if now is None:
        capture_time = datetime.now(_CAPTURE_DEFAULT_TIMEZONE)
    elif now.tzinfo is None:
        capture_time = now.replace(tzinfo=_CAPTURE_DEFAULT_TIMEZONE)
    else:
        capture_time = now.astimezone(_CAPTURE_DEFAULT_TIMEZONE)

    return Path("data") / capture_time.strftime("%Y-%m-%d-%H-%M-%S.png")


def _print_waveform_capture_commands(
    channels: Sequence[int], waveform_format: str, points: int
) -> None:
    for channel in channels:
        print(f"Command: {waveform_source_command(channel)}")
        if waveform_format == "word":
            print(f"Command: {waveform_format_word_command()}")
            print(f"Command: {waveform_byte_order_command(WORD_BYTE_ORDER)}")
            print(f"Command: {waveform_unsigned_command(WORD_UNSIGNED)}")
        else:
            print(f"Command: {waveform_format_byte_command()}")
        print(f"Command: {waveform_points_command(points)}")
        print(f"Command: {waveform_preamble_query()}")
        print(f"Command: {waveform_data_query()}")


def _format_channel_list(channels: Sequence[int]) -> str:
    return ", ".join(f"CH{channel}" for channel in channels)


def _format_actual_points(capture: WaveformCapture | MultiChannelWaveformCapture) -> str:
    if isinstance(capture, MultiChannelWaveformCapture):
        per_channel = ", ".join(
            f"CH{item.channel}={len(item.raw_samples)}" for item in capture.captures
        )
        return f"Actual points: {per_channel}"
    return f"Actual points: {len(capture.raw_samples)}"


def _capture_waveform(
    scope: KeysightScope,
    channels: Sequence[int],
    waveform_format: str,
    points: int,
) -> WaveformCapture | MultiChannelWaveformCapture:
    normalized_format = waveform_format.lower()
    if len(channels) == 1:
        channel = channels[0]
        if normalized_format == "word":
            return scope.capture_waveform_word(channel, points=points)
        return scope.capture_waveform_byte(channel, points=points)

    if normalized_format == "word":
        return scope.capture_waveforms_word(channels, points=points)
    return scope.capture_waveforms_byte(channels, points=points)


def _resolve_capture_channels(
    raw_channels: Sequence[int | str], capabilities: ScopeCapabilities
) -> tuple[int, ...]:
    if any(channel == "all" for channel in raw_channels):
        if len(raw_channels) != 1:
            raise KeysightScopeError(
                "error: --channel all cannot be combined with explicit channel numbers"
            )
        return validate_waveform_channels(
            tuple(range(1, capabilities.analog_channels + 1)), capabilities
        )

    return validate_waveform_channels(raw_channels, capabilities)


def _write_capture_csv(
    capture: WaveformCapture | MultiChannelWaveformCapture, csv_path: Path
) -> Path:
    try:
        if isinstance(capture, MultiChannelWaveformCapture):
            return write_waveforms_csv(capture, csv_path)
        return write_waveform_csv(capture, csv_path)
    except OSError as exc:
        raise KeysightScopeError(_format_output_file_error("CSV", csv_path, exc)) from exc


def _write_capture_metadata(
    capture: WaveformCapture | MultiChannelWaveformCapture,
    meta_path: Path,
    *,
    idn,
    resource: str,
) -> Path:
    try:
        if isinstance(capture, MultiChannelWaveformCapture):
            return write_waveforms_metadata(capture, meta_path, idn=idn, resource=resource)
        return write_waveform_metadata(capture, meta_path, idn=idn, resource=resource)
    except OSError as exc:
        raise KeysightScopeError(
            _format_output_file_error("metadata JSON", meta_path, exc)
        ) from exc


def _write_screenshot_png(capture, output_path: Path) -> Path:
    try:
        return write_screenshot_png(capture, output_path)
    except OSError as exc:
        raise KeysightScopeError(
            _format_output_file_error("screenshot PNG", output_path, exc)
        ) from exc


def _write_batch_manifest(manifest: BatchManifest, manifest_path: Path) -> Path:
    try:
        return write_batch_manifest(manifest, manifest_path)
    except OSError as exc:
        raise KeysightScopeError(
            _format_plain_output_file_error("batch manifest JSON", manifest_path, exc)
        ) from exc


def _write_batch_manifest_best_effort(
    manifest: BatchManifest,
    manifest_path: Path,
) -> None:
    try:
        write_batch_manifest(manifest, manifest_path)
    except OSError:
        pass


def _format_output_file_error(file_kind: str, path: Path, exc: OSError) -> str:
    reason = exc.strerror or str(exc)
    if file_kind.startswith("screenshot"):
        message = f"could not write {file_kind} file {path}: {reason}"
    else:
        message = f"could not write waveform {file_kind} file {path}: {reason}"
    if isinstance(exc, PermissionError):
        if file_kind.startswith("screenshot"):
            message += (
                ". The file may be open in another program, "
                "or the folder may not be writable."
            )
        else:
            message += (
                ". The file may be open in another program, such as Excel, "
                "or the folder may not be writable."
            )
    return message


def _format_plain_output_file_error(file_kind: str, path: Path, exc: OSError) -> str:
    reason = exc.strerror or str(exc)
    message = f"could not write {file_kind} file {path}: {reason}"
    if isinstance(exc, PermissionError):
        message += ". The file may be open in another program, or the folder may not be writable."
    return message


def _print_capabilities(capabilities: ScopeCapabilities | None) -> None:
    if capabilities is None:
        print("Capabilities: unavailable for this model")
        return

    print(f"Analog channels: {capabilities.analog_channels}")
    print(f"Default waveform points: {capabilities.default_waveform_points}")
    print(f"Safe max waveform points: {capabilities.safe_max_waveform_points}")


def _require_resource(args: argparse.Namespace) -> str | None:
    mode = _resolve_cli_mode(args)
    if mode == "simulate":
        return args.resource or f"SIM::{args.model}::INSTR"
    if mode == "dry_run":
        return args.resource or f"DRY::{args.model}::INSTR"

    resource = args.resource or os.environ.get("KEYSIGHT_SCOPE_RESOURCE")
    if resource:
        return resource

    print(
        "error: --resource is required unless KEYSIGHT_SCOPE_RESOURCE is set",
        file=sys.stderr,
    )
    return None


def _configure_scpi_logging(args: argparse.Namespace) -> None:
    if args.log_scpi:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _capture_channel_arg(value: str) -> int | str:
    if value.strip().lower() == "all":
        return "all"
    try:
        return _positive_int(value)
    except argparse.ArgumentTypeError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer or all") from exc


def _finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_channel_offset(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_channel_scale(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _nonnegative_finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not parsed == parsed or parsed in (float("inf"), float("-inf")):
        raise argparse.ArgumentTypeError("must be finite")
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _probe_ratio_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_probe_ratio(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _finite_timebase_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_timebase_position(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _positive_timebase_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_timebase_scale(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _trigger_level_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_trigger_level(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _measurement_finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not parsed == parsed or parsed in (float("inf"), float("-inf")):
        raise argparse.ArgumentTypeError("must be a finite number")
    return parsed


def _measurement_query_kwargs(args: argparse.Namespace, item: str) -> dict[str, object]:
    values: dict[str, object] = {}
    if args.time_s is not None:
        values["time_s"] = args.time_s
    if args.level is not None:
        values["level"] = args.level
    if args.slope is not None:
        values["slope"] = args.slope
    if args.occurrence is not None:
        values["occurrence"] = args.occurrence

    if is_pair_measurement_item(item):
        if values:
            raise KeysightScopeError(
                "--time, --level, --slope, and --occurrence cannot be used with "
                "phase or delay measurements"
            )
        return {}

    if item == "y_at_x":
        if args.time_s is None:
            raise KeysightScopeError("y_at_x measurement requires --time")
        if any(value is not None for value in (args.level, args.slope, args.occurrence)):
            raise KeysightScopeError(
                "--level, --slope, and --occurrence cannot be used with y_at_x"
            )
        return values

    if item == "time_at_edge":
        if args.time_s is not None or args.level is not None:
            raise KeysightScopeError("--time and --level cannot be used with time_at_edge")
        values.setdefault("slope", "positive")
        values.setdefault("occurrence", 1)
        return values

    if item == "time_at_value":
        if args.level is None:
            raise KeysightScopeError("time_at_value measurement requires --level")
        if args.time_s is not None:
            raise KeysightScopeError("--time cannot be used with time_at_value")
        values.setdefault("slope", "positive")
        values.setdefault("occurrence", 1)
        return values

    if values:
        raise KeysightScopeError(
            "--time, --level, --slope, and --occurrence can only be used with "
            "y_at_x, time_at_edge, or time_at_value"
        )
    return {}


def _resolve_measurement_source_channel(args: argparse.Namespace) -> int | None:
    if args.channel is not None and args.source_channel is not None:
        raise KeysightScopeError("--channel cannot be combined with --source-channel")
    return args.source_channel if args.source_channel is not None else args.channel


def _resolve_single_measurement_channel(
    args: argparse.Namespace, capabilities: ScopeCapabilities
) -> int:
    if args.reference_channel is not None:
        raise KeysightScopeError(
            "--reference-channel can only be used with phase or delay measurements"
        )
    channel = _resolve_measurement_source_channel(args)
    if channel is None:
        raise KeysightScopeError("measure requires --channel or --source-channel")
    return validate_analog_channel(channel, capabilities)


def _resolve_pair_measurement_channels(
    args: argparse.Namespace,
    capabilities: ScopeCapabilities,
    item: str,
) -> tuple[int, int]:
    source_channel = _resolve_measurement_source_channel(args)
    if source_channel is None or args.reference_channel is None:
        raise KeysightScopeError(
            f"{item} measurement requires --source-channel or --channel, "
            "plus --reference-channel"
        )
    source_channel = validate_analog_channel(source_channel, capabilities)
    reference_channel = validate_analog_channel(args.reference_channel, capabilities)
    if source_channel == reference_channel:
        raise KeysightScopeError("source channel and reference channel must be different")
    return source_channel, reference_channel


def _format_measurement_parameters(values: dict[str, object]) -> str:
    if not values:
        return ""
    labels = {
        "time_s": "time",
        "level": "level",
        "slope": "slope",
        "occurrence": "occurrence",
    }
    formatted = ", ".join(f"{labels[key]}={value}" for key, value in values.items())
    return f" ({formatted})"


def _waveform_points_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed not in SUPPORTED_WAVEFORM_POINTS:
        supported = ", ".join(str(point_count) for point_count in SUPPORTED_WAVEFORM_POINTS)
        raise argparse.ArgumentTypeError(
            f"waveform capture supports only these point counts: {supported}"
        )
    return parsed


def _print_session_header(scope: KeysightScope, resource: str) -> None:
    print(f"Resource: {resource}")
    backend = getattr(scope.backend, "backend", None)
    if backend is not None:
        print(f"PyVISA backend: {backend}")
    timeout = getattr(scope.backend, "timeout", None)
    if timeout is not None:
        print(f"Timeout ms: {timeout}")


if __name__ == "__main__":
    raise SystemExit(main())
