"""Command line interface for oscilloscope checks."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import sys
from typing import Sequence

from .capabilities import ScopeCapabilities
from .channel import (
    channel_display_command,
    channel_display_query,
    channel_offset_command,
    channel_offset_query,
    channel_scale_command,
    channel_scale_query,
    validate_analog_channel,
    validate_channel_offset,
    validate_channel_scale,
)
from .errors import KeysightScopeError
from .scope import KeysightScope
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
    SUPPORTED_BYTE_POINTS,
    validate_waveform_points,
    waveform_data_query,
    waveform_format_byte_command,
    waveform_points_command,
    waveform_preamble_query,
    waveform_source_command,
    write_waveform_csv,
    write_waveform_metadata,
)

_CONTROL_COMMANDS = {
    "run": ("run", ":RUN"),
    "stop": ("stop", ":STOP"),
    "single": ("single", ":SINGle"),
}
_CAPTURE_DEFAULT_TIMEZONE = timezone(timedelta(hours=8), name="UTC+8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `scope-tool` command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
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
        if args.command == "timebase-scale":
            return _cmd_timebase_scale(args)
        if args.command == "timebase-position":
            return _cmd_timebase_position(args)
        if args.command == "edge-trigger":
            return _cmd_edge_trigger(args)
        if args.command == "capture":
            return _cmd_capture(args)
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

    capture_parser = subparsers.add_parser(
        "capture",
        help="capture one analog channel waveform to CSV and metadata JSON",
    )
    _add_scope_connection_args(capture_parser)
    capture_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
    )
    capture_parser.add_argument(
        "--points",
        type=_waveform_points_arg,
        default=1000,
        help="waveform point count; first capture slice supports 1000",
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


def _cmd_list_resources(args: argparse.Namespace) -> int:
    listing = list_visa_resources(visa_library=args.visa_library)
    print(f"PyVISA backend: {listing.backend}")
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
    for resource in resources:
        try:
            with KeysightScope.open(resource, visa_library=visa_library) as scope:
                idn = scope.query_idn()
        except KeysightScopeError:
            continue

        live_count += 1
        print(f"  {resource}")
        print(f"    IDN: {idn.raw}")

    if live_count == 0:
        print("  <none>")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        _print_session_header(scope, resource)
        if args.drain:
            entries = scope.drain_system_errors(max_reads=args.max_reads)
            for index, entry in enumerate(entries, start=1):
                print(f"System error {index}: {entry.format()}")
            return 1 if any(entry.is_error for entry in entries) else 0

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_control(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)
    method_name, command = _CONTROL_COMMANDS[args.command]

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        _print_session_header(scope, resource)
        getattr(scope, method_name)()
        print(f"Command: {command}")
        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_display(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
            print(f"Command: {command}")
            print(f"Display: {'ON' if enabled else 'OFF'}")
        else:
            enabled = args.display_action == "on"
            command = channel_display_command(channel, enabled)
            print(f"Planned change: CH{channel} display {'ON' if enabled else 'OFF'}")
            scope.set_channel_display(channel, enabled)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_scale(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
            print(f"Command: {command}")
            print(f"Scale V/div: {scale:.12g}")
        else:
            scale = validate_channel_scale(args.scale_value)
            command = channel_scale_command(channel, scale)
            print(f"Planned change: CH{channel} scale {scale:.12g} V/div")
            scope.set_channel_scale(channel, scale)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_offset(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
            print(f"Command: {command}")
            print(f"Offset V: {offset:.12g}")
        else:
            offset = validate_channel_offset(args.offset_value)
            command = channel_offset_command(channel, offset)
            print(f"Planned change: CH{channel} offset {offset:.12g} V")
            scope.set_channel_offset(channel, offset)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_timebase_scale(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
            print(f"Command: {command}")
            print(f"Timebase scale s/div: {scale:.12g}")
        else:
            scale = validate_timebase_scale(args.timebase_scale_value)
            command = timebase_scale_command(scale)
            print(f"Planned change: timebase scale {scale:.12g} s/div")
            scope.set_timebase_scale(scale)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_timebase_position(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
            print(f"Command: {command}")
            print(f"Timebase position s: {position:.12g}")
        else:
            position = validate_timebase_position(args.timebase_position_value)
            command = timebase_position_command(position)
            print(f"Planned change: timebase position {position:.12g} s")
            scope.set_timebase_position(position)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_edge_trigger(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
            print(f"Command: {trigger_mode_edge_command()}")
            print(f"Command: {edge_trigger_source_command(channel)}")
            print(f"Command: {edge_trigger_level_command(level)}")
            print(f"Command: {edge_trigger_slope_command(slope)}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_capture(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    csv_path = Path(args.csv_path) if args.csv_path is not None else _default_capture_csv_path()
    meta_path = Path(args.meta_path) if args.meta_path is not None else csv_path.with_name(
        f"{csv_path.stem}_meta.json"
    )

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        print(f"Series: {idn.series or 'unknown'}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1

        channel = validate_analog_channel(args.channel, scope.capabilities)
        points = validate_waveform_points(args.points, scope.capabilities)
        print(f"Planned capture: CH{channel}, {points} points, BYTE format")
        capture = scope.capture_waveform_byte(channel, points=points)
        print(f"Command: {waveform_source_command(channel)}")
        print(f"Command: {waveform_format_byte_command()}")
        print(f"Command: {waveform_points_command(points)}")
        print(f"Command: {waveform_preamble_query()}")
        print(f"Command: {waveform_data_query()}")
        written_csv = _write_capture_csv(capture, csv_path)
        written_meta = _write_capture_metadata(capture, meta_path, idn=idn, resource=resource)
        print(f"Actual points: {len(capture.raw_samples)}")
        print(f"CSV: {written_csv}")
        print(f"Metadata: {written_meta}")
        entry = scope.query_system_error()
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


def _write_capture_csv(capture, csv_path: Path) -> Path:
    try:
        return write_waveform_csv(capture, csv_path)
    except OSError as exc:
        raise KeysightScopeError(_format_output_file_error("CSV", csv_path, exc)) from exc


def _write_capture_metadata(capture, meta_path: Path, *, idn, resource: str) -> Path:
    try:
        return write_waveform_metadata(capture, meta_path, idn=idn, resource=resource)
    except OSError as exc:
        raise KeysightScopeError(_format_output_file_error("metadata JSON", meta_path, exc)) from exc


def _format_output_file_error(file_kind: str, path: Path, exc: OSError) -> str:
    reason = exc.strerror or str(exc)
    message = f"could not write waveform {file_kind} file {path}: {reason}"
    if isinstance(exc, PermissionError):
        message += (
            ". The file may be open in another program, such as Excel, "
            "or the folder may not be writable."
        )
    return message


def _print_capabilities(capabilities: ScopeCapabilities | None) -> None:
    if capabilities is None:
        print("Capabilities: unavailable for this model")
        return

    print(f"Analog channels: {capabilities.analog_channels}")
    print(f"Default waveform points: {capabilities.default_waveform_points}")
    print(f"Safe max waveform points: {capabilities.safe_max_waveform_points}")


def _require_resource(args: argparse.Namespace) -> str | None:
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


def _waveform_points_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed not in SUPPORTED_BYTE_POINTS:
        supported = ", ".join(str(point_count) for point_count in SUPPORTED_BYTE_POINTS)
        raise argparse.ArgumentTypeError(
            f"first waveform capture slice supports only these point counts: {supported}"
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
