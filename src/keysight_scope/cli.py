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
from .measurements import (
    MEASUREMENT_ITEM_CHOICES,
    measurement_query,
    normalize_measurement_item,
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
        if args.command == "screenshot":
            return _cmd_screenshot(args)
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
        help="query one read-only measurement item for one analog channel",
    )
    _add_scope_connection_args(measure_parser)
    measure_parser.add_argument(
        "--channel",
        type=_positive_int,
        required=True,
        help="analog channel number, validated against the detected scope model",
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


def _cmd_channel_coupling(args: argparse.Namespace) -> int:
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
        if args.coupling_query:
            command = channel_coupling_query(channel)
            print(f"Planned query: CH{channel} coupling")
            coupling = scope.query_channel_coupling(channel)
            print(f"Command: {command}")
            print(f"Coupling: {coupling.upper()}")
        else:
            coupling = normalize_channel_coupling(args.coupling_value)
            command = channel_coupling_command(channel, coupling)
            print(f"Planned change: CH{channel} coupling {coupling.upper()}")
            scope.set_channel_coupling(channel, coupling)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_probe(args: argparse.Namespace) -> int:
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
        if args.probe_query:
            command = channel_probe_ratio_query(channel)
            print(f"Planned query: CH{channel} probe ratio")
            ratio = scope.query_channel_probe_ratio(channel)
            print(f"Command: {command}")
            print(f"Probe ratio: {ratio:.12g}")
        else:
            ratio = validate_probe_ratio(args.probe_ratio)
            command = channel_probe_ratio_command(channel, ratio)
            print(f"Planned change: CH{channel} probe ratio {ratio:.12g}")
            scope.set_channel_probe_ratio(channel, ratio)
            print(f"Command: {command}")

        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_channel_bandwidth_limit(args: argparse.Namespace) -> int:
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
        if args.bandwidth_action == "query":
            command = channel_bandwidth_limit_query(channel)
            print(f"Planned query: CH{channel} bandwidth limit")
            enabled = scope.query_channel_bandwidth_limit(channel)
            print(f"Command: {command}")
            print(f"Bandwidth limit: {'ON' if enabled else 'OFF'}")
        else:
            enabled = args.bandwidth_action == "on"
            command = channel_bandwidth_limit_command(channel, enabled)
            state = "ON" if enabled else "OFF"
            print(f"Planned change: CH{channel} bandwidth limit {state}")
            scope.set_channel_bandwidth_limit(channel, enabled)
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


def _cmd_measure(args: argparse.Namespace) -> int:
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
        item = normalize_measurement_item(args.item)
        measurement_kwargs = _measurement_query_kwargs(args, item)
        print(
            f"Planned query: CH{channel} {item} measurement"
            f"{_format_measurement_parameters(measurement_kwargs)}"
        )
        result = scope.query_measurement(channel, item, **measurement_kwargs)
        print(
            "Command: "
            f"{measurement_query(item, channel, capabilities=scope.capabilities, **measurement_kwargs)}"
        )
        print(f"Measurement: {result.item}")
        print(f"Channel: {result.channel}")
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

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
        print(_format_actual_points(capture))
        print(f"CSV: {written_csv}")
        print(f"Metadata: {written_meta}")
        entry = scope.query_system_error()
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_screenshot(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    output_path = (
        Path(args.output_path) if args.output_path is not None else _default_screenshot_path()
    )

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
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
        print(f"Format: {capture.format_name}")
        print(f"Palette: {capture.palette}")
        print(f"Background: {capture.background}")
        print(f"Bytes: {len(capture.data)}")
        print(f"PNG: {written_png}")
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
