"""Command line interface for oscilloscope checks."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Sequence

from .capabilities import ScopeCapabilities
from .channel import channel_display_command, channel_display_query, validate_analog_channel
from .errors import KeysightScopeError
from .scope import KeysightScope
from .visa_backend import list_visa_resources

_CONTROL_COMMANDS = {
    "run": ("run", ":RUN"),
    "stop": ("stop", ":STOP"),
    "single": ("single", ":SINGle"),
}


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
