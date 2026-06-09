"""Command line interface for Phase 1 oscilloscope checks."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Sequence

from .capabilities import ScopeCapabilities
from .errors import KeysightScopeError
from .scope import KeysightScope
from .visa_backend import list_visa_resources


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `scope-tool` command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            return _cmd_list(args)
        if args.command == "idn":
            return _cmd_idn(args)
    except KeysightScopeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("missing command")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scope-tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list visible VISA resources")
    list_parser.add_argument(
        "--visa-library",
        default=None,
        help="optional PyVISA library argument, such as @py",
    )

    idn_parser = subparsers.add_parser("idn", help="query and parse *IDN?")
    idn_parser.add_argument(
        "--resource",
        default=None,
        help="VISA resource string. Defaults to KEYSIGHT_SCOPE_RESOURCE.",
    )
    idn_parser.add_argument(
        "--visa-library",
        default=None,
        help="optional PyVISA library argument, such as @py",
    )
    idn_parser.add_argument(
        "--log-scpi",
        action="store_true",
        help="write SCPI command and response logs to stderr",
    )
    return parser


def _cmd_list(args: argparse.Namespace) -> int:
    listing = list_visa_resources(visa_library=args.visa_library)
    print(f"PyVISA backend: {listing.backend}")
    print("Resources:")
    if not listing.resources:
        print("  <none>")
        return 0

    for resource in listing.resources:
        print(f"  {resource}")
    return 0


def _cmd_idn(args: argparse.Namespace) -> int:
    resource = args.resource or os.environ.get("KEYSIGHT_SCOPE_RESOURCE")
    if not resource:
        print(
            "error: --resource is required unless KEYSIGHT_SCOPE_RESOURCE is set",
            file=sys.stderr,
        )
        return 2

    if args.log_scpi:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")

    with KeysightScope.open(resource, visa_library=args.visa_library) as scope:
        idn = scope.query_idn()
        print(f"Resource: {resource}")
        backend = getattr(scope.backend, "backend", None)
        if backend is not None:
            print(f"PyVISA backend: {backend}")
        timeout = getattr(scope.backend, "timeout", None)
        if timeout is not None:
            print(f"Timeout ms: {timeout}")
        print(f"Raw IDN: {idn.raw}")
        print(f"Vendor: {idn.vendor}")
        print(f"Model: {idn.model}")
        print(f"Serial: {idn.serial}")
        print(f"Firmware: {idn.firmware}")
        print(f"Series: {idn.series or 'unknown'}")
        _print_capabilities(scope.capabilities)
    return 0


def _print_capabilities(capabilities: ScopeCapabilities | None) -> None:
    if capabilities is None:
        print("Capabilities: unavailable for this model")
        return

    print(f"Analog channels: {capabilities.analog_channels}")
    print(f"Default waveform points: {capabilities.default_waveform_points}")
    print(f"Safe max waveform points: {capabilities.safe_max_waveform_points}")


if __name__ == "__main__":
    raise SystemExit(main())
