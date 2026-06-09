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
from .advanced import (
    autoscale_commands,
    cursor_auto_vertical_dry_run_plan,
    cursor_auto_vertical_json,
    cursor_auto_vertical_plan,
    cursor_auto_timebase_dry_run_plan,
    cursor_auto_timebase_json,
    cursor_auto_timebase_plan,
    cursor_configure_commands,
    fft_configure_commands,
    fft_query_commands,
    setup_recall_command,
    setup_save_command,
    trigger_holdoff_commands,
    trigger_holdoff_query,
    validate_trigger_holdoff,
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
from .measure_logger import (
    log_measurements_workflow,
    measure_log_paths,
    prepare_measure_log_output_dir,
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
    MeasurementStatisticsResult,
    is_pair_measurement_item,
    measurement_query,
    normalize_measurement_item,
    parse_statistics_results,
    pair_measurement_query,
    statistics_install_command,
    statistics_mode_scpi,
    validate_statistics_items,
    validate_statistics_max_count,
    validate_statistics_settle_seconds,
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
from .simulator_backend import SimulatedSignal, SimulatorBackend, simulator_idn
from .simulator_config import (
    PRESET_NAMES,
    parse_simulate_signal_spec,
    simulator_backend_kwargs,
    validate_simulator_args,
)
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
    waveform_time_axis_tolerance_summary,
    waveform_data_query,
    waveform_format_byte_command,
    waveform_format_word_command,
    waveform_points_command,
    waveform_preamble_query,
    waveform_source_command,
    waveform_unsigned_command,
    write_waveform_csv,
    write_waveform_metadata,
    write_waveform_plot_png,
    write_waveforms_csv,
    write_waveforms_metadata,
)

_CONTROL_COMMANDS = {
    "run": ("run", ":RUN"),
    "stop": ("stop", ":STOP"),
    "single": ("single", ":SINGle"),
}
_CAPTURE_DEFAULT_TIMEZONE = timezone(timedelta(hours=8), name="UTC+8")
AUTOSCALE_SYSTEM_ERROR_TIMEOUT_MS = 15000
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

    hardware_report_parser = subparsers.add_parser(
        "hardware-report",
        help="render hardware report JSON files as a Markdown summary",
    )
    hardware_report_parser.add_argument(
        "report_paths",
        nargs="+",
        help="report JSON files from smoke or acquisition-check",
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

    cursor_parser = subparsers.add_parser(
        "cursor",
        help="query, hide, or configure manual marker cursors",
    )
    _add_scope_connection_args(cursor_parser)
    cursor_action = cursor_parser.add_mutually_exclusive_group(required=True)
    cursor_action.add_argument("--query", dest="cursor_query", action="store_true")
    cursor_action.add_argument("--off", dest="cursor_off", action="store_true")
    cursor_action.add_argument("--x1", type=_measurement_finite_float, default=None)
    cursor_parser.add_argument("--source-channel", type=_positive_int, default=None)
    cursor_parser.add_argument("--x2", type=_measurement_finite_float, default=None)
    cursor_parser.add_argument("--y1", type=_measurement_finite_float, default=None)
    cursor_parser.add_argument("--y2", type=_measurement_finite_float, default=None)
    cursor_parser.add_argument(
        "--auto-timebase",
        action="store_true",
        help="widen horizontal scale before setting cursors if X positions are outside the visible range",
    )
    cursor_parser.add_argument(
        "--auto-vertical",
        action="store_true",
        help="adjust source channel vertical scale/offset before setting Y cursors if needed",
    )

    trigger_holdoff_parser = subparsers.add_parser(
        "trigger-holdoff",
        help="set or query trigger holdoff seconds",
    )
    _add_scope_connection_args(trigger_holdoff_parser)
    holdoff_action = trigger_holdoff_parser.add_mutually_exclusive_group(required=True)
    holdoff_action.add_argument("--query", dest="holdoff_query", action="store_true")
    holdoff_action.add_argument("--seconds", dest="holdoff_seconds", type=_holdoff_seconds_arg)

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

    measure_stats_parser = subparsers.add_parser(
        "measure-stats",
        help="rebuild front-panel measurements and query statistics",
    )
    _add_scope_connection_args(measure_stats_parser)
    measure_stats_parser.add_argument("--channel", type=_positive_int, required=True)
    measure_stats_parser.add_argument("--items", required=True)
    measure_stats_parser.add_argument(
        "--mode",
        choices=("all", "current", "min", "max", "mean", "stddev", "count"),
        default="all",
    )
    measure_stats_parser.add_argument("--reset", action="store_true")
    measure_stats_parser.add_argument("--max-count", type=_positive_int, default=None)
    measure_stats_parser.add_argument(
        "--settle-seconds",
        type=_nonnegative_finite_float,
        default=None,
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="collect a read-only scope configuration snapshot for diagnostics",
    )
    _add_scope_connection_args(doctor_parser)

    measure_sweep_parser = subparsers.add_parser(
        "measure-sweep",
        help="query multiple read-only measurements and summarize failures",
    )
    _add_scope_connection_args(measure_sweep_parser)
    measure_sweep_parser.add_argument(
        "--channel",
        type=_capture_channel_arg,
        action="append",
        default=None,
        help="analog channel number; repeat or use all. Defaults to all channels",
    )
    measure_sweep_parser.add_argument(
        "--items",
        default="vpp,frequency,period,vrms",
        help="comma-separated single-channel measurement items",
    )
    measure_sweep_parser.add_argument(
        "--pair",
        action="append",
        default=[],
        metavar="SRC:REF",
        help="source/reference channel pair such as 1:2; repeatable",
    )
    measure_sweep_parser.add_argument(
        "--pair-items",
        default="phase,delay",
        help="comma-separated pair measurement items; only used with --pair",
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
    capture_parser.add_argument(
        "--plot",
        dest="plot_path",
        default=None,
        help="optional output PNG plot path",
    )
    capture_parser.add_argument(
        "--allow-time-axis-tolerance",
        action="store_true",
        help=(
            "allow small multi-channel time-axis drift up to half the first "
            "channel sample interval"
        ),
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

    measure_log_parser = subparsers.add_parser(
        "measure-log",
        help="log a finite batch of single-channel and channel-pair measurements to CSV",
    )
    _add_scope_connection_args(measure_log_parser)
    measure_log_parser.add_argument(
        "--channel",
        "--source-channel",
        dest="channel",
        type=_capture_channel_arg,
        action="append",
        default=None,
        help="analog channel number to log; repeat for multiple channels, or use all",
    )
    measure_log_parser.add_argument(
        "--items",
        default="vpp,frequency",
        help="comma-separated single-channel measurements; defaults to vpp,frequency",
    )
    measure_log_parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="repeatable source/reference channel pairs (SRC:REF)",
    )
    measure_log_parser.add_argument(
        "--pair-items",
        default="phase,delay",
        help="comma-separated pair measurements; defaults to phase,delay",
    )
    measure_log_parser.add_argument(
        "--interval-seconds",
        type=_nonnegative_finite_float,
        default=1.0,
        help="seconds to sleep between log rows; defaults to 1.0",
    )
    measure_log_parser.add_argument(
        "--count",
        type=_positive_int,
        default=None,
        help="total number of log rows to capture; required unless --duration-seconds is set",
    )
    measure_log_parser.add_argument(
        "--duration-seconds",
        type=_positive_plain_float,
        default=None,
        help="maximum duration in seconds; required unless --count is set",
    )
    measure_log_parser.add_argument(
        "--output-dir",
        default=None,
        help="output directory; if provided, it must not exist or must be empty",
    )
    measure_log_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="abort logging immediately if an instrument system error is detected",
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

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="run a capture-safe diagnostic smoke test and write a report directory",
    )
    _add_scope_connection_args(smoke_parser)
    smoke_parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "output directory; defaults to data/hardware_smoke/<UTC+8 timestamp>. "
            "If provided, it must not exist or must be empty"
        ),
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

    autoscale_parser = subparsers.add_parser("autoscale", help="run oscilloscope autoscale")
    _add_scope_connection_args(autoscale_parser)
    autoscale_parser.add_argument(
        "--source-channel",
        type=_positive_int,
        action="append",
        default=None,
        help="analog channel source; repeat to autoscale selected sources",
    )
    autoscale_parser.add_argument(
        "--acquire-mode",
        choices=("normal", "current"),
        default=None,
    )
    autoscale_parser.add_argument(
        "--channels",
        choices=("all", "displayed"),
        default=None,
    )

    setup_save_parser = subparsers.add_parser("setup-save", help="save setup to slot or file")
    _add_scope_connection_args(setup_save_parser)
    save_target = setup_save_parser.add_mutually_exclusive_group(required=True)
    save_target.add_argument("--slot", type=_setup_slot_arg, default=None)
    save_target.add_argument("--file", dest="setup_file", default=None)

    setup_recall_parser = subparsers.add_parser("setup-recall", help="recall setup from slot or file")
    _add_scope_connection_args(setup_recall_parser)
    recall_target = setup_recall_parser.add_mutually_exclusive_group(required=True)
    recall_target.add_argument("--slot", type=_setup_slot_arg, default=None)
    recall_target.add_argument("--file", dest="setup_file", default=None)

    fft_parser = subparsers.add_parser("fft", help="configure or query FFT math function")
    _add_scope_connection_args(fft_parser)
    fft_parser.add_argument("--query", dest="fft_query", action="store_true")
    fft_parser.add_argument("--function", type=_positive_int, required=True)
    fft_parser.add_argument("--source-channel", type=_positive_int, default=None)
    fft_parser.add_argument("--units", choices=("decibel", "vrms"), default=None)
    fft_parser.add_argument(
        "--window",
        choices=("rectangular", "hanning", "flattop", "bharris", "bartlett"),
        default=None,
    )
    fft_parser.add_argument("--center-hz", type=_nonnegative_finite_float, default=None)
    fft_parser.add_argument("--span-hz", type=_positive_plain_float, default=None)
    fft_parser.add_argument("--display", choices=("on", "off"), default=None)

    acquisition_check_parser = subparsers.add_parser(
        "acquisition-check",
        help="run the acquisition configuration hardware validation workflow",
    )
    _add_scope_connection_args(acquisition_check_parser)
    acquisition_check_parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "output directory; defaults to data/hardware_acquisition/<UTC+8 timestamp>. "
            "If provided, it must not exist or must be empty"
        ),
    )
    acquisition_check_parser.add_argument(
        "--average-count",
        type=_positive_int,
        default=16,
        help="average acquisition count to validate; defaults to 16",
    )
    acquisition_check_parser.add_argument(
        "--check-only",
        action="store_true",
        help="only query the current acquisition configuration and system error",
    )
    acquisition_check_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="stop the workflow after the first acquisition step with a system error",
    )
    acquisition_check_parser.add_argument(
        "--restore-type",
        action="store_true",
        help="restore the initial acquisition type after the workflow completes",
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
        "--simulate-signal",
        dest="simulate_signals",
        action="append",
        default=[],
        metavar="CH:shape:frequency_hz:vpp_v:offset_v:phase_deg[:noise_rms_v]",
        help=(
            "override one simulator channel signal; repeat per channel. "
            "Only valid with --simulate"
        ),
    )
    parser.add_argument(
        "--simulate-preset",
        choices=PRESET_NAMES,
        default=None,
        help="apply a built-in simulator preset; only valid with --simulate",
    )
    parser.add_argument(
        "--simulate-scenario",
        default=None,
        help="load simulator scenario JSON; only valid with --simulate",
    )
    parser.add_argument(
        "--simulate-system-error",
        dest="simulate_system_errors",
        action="append",
        default=[],
        metavar="CODE",
        help="seed one simulator system error code; repeatable and only valid with --simulate",
    )
    parser.add_argument(
        "--simulate-binary-transfer-failure",
        action="store_true",
        help="fail simulator waveform binary transfers; only valid with --simulate",
    )
    parser.add_argument(
        "--simulate-invalid-measurement",
        dest="simulate_invalid_measurement_channels",
        action="append",
        default=[],
        metavar="CH",
        help="make simulator measurements invalid for a channel; repeatable and only valid with --simulate",
    )
    parser.add_argument(
        "--simulate-display-off",
        dest="simulate_display_off_channels",
        action="append",
        default=[],
        metavar="CH",
        help="start a simulator channel display off; repeatable and only valid with --simulate",
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
    if args.command == "hardware-report":
        return _cmd_hardware_report(args)
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
    if args.command == "cursor":
        return _cmd_cursor(args)
    if args.command == "trigger-holdoff":
        return _cmd_trigger_holdoff(args)
    if args.command == "measure":
        return _cmd_measure(args)
    if args.command == "measure-stats":
        return _cmd_measure_stats(args)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "measure-sweep":
        return _cmd_measure_sweep(args)
    if args.command == "capture":
        return _cmd_capture(args)
    if args.command == "capture-batch":
        return _cmd_capture_batch(args)
    if args.command == "measure-log":
        return _cmd_measure_log(args)
    if args.command == "screenshot":
        return _cmd_screenshot(args)
    if args.command == "smoke":
        return _cmd_smoke(args)
    if args.command == "acquisition":
        return _cmd_acquisition(args)
    if args.command == "autoscale":
        return _cmd_autoscale(args)
    if args.command == "setup-save":
        return _cmd_setup_save(args)
    if args.command == "setup-recall":
        return _cmd_setup_recall(args)
    if args.command == "fft":
        return _cmd_fft(args)
    if args.command == "acquisition-check":
        return _cmd_acquisition_check(args)
    raise KeysightScopeError("missing command")



_LAST_BACKEND = None


def _resolve_cli_mode(args: argparse.Namespace) -> str:
    _validate_cursor_auto_args(args)
    _validate_measure_log_args(args)
    if getattr(args, "simulate", False) and getattr(args, "dry_run", False):
        raise KeysightScopeError("--simulate cannot be combined with --dry-run")
    if getattr(args, "simulate_signals", None) and not getattr(args, "simulate", False):
        raise KeysightScopeError("--simulate-signal can only be used with --simulate")
    for attr, option in (
        ("simulate_preset", "--simulate-preset"),
        ("simulate_scenario", "--simulate-scenario"),
        ("simulate_system_errors", "--simulate-system-error"),
        ("simulate_binary_transfer_failure", "--simulate-binary-transfer-failure"),
        ("simulate_invalid_measurement_channels", "--simulate-invalid-measurement"),
        ("simulate_display_off_channels", "--simulate-display-off"),
    ):
        value = getattr(args, attr, None)
        if value and not getattr(args, "simulate", False):
            raise KeysightScopeError(f"{option} can only be used with --simulate")
    if getattr(args, "simulate", False):
        capabilities = capabilities_for_model(args.model)
        validate_simulator_args(args, capabilities)
        return "simulate"
    if getattr(args, "dry_run", False):
        capabilities_for_model(args.model)
        return "dry_run"
    return "live"


def _validate_cursor_auto_args(args: argparse.Namespace) -> None:
    if getattr(args, "command", None) != "cursor":
        return
    setting_cursor = not getattr(args, "cursor_query", False) and not getattr(args, "cursor_off", False)
    if getattr(args, "auto_timebase", False) and not setting_cursor:
        raise KeysightScopeError("--auto-timebase is only valid when setting cursor positions")
    if not getattr(args, "auto_vertical", False):
        return
    if not setting_cursor:
        raise KeysightScopeError("--auto-vertical is only valid when setting cursor positions")
    if getattr(args, "source_channel", None) is None or getattr(args, "x2", None) is None:
        raise KeysightScopeError(
            "--auto-vertical requires --source-channel, --x1, and --x2"
        )
    if getattr(args, "y1", None) is None and getattr(args, "y2", None) is None:
        raise KeysightScopeError("--auto-vertical requires --y1 or --y2")


def _validate_measure_log_args(args: argparse.Namespace) -> None:
    if getattr(args, "command", None) != "measure-log":
        return
    if args.count is None and args.duration_seconds is None:
        raise KeysightScopeError(
            "measure-log requires --count or --duration-seconds so the run is finite"
        )
    for value in args.pair:
        parts = value.split(":")
        if len(parts) != 2:
            raise KeysightScopeError("--pair must use SRC:REF, for example 1:2")
        try:
            source = int(parts[0])
            reference = int(parts[1])
        except ValueError as exc:
            raise KeysightScopeError("--pair channels must be integers") from exc
        if source == reference:
            raise KeysightScopeError("--pair source and reference channels must differ")


def _open_scope(args: argparse.Namespace, resource: str) -> KeysightScope:
    global _LAST_BACKEND
    mode = _resolve_cli_mode(args)
    if mode == "simulate":
        backend = _make_simulator_backend(args, resource)
        _LAST_BACKEND = backend
        return KeysightScope(backend)
    scope = KeysightScope.open(resource, visa_library=args.visa_library)
    _LAST_BACKEND = getattr(scope, "backend", None)
    if _JSON_RECORD is not None:
        _JSON_RECORD["backend"] = getattr(scope.backend, "backend", None)
    return scope


def _make_simulator_backend(args: argparse.Namespace, resource: str) -> SimulatorBackend:
    kwargs = simulator_backend_kwargs(args, resource, capabilities_for_model(args.model))
    return SimulatorBackend(**kwargs)


def _parse_simulate_signal_specs(
    specs: Sequence[str], capabilities: ScopeCapabilities
) -> dict[int, SimulatedSignal]:
    signals: dict[int, SimulatedSignal] = {}
    for spec in specs:
        channel, signal = _parse_simulate_signal_spec(spec)
        validate_analog_channel(channel, capabilities)
        if channel in signals:
            raise KeysightScopeError(f"duplicate --simulate-signal for CH{channel}")
        signals[channel] = signal
    return signals


def _parse_simulate_signal_spec(spec: str) -> tuple[int, SimulatedSignal]:
    return parse_simulate_signal_spec(spec)


def _parse_simulate_signal_channel(token: str) -> int:
    normalized = token.strip().upper()
    if normalized.startswith("CH"):
        normalized = normalized[2:]
    try:
        channel = int(normalized)
    except ValueError as exc:
        raise KeysightScopeError(
            "--simulate-signal channel must be CHn or a positive integer"
        ) from exc
    if channel < 1:
        raise KeysightScopeError("--simulate-signal channel must be at least 1")
    return channel


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
    if command == "cursor":
        if args.cursor_query:
            commands = _cursor_query_commands()
            return commands + [":SYSTem:ERRor?"], [], {"operation": "query", "commands": commands}
        if args.cursor_off:
            return [":MARKer:MODE OFF", ":SYSTem:ERRor?"], [], {"operation": "off", "command": ":MARKer:MODE OFF"}
        if args.source_channel is None or args.x2 is None:
            raise KeysightScopeError("cursor configure requires --source-channel, --x1, and --x2")
        channel = validate_analog_channel(args.source_channel, capabilities)
        commands = cursor_configure_commands(
            channel,
            args.x1,
            args.x2,
            y1_volts=args.y1,
            y2_volts=args.y2,
            capabilities=capabilities,
        )
        auto_timebase = (
            cursor_auto_timebase_dry_run_plan()
            if getattr(args, "auto_timebase", False)
            else None
        )
        auto_vertical = (
            cursor_auto_vertical_dry_run_plan(channel)
            if getattr(args, "auto_vertical", False)
            else None
        )
        planned = (
            (list(auto_timebase.commands) if auto_timebase is not None else [])
            + (list(auto_vertical.commands) if auto_vertical is not None else [])
            + commands
        )
        result = {
            "operation": "set",
            "commands": commands,
            "source_channel": channel,
            "x1_seconds": args.x1,
            "x2_seconds": args.x2,
            "y1_volts": args.y1,
            "y2_volts": args.y2,
        }
        if auto_timebase is not None:
            result["auto_timebase"] = cursor_auto_timebase_json(auto_timebase)
        if auto_vertical is not None:
            result["auto_vertical"] = cursor_auto_vertical_json(auto_vertical)
        return planned + [":SYSTem:ERRor?"], [], result
    if command == "trigger-holdoff":
        if args.holdoff_query:
            return [trigger_holdoff_query(), ":SYSTem:ERRor?"], [], {"operation": "query", "command": trigger_holdoff_query()}
        seconds = validate_trigger_holdoff(args.holdoff_seconds)
        planned = trigger_holdoff_commands(seconds)
        return planned + [":SYSTem:ERRor?"], [], {"operation": "set", "command": planned[-1], "commands": planned, "seconds": seconds}
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
    if command == "measure-stats":
        channel = validate_analog_channel(args.channel, capabilities)
        items = _parse_stats_items(args.items)
        commands = _measure_stats_planned_scpi(channel, items, args.mode, reset=args.reset, max_count=args.max_count)
        return commands + [":SYSTem:ERRor?"], [], {"channel": channel, "items": list(items), "mode": args.mode, "reset": bool(args.reset), "max_count": args.max_count, "settle_seconds": args.settle_seconds, "records": []}
    if command == "doctor":
        planned = _doctor_planned_scpi(capabilities)
        return planned, [], {
            "backend": None,
            "timeout_ms": None,
            "acquisition": {},
            "channels": [],
            "timebase": {},
            "edge_trigger": {},
        }
    if command == "measure-sweep":
        channels = _resolve_sweep_channels(args.channel, capabilities)
        items = _parse_measurement_item_list(args.items, allow_pair=False)
        pairs = _parse_pair_specs(args.pair, capabilities)
        pair_items = _parse_measurement_item_list(args.pair_items, allow_pair=True)
        planned = _measure_sweep_planned_scpi(channels, items, pairs, pair_items, capabilities)
        return planned, [], {
            "channels": list(channels),
            "items": list(items),
            "pairs": [{"source_channel": source, "reference_channel": reference} for source, reference in pairs],
            "pair_items": list(pair_items),
            "measurements": [],
            "summary": {"valid_count": 0, "invalid_count": 0, "error_count": 0},
        }
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
    if command == "measure-log":
        channels = _resolve_capture_channels(args.channel or ("all",), capabilities)
        items = _parse_measurement_item_list(args.items, allow_pair=False)
        pairs = _parse_pair_specs(args.pair, capabilities)
        pair_items = _parse_measurement_item_list(args.pair_items, allow_pair=True)
        planned = _measure_log_planned_scpi(channels, items, pairs, pair_items, capabilities)
        files = _planned_measure_log_files(args)
        result = {
            "status": "planned",
            "channels": list(channels),
            "items": list(items),
            "pairs": [f"{src}:{ref}" for src, ref in pairs],
            "pair_items": list(pair_items),
            "interval_seconds": args.interval_seconds,
            "requested_count": args.count,
            "requested_duration_seconds": args.duration_seconds,
            "completed_rows": 0,
            "files": files,
            "manifest_path": files[1]["path"],
            "scpi_log_path": files[2]["path"],
            "csv_path": files[0]["path"],
        }
        return planned, files, result
    if command == "screenshot":
        png_path = Path(args.output_path) if args.output_path else _default_screenshot_path()
        files = [{"kind": "png", "path": str(png_path)}]
        return [hardcopy_inksaver_command(hardcopy_inksaver_for_background(args.background)), screenshot_data_query(), ":SYSTem:ERRor?"], files, {"format": "PNG", "background": args.background, "timeout_ms": SCREENSHOT_TIMEOUT_MS, "files": files, "png_path": str(png_path)}
    if command == "smoke":
        output_dir = Path(args.output_dir) if args.output_dir is not None else Path("data") / "hardware_smoke" / "DRY-RUN"
        files = _smoke_file_list(output_dir)
        planned = (
            _doctor_planned_scpi(capabilities)
            + [
                measurement_query("vpp", 1, capabilities=capabilities),
                measurement_query("vrms", 1, capabilities=capabilities),
            ]
            + _planned_waveform_scpi((1,), "byte", 1000)
            + [
                hardcopy_inksaver_command(hardcopy_inksaver_for_background("black")),
                screenshot_data_query(),
                ":SYSTem:ERRor?",
            ]
        )
        return planned, files, {
            "status": "planned",
            "output_dir": str(output_dir),
            "files": files,
            "doctor": {},
            "measurements": [],
            "capture": {},
            "screenshot": {},
            "warnings": [],
        }
    if command == "acquisition-check":
        average_count = validate_acquisition_count(args.average_count)
        check_only = bool(getattr(args, "check_only", False))
        stop_on_error = bool(getattr(args, "stop_on_error", False))
        restore_type = bool(getattr(args, "restore_type", False))
        if check_only and restore_type:
            raise KeysightScopeError("--check-only cannot be combined with --restore-type")
        output_dir = (
            Path(args.output_dir)
            if args.output_dir is not None
            else Path("data") / "hardware_acquisition" / "DRY-RUN"
        )
        files = _acquisition_check_file_list(output_dir)
        planned = _acquisition_check_planned_scpi(
            average_count,
            check_only=check_only,
            stop_on_error=stop_on_error,
            restore_type=restore_type,
        )
        return planned, files, {
            "status": "planned",
            "output_dir": str(output_dir),
            "report_path": str(output_dir / "report.json"),
            "scpi_log_path": str(output_dir / "scpi.log"),
            "average_count": average_count,
            "check_only": check_only,
            "stopped_on_error": False,
            "initial_acquisition": None,
            "restore": {
                "requested": restore_type,
                "attempted": False,
                "succeeded": None,
                "error": None,
            },
            "termination_reason": None,
            "steps": [],
            "final_acquisition": None,
            "files": files,
        }
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
    if command == "autoscale":
        channels = None if not args.source_channel else tuple(validate_analog_channel(channel, capabilities) for channel in args.source_channel)
        planned = autoscale_commands(channels, acquire_mode=args.acquire_mode, channels_mode=args.channels, capabilities=capabilities)
        return planned + [":SYSTem:ERRor?"], [], {"operation": "run", "commands": planned, "source_channels": None if channels is None else list(channels), "acquire_mode": args.acquire_mode, "channels": args.channels}
    if command == "setup-save":
        planned = [setup_save_command(slot=args.slot, file_spec=args.setup_file)]
        return planned + [":SYSTem:ERRor?"], [], {"operation": "save", "command": planned[0], "slot": args.slot, "file": args.setup_file}
    if command == "setup-recall":
        planned = [setup_recall_command(slot=args.slot, file_spec=args.setup_file)]
        return planned + [":SYSTem:ERRor?"], [], {"operation": "recall", "command": planned[0], "slot": args.slot, "file": args.setup_file}
    if command == "fft":
        if args.fft_query:
            if any(value is not None for value in (args.source_channel, args.units, args.window, args.center_hz, args.span_hz, args.display)):
                raise KeysightScopeError("--query cannot be combined with FFT configuration options")
            commands = fft_query_commands(args.function)
            return commands + [":SYSTem:ERRor?"], [], {"operation": "query", "commands": commands, "function": args.function}
        if args.source_channel is None:
            raise KeysightScopeError("fft configure requires --source-channel unless --query is used")
        commands = fft_configure_commands(
            args.function,
            args.source_channel,
            units=args.units,
            window=args.window,
            center_hz=args.center_hz,
            span_hz=args.span_hz,
            display=None if args.display is None else args.display == "on",
            capabilities=capabilities,
        )
        return commands + [":SYSTem:ERRor?"], [], {"operation": "set", "commands": commands, "function": args.function, "source_channel": args.source_channel, "units": args.units, "window": args.window, "center_hz": args.center_hz, "span_hz": args.span_hz, "display": args.display}
    return [], [], {}


def _acquisition_check_planned_scpi(
    average_count: int,
    *,
    check_only: bool = False,
    stop_on_error: bool = False,
    restore_type: bool = False,
) -> list[str]:
    if check_only:
        return ["*IDN?", acquisition_type_query(), acquisition_count_query(), ":SYSTem:ERRor?"]
    return [
        "*IDN?",
        acquisition_type_query(),
        acquisition_count_query(),
        ":SYSTem:ERRor?",
        acquisition_type_command("NORMal"),
        ":SYSTem:ERRor?",
        acquisition_type_command("AVERage"),
        acquisition_count_command(average_count),
        ":SYSTem:ERRor?",
        acquisition_type_query(),
        acquisition_count_query(),
        ":SYSTem:ERRor?",
        acquisition_type_command("HRESolution"),
        ":SYSTem:ERRor?",
        acquisition_type_command("PEAK"),
        ":SYSTem:ERRor?",
        acquisition_type_query(),
        acquisition_count_query(),
        ":SYSTem:ERRor?",
    ]


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


def _cursor_query_commands() -> list[str]:
    return [
        ":MARKer:MODE?",
        ":MARKer:X1Position?",
        ":MARKer:X2Position?",
        ":MARKer:Y1Position?",
        ":MARKer:Y2Position?",
        ":MARKer:XDELta?",
        ":MARKer:YDELta?",
        ":MARKer:DYDX?",
    ]


def _cursor_range_diagnostic(args: argparse.Namespace, entry) -> str | None:
    if (
        getattr(args, "command", None) != "cursor"
        or getattr(args, "cursor_query", False)
        or getattr(args, "cursor_off", False)
        or entry.code != -222
        or "data out of range" not in entry.message.lower()
    ):
        return None
    auto_timebase = getattr(args, "auto_timebase", False)
    auto_vertical = getattr(args, "auto_vertical", False)
    if auto_timebase and auto_vertical:
        return (
            "cursor position was rejected as out of range after auto adjustment; "
            "check instrument limits or manually adjust timebase scale and channel "
            "scale/offset"
        )
    if auto_timebase:
        return (
            "cursor Y position may be outside the current vertical display range; "
            "retry with cursor --auto-vertical, manually adjust channel scale/offset, "
            "or choose smaller Y cursor positions"
        )
    if auto_vertical:
        return (
            "cursor X position may be outside the current horizontal display range; "
            "retry with cursor --auto-timebase, use a wider timebase scale, or choose "
            "smaller X cursor positions"
        )
    return (
        "cursor position was rejected as out of range; retry with cursor "
        "--auto-timebase for X positions or cursor --auto-vertical for Y positions, "
        "or manually adjust the display range"
    )


def _measure_stats_planned_scpi(
    channel: int,
    items: Sequence[str],
    mode: str,
    *,
    reset: bool = False,
    max_count: int | None = None,
) -> list[str]:
    commands = [":MEASure:CLEar", f":MEASure:SOURce CHANnel{channel}"]
    commands.extend(statistics_install_command(item) for item in items)
    if reset:
        commands.append(":MEASure:STATistics:RESet")
    if max_count is not None:
        commands.append(f":MEASure:STATistics:COUNt {validate_statistics_max_count(max_count)}")
    commands.extend([f":MEASure:STATistics {statistics_mode_scpi(mode)}", ":MEASure:RESults?"])
    return commands


def _doctor_planned_scpi(capabilities: ScopeCapabilities) -> list[str]:
    planned = [
        "*IDN?",
        acquisition_type_query(),
        acquisition_count_query(),
    ]
    for channel in range(1, capabilities.analog_channels + 1):
        planned.extend(
            [
                channel_display_query(channel),
                channel_scale_query(channel),
                channel_offset_query(channel),
                channel_coupling_query(channel),
                channel_probe_ratio_query(channel),
                channel_bandwidth_limit_query(channel),
            ]
        )
    planned.extend(
        [
            timebase_scale_query(),
            timebase_position_query(),
            edge_trigger_source_query(),
            edge_trigger_level_query(),
            edge_trigger_slope_query(),
            ":SYSTem:ERRor?",
        ]
    )
    return planned


def _measure_sweep_planned_scpi(
    channels: Sequence[int],
    items: Sequence[str],
    pairs: Sequence[tuple[int, int]],
    pair_items: Sequence[str],
    capabilities: ScopeCapabilities,
) -> list[str]:
    planned = ["*IDN?"]
    for channel in channels:
        for item in items:
            planned.append(measurement_query(item, channel, capabilities=capabilities))
            planned.append(":SYSTem:ERRor?")
    for source_channel, reference_channel in pairs:
        for item in pair_items:
            try:
                planned.append(
                    pair_measurement_query(
                        item,
                        source_channel,
                        reference_channel,
                        capabilities=capabilities,
                    )
                )
                planned.append(":SYSTem:ERRor?")
            except KeysightScopeError:
                continue
    return planned


def _planned_capture_files(args: argparse.Namespace, command: str) -> list[dict[str, str]]:
    if command == "capture":
        csv_path = Path(args.csv_path) if args.csv_path is not None else _default_capture_csv_path()
        meta_path = Path(args.meta_path) if args.meta_path is not None else csv_path.with_name(f"{csv_path.stem}_meta.json")
        files = [{"kind": "csv", "path": str(csv_path)}, {"kind": "metadata", "path": str(meta_path)}]
        if args.plot_path is not None:
            files.append({"kind": "plot_png", "path": str(Path(args.plot_path))})
        return files
    output_dir = Path(args.output_dir) if args.output_dir is not None else Path("data") / "captures" / "DRY-RUN"
    files = [{"kind": "manifest", "path": str(output_dir / "manifest.json")}, {"kind": "scpi_log", "path": str(output_dir / "scpi.log")}]
    for index in range(1, args.count + 1):
        csv_path, meta_path = batch_capture_paths(output_dir, index, args.count)
        files.extend([{"kind": "csv", "path": str(csv_path)}, {"kind": "metadata", "path": str(meta_path)}])
    return files


def _planned_measure_log_files(args: argparse.Namespace) -> list[dict[str, str]]:
    output_dir = (
        Path(args.output_dir)
        if args.output_dir is not None
        else Path("data") / "measure_logs" / "DRY-RUN"
    )
    csv_path, manifest_path, scpi_log_path = measure_log_paths(output_dir)
    return [
        {"kind": "csv", "path": str(csv_path)},
        {"kind": "manifest", "path": str(manifest_path)},
        {"kind": "scpi_log", "path": str(scpi_log_path)},
    ]


def _measure_log_planned_scpi(
    channels: Sequence[int],
    items: Sequence[str],
    pairs: Sequence[tuple[int, int]],
    pair_items: Sequence[str],
    capabilities: ScopeCapabilities,
) -> list[str]:
    planned = []
    for channel in channels:
        for item in items:
            planned.append(measurement_query(item, channel, capabilities=capabilities))
    for source_channel, reference_channel in pairs:
        for item in pair_items:
            planned.append(
                pair_measurement_query(
                    item,
                    source_channel,
                    reference_channel,
                    capabilities=capabilities,
                )
            )
    planned.append(":SYSTem:ERRor?")
    return planned


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


def _measurement_statistics_json(result: MeasurementStatisticsResult) -> dict[str, object]:
    return {
        "channel": result.channel,
        "mode": result.mode,
        "raw_response": result.raw_response,
        "records": [
            {
                "item": record.item,
                "current": record.current,
                "minimum": record.minimum,
                "maximum": record.maximum,
                "mean": record.mean,
                "stddev": record.stddev,
                "count": record.count,
                "raw_values": list(record.raw_values),
            }
            for record in result.records
        ],
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


def _cmd_doctor(args: argparse.Namespace) -> int:
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

        snapshot = _doctor_snapshot(scope)
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        _json_update_result(**snapshot)

        print("Doctor snapshot:")
        print(f"Acquisition type: {snapshot['acquisition']['type']}")
        print(f"Average count: {snapshot['acquisition']['count']}")
        print(f"Channels: {_format_channel_list([item['channel'] for item in snapshot['channels']])}")
        print(f"Timebase scale: {snapshot['timebase']['scale_seconds_per_division']}")
        print(f"Timebase position: {snapshot['timebase']['position_seconds']}")
        trigger = snapshot["edge_trigger"]
        print(
            "Edge trigger: "
            f"CH{trigger['source_channel']}, {trigger['level_volts']:.12g} V, "
            f"{trigger['slope']}"
        )
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_measure_sweep(args: argparse.Namespace) -> int:
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

        channels = _resolve_sweep_channels(args.channel, scope.capabilities)
        items = _parse_measurement_item_list(args.items, allow_pair=False)
        pairs = _parse_pair_specs(args.pair, scope.capabilities)
        pair_items = _parse_measurement_item_list(args.pair_items, allow_pair=True)
        measurements: list[dict[str, object]] = []

        print(
            f"Planned sweep: {_format_channel_list(channels)}; "
            f"items {', '.join(items)}"
        )
        for channel in channels:
            for item in items:
                command = measurement_query(item, channel, capabilities=scope.capabilities)
                print(f"Command: {command}")
                measurements.append(_run_sweep_measurement(scope, command, channel, item))

        for source_channel, reference_channel in pairs:
            for item in pair_items:
                try:
                    command = pair_measurement_query(
                        item,
                        source_channel,
                        reference_channel,
                        capabilities=scope.capabilities,
                    )
                    print(f"Command: {command}")
                    measurements.append(
                        _run_sweep_pair_measurement(
                            scope,
                            command,
                            source_channel,
                            reference_channel,
                            item,
                        )
                    )
                except KeysightScopeError as exc:
                    measurements.append(
                        _sweep_error_record(
                            item=item,
                            channel=source_channel,
                            reference_channel=reference_channel,
                            command=None,
                            exc=exc,
                            system_error=None,
                        )
                    )

        summary = _measure_sweep_summary(measurements)
        _json_update_result(
            channels=list(channels),
            items=list(items),
            pairs=[
                {"source_channel": source, "reference_channel": reference}
                for source, reference in pairs
            ],
            pair_items=list(pair_items),
            measurements=measurements,
            summary=summary,
        )
        print(
            "Summary: "
            f"{summary['valid_count']} valid, "
            f"{summary['invalid_count']} invalid, "
            f"{summary['error_count']} errors"
        )
        return 1 if summary["invalid_count"] or summary["error_count"] else 0


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


def _cmd_measure_stats(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    _configure_scpi_logging(args)

    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1
        channel = validate_analog_channel(args.channel, scope.capabilities)
        items = _parse_stats_items(args.items)
        if args.max_count is not None:
            validate_statistics_max_count(args.max_count)
        if args.settle_seconds is not None:
            validate_statistics_settle_seconds(args.settle_seconds)
        print(f"Planned statistics: CH{channel}; items {', '.join(items)}")
        result = scope.query_measurement_statistics(
            channel,
            items,
            mode=args.mode,
            reset=args.reset,
            max_count=args.max_count,
            settle_seconds=args.settle_seconds,
        )
        _json_update_result(**_measurement_statistics_json(result))
        for command in _measure_stats_planned_scpi(
            channel,
            items,
            args.mode,
            reset=args.reset,
            max_count=args.max_count,
        ):
            print(f"Command: {command}")
        for record in result.records:
            print(
                f"{record.item}: current={_format_optional_number(record.current)}, "
                f"min={_format_optional_number(record.minimum)}, "
                f"max={_format_optional_number(record.maximum)}, "
                f"mean={_format_optional_number(record.mean)}, "
                f"stddev={_format_optional_number(record.stddev)}, "
                f"count={record.count}"
            )
        entry = scope.query_system_error()
        _json_record_system_error(entry)
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
    plot_path = Path(args.plot_path) if args.plot_path is not None else None

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
        time_axis_tolerance = None
        if (
            args.allow_time_axis_tolerance
            and isinstance(capture, MultiChannelWaveformCapture)
        ):
            time_axis_tolerance = waveform_time_axis_tolerance_summary(capture)
        written_csv = _write_capture_csv(
            capture,
            csv_path,
            allow_time_axis_tolerance=args.allow_time_axis_tolerance,
        )
        written_meta = _write_capture_metadata(
            capture,
            meta_path,
            idn=idn,
            resource=resource,
            time_axis_tolerance=time_axis_tolerance,
        )
        files = [{"kind": "csv", "path": str(written_csv)}, {"kind": "metadata", "path": str(written_meta)}]
        if plot_path is not None:
            written_plot = _write_capture_plot(capture, plot_path)
            files.append({"kind": "plot_png", "path": str(written_plot)})
        _json_set_files(files)
        result = {
            "channels": list(channels),
            "requested_points": points,
            "format": waveform_format,
            "files": files,
            **_waveform_capture_summary(capture),
        }
        if time_axis_tolerance is not None:
            result["time_axis_tolerance"] = time_axis_tolerance
        _json_update_result(**result)
        print(_format_actual_points(capture))
        print(f"CSV: {written_csv}")
        print(f"Metadata: {written_meta}")
        if plot_path is not None:
            print(f"Plot: {plot_path}")
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


def _cmd_measure_log(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    output_dir = prepare_measure_log_output_dir(args.output_dir)
    csv_path, manifest_path, scpi_log_path = measure_log_paths(output_dir)

    try:
        with capture_batch_scpi_logging(
            scpi_log_path,
            echo_to_stderr=args.log_scpi,
        ):
            with _open_scope(args, resource) as scope:
                idn = scope.query_idn()
                _json_record_scope(scope, idn)

                _print_session_header(scope, resource)
                print(f"Model: {idn.model}")
                print(f"Series: {idn.series or 'unknown'}")

                if scope.capabilities is None:
                    raise KeysightScopeError("Capabilities unavailable for this model")

                channels = _resolve_capture_channels(args.channel or ("all",), scope.capabilities)
                items = _parse_measurement_item_list(args.items, allow_pair=False)
                pairs = _parse_pair_specs(args.pair, scope.capabilities)
                pair_items = _parse_measurement_item_list(args.pair_items, allow_pair=True)

                _json_set_files([
                    {"kind": "csv", "path": str(csv_path)},
                    {"kind": "manifest", "path": str(manifest_path)},
                    {"kind": "scpi_log", "path": str(scpi_log_path)},
                ])
                _json_update_result(
                    status="running",
                    channels=list(channels),
                    items=list(items),
                    pairs=[f"{src}:{ref}" for src, ref in pairs],
                    pair_items=list(pair_items),
                    interval_seconds=args.interval_seconds,
                    requested_count=args.count,
                    requested_duration_seconds=args.duration_seconds,
                    completed_rows=0,
                    manifest_path=str(manifest_path),
                    scpi_log_path=str(scpi_log_path),
                    csv_path=str(csv_path),
                )

                code = log_measurements_workflow(
                    scope=scope,
                    resource=resource,
                    output_dir=output_dir,
                    csv_path=csv_path,
                    manifest_path=manifest_path,
                    scpi_log_path=scpi_log_path,
                    channels=list(channels),
                    items=list(items),
                    pairs=list(pairs),
                    pair_items=list(pair_items),
                    interval_seconds=args.interval_seconds,
                    requested_count=args.count,
                    requested_duration_seconds=args.duration_seconds,
                    stop_on_error=args.stop_on_error,
                )

                _update_measure_log_json_from_manifest(manifest_path)
                print(f"SCPI log: {scpi_log_path}")

                return code
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except OSError as exc:
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


def _cmd_smoke(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    output_dir = _prepare_smoke_output_dir(args.output_dir)
    report_path = output_dir / "report.json"
    scpi_log_path = output_dir / "scpi.log"
    capture_csv_path = output_dir / "capture.csv"
    capture_meta_path = output_dir / "capture_meta.json"
    screenshot_path = output_dir / "screen.png"
    files = _smoke_file_list(output_dir)
    _json_set_files(files)

    report: dict[str, object] = {
        "schema_version": 1,
        "start_time": batch_iso_timestamp(),
        "end_time": None,
        "status": "running",
        "resource": resource,
        "backend": None,
        "timeout_ms": None,
        "idn": None,
        "doctor": None,
        "measurements": [],
        "capture": None,
        "screenshot": None,
        "post_check_error": None,
        "warnings": [],
        "files": files,
        "error": None,
    }

    try:
        with capture_batch_scpi_logging(
            scpi_log_path,
            echo_to_stderr=args.log_scpi,
        ):
            with _open_scope(args, resource) as scope:
                idn = scope.query_idn()
                _json_record_scope(scope, idn)
                report["backend"] = getattr(scope.backend, "backend", None)
                report["timeout_ms"] = getattr(scope.backend, "timeout", None)
                report["idn"] = idn_manifest_dict(idn)
                _print_session_header(scope, resource)
                print(f"Model: {idn.model}")
                print(f"Series: {idn.series or 'unknown'}")
                if scope.capabilities is None:
                    raise KeysightScopeError("Capabilities unavailable for this model")

                doctor = _doctor_snapshot(scope)
                report["doctor"] = doctor
                measurements = []
                for item in ("vpp", "vrms"):
                    command = measurement_query(item, 1, capabilities=scope.capabilities)
                    print(f"Command: {command}")
                    measurement = scope.query_measurement(1, item)
                    record = {
                        "command": command,
                        **_measurement_result_json(measurement, parameters={}),
                        "system_error": None,
                    }
                    measurements.append(record)
                    if record.get("valid") is False:
                        warnings = report.setdefault("warnings", [])
                        if isinstance(warnings, list):
                            warnings.append(
                                f"CH1 {item} measurement invalid: {record.get('reason')}"
                            )
                report["measurements"] = measurements

                print("Planned capture: CH1, 1000 points, BYTE format")
                capture = scope.capture_waveform_byte(1, points=1000)
                written_csv = _write_capture_csv(capture, capture_csv_path)
                written_meta = _write_capture_metadata(
                    capture,
                    capture_meta_path,
                    idn=idn,
                    resource=resource,
                )
                report["capture"] = {
                    "csv": str(written_csv),
                    "metadata": str(written_meta),
                    **_waveform_capture_summary(capture),
                }

                print("Planned capture: current screen PNG image with black background")
                screenshot = scope.capture_screenshot_png(background="black")
                written_png = _write_screenshot_png(screenshot, screenshot_path)
                report["screenshot"] = {
                    "png_path": str(written_png),
                    "format": screenshot.format_name,
                    "palette": screenshot.palette,
                    "background": screenshot.background,
                    "byte_count": len(screenshot.data),
                }

                entry = scope.query_system_error()
                _json_record_system_error(entry)
                report["post_check_error"] = _system_error_json(entry)
                report["status"] = "instrument_error" if entry.is_error else "completed"
                report["end_time"] = batch_iso_timestamp()
                _write_json_file(report, report_path, file_kind="smoke report JSON")
                _json_update_result(
                    status=report["status"],
                    output_dir=str(output_dir),
                    report_path=str(report_path),
                    scpi_log_path=str(scpi_log_path),
                    files=files,
                    doctor=doctor,
                    measurements=measurements,
                    capture=report["capture"],
                    screenshot=report["screenshot"],
                    warnings=report["warnings"],
                )
                print(f"Output directory: {output_dir}")
                print(f"Report: {report_path}")
                print(f"SCPI log: {scpi_log_path}")
                print(f"System error: {entry.format()}")
                return 1 if entry.is_error else 0
    except KeysightScopeError as exc:
        report["status"] = "error"
        report["end_time"] = batch_iso_timestamp()
        report["error"] = str(exc)
        _json_update_result(
            status=report["status"],
            output_dir=str(output_dir),
            report_path=str(report_path),
            scpi_log_path=str(scpi_log_path),
            files=files,
            warnings=report["warnings"],
            error=str(exc),
        )
        _write_json_file_best_effort(report, report_path)
        raise
    except OSError as exc:
        report["status"] = "error"
        report["end_time"] = batch_iso_timestamp()
        report["error"] = str(exc)
        _write_json_file_best_effort(report, report_path)
        raise KeysightScopeError(
            _format_plain_output_file_error("smoke output", output_dir, exc)
        ) from exc


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


def _cmd_cursor(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2
    _configure_scpi_logging(args)
    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1
        if args.cursor_query:
            state = scope.query_cursor()
            _json_update_result(operation="query", **state.__dict__)
            for command in _cursor_query_commands():
                print(f"Command: {command}")
            print(f"Mode: {state.mode}")
            print(f"X delta s: {state.x_delta_seconds:.12g}")
            print(f"Y delta V: {state.y_delta_volts:.12g}")
        elif args.cursor_off:
            scope.cursor_off()
            _json_update_result(operation="off", command=":MARKer:MODE OFF")
            print("Command: :MARKer:MODE OFF")
        else:
            if args.source_channel is None or args.x2 is None:
                raise KeysightScopeError("cursor configure requires --source-channel, --x1, and --x2")
            channel = validate_analog_channel(args.source_channel, scope.capabilities)
            auto_timebase = None
            if getattr(args, "auto_timebase", False):
                scale = scope.query_timebase_scale()
                position = scope.query_timebase_position()
                auto_timebase = cursor_auto_timebase_plan(scale, position, args.x1, args.x2)
                for command in (timebase_scale_query(), timebase_position_query()):
                    print(f"Command: {command}")
                if auto_timebase.changed and auto_timebase.target_scale_seconds_per_division is not None:
                    scope.set_timebase_scale(auto_timebase.target_scale_seconds_per_division)
                    print(
                        "Command: "
                        f"{timebase_scale_command(auto_timebase.target_scale_seconds_per_division)}"
                    )
            auto_vertical = None
            if getattr(args, "auto_vertical", False):
                scale = scope.query_channel_scale(channel)
                offset = scope.query_channel_offset(channel)
                auto_vertical = cursor_auto_vertical_plan(
                    channel,
                    scale,
                    offset,
                    y1_volts=args.y1,
                    y2_volts=args.y2,
                    capabilities=scope.capabilities,
                )
                for command in (channel_scale_query(channel), channel_offset_query(channel)):
                    print(f"Command: {command}")
                if auto_vertical.changed:
                    assert auto_vertical.target_scale_volts_per_division is not None
                    assert auto_vertical.target_offset_volts is not None
                    scope.set_channel_scale(
                        channel,
                        auto_vertical.target_scale_volts_per_division,
                    )
                    print(
                        "Command: "
                        f"{channel_scale_command(channel, auto_vertical.target_scale_volts_per_division)}"
                    )
                    if auto_vertical.offset_changed:
                        scope.set_channel_offset(channel, auto_vertical.target_offset_volts)
                        print(
                            "Command: "
                            f"{channel_offset_command(channel, auto_vertical.target_offset_volts)}"
                        )
            scope.configure_cursor(channel, args.x1, args.x2, y1_volts=args.y1, y2_volts=args.y2)
            commands = cursor_configure_commands(
                channel,
                args.x1,
                args.x2,
                y1_volts=args.y1,
                y2_volts=args.y2,
                capabilities=scope.capabilities,
            )
            result = {
                "operation": "set",
                "commands": commands,
                "source_channel": channel,
                "x1_seconds": args.x1,
                "x2_seconds": args.x2,
                "y1_volts": args.y1,
                "y2_volts": args.y2,
            }
            if auto_timebase is not None:
                result["auto_timebase"] = cursor_auto_timebase_json(auto_timebase)
            if auto_vertical is not None:
                result["auto_vertical"] = cursor_auto_vertical_json(auto_vertical)
            _json_update_result(**result)
            for command in commands:
                print(f"Command: {command}")
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        diagnostic = _cursor_range_diagnostic(args, entry)
        if diagnostic is not None:
            _json_update_result(diagnostic=diagnostic)
            print(f"Diagnostic: {diagnostic}")
        return 1 if entry.is_error else 0


def _cmd_trigger_holdoff(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2
    _configure_scpi_logging(args)
    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        if args.holdoff_query:
            seconds = scope.query_trigger_holdoff()
            _json_update_result(operation="query", command=trigger_holdoff_query(), seconds=seconds)
            print(f"Command: {trigger_holdoff_query()}")
            print(f"Holdoff seconds: {seconds:.12g}")
        else:
            seconds = validate_trigger_holdoff(args.holdoff_seconds)
            scope.set_trigger_holdoff(seconds)
            commands = trigger_holdoff_commands(seconds)
            _json_update_result(operation="set", command=commands[-1], commands=commands, seconds=seconds)
            for command in commands:
                print(f"Command: {command}")
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_autoscale(args: argparse.Namespace) -> int:
    return _cmd_simple_advanced(args, "autoscale")


def _cmd_setup_save(args: argparse.Namespace) -> int:
    return _cmd_simple_advanced(args, "setup-save")


def _cmd_setup_recall(args: argparse.Namespace) -> int:
    return _cmd_simple_advanced(args, "setup-recall")


def _cmd_fft(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2
    _configure_scpi_logging(args)
    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1
        if args.fft_query:
            if any(value is not None for value in (args.source_channel, args.units, args.window, args.center_hz, args.span_hz, args.display)):
                raise KeysightScopeError("--query cannot be combined with FFT configuration options")
            state = scope.query_fft(args.function)
            _json_update_result(
                operation="query",
                function=state.function,
                fft_operation=state.operation,
                source_channel=state.source_channel,
                units=state.units,
                window=state.window,
                center_hz=state.center_hz,
                span_hz=state.span_hz,
                display=state.display,
            )
            for command in fft_query_commands(args.function):
                print(f"Command: {command}")
            print(f"Function: {state.function}")
            print(f"Source: CH{state.source_channel}")
        else:
            if args.source_channel is None:
                raise KeysightScopeError("fft configure requires --source-channel unless --query is used")
            display = None if args.display is None else args.display == "on"
            scope.configure_fft(args.function, args.source_channel, units=args.units, window=args.window, center_hz=args.center_hz, span_hz=args.span_hz, display=display)
            commands = fft_configure_commands(args.function, args.source_channel, units=args.units, window=args.window, center_hz=args.center_hz, span_hz=args.span_hz, display=display, capabilities=scope.capabilities)
            _json_update_result(operation="set", commands=commands, function=args.function, source_channel=args.source_channel)
            for command in commands:
                print(f"Command: {command}")
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _cmd_simple_advanced(args: argparse.Namespace, command_name: str) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2
    _configure_scpi_logging(args)
    with _open_scope(args, resource) as scope:
        idn = scope.query_idn()
        _json_record_scope(scope, idn)
        _print_session_header(scope, resource)
        print(f"Model: {idn.model}")
        if scope.capabilities is None:
            print("Capabilities: unavailable for this model")
            return 1
        if command_name == "autoscale":
            channels = None if not args.source_channel else tuple(validate_analog_channel(channel, scope.capabilities) for channel in args.source_channel)
            scope.autoscale(channels, acquire_mode=args.acquire_mode, channels_mode=args.channels)
            commands = autoscale_commands(channels, acquire_mode=args.acquire_mode, channels_mode=args.channels, capabilities=scope.capabilities)
            _json_update_result(operation="run", commands=commands, source_channels=None if channels is None else list(channels))
        elif command_name == "setup-save":
            scope.save_setup(slot=args.slot, file_spec=args.setup_file)
            commands = [setup_save_command(slot=args.slot, file_spec=args.setup_file)]
            _json_update_result(operation="save", command=commands[0], slot=args.slot, file=args.setup_file)
        else:
            scope.recall_setup(slot=args.slot, file_spec=args.setup_file)
            commands = [setup_recall_command(slot=args.slot, file_spec=args.setup_file)]
            _json_update_result(operation="recall", command=commands[0], slot=args.slot, file=args.setup_file)
        for command in commands:
            print(f"Command: {command}")
        if command_name == "autoscale" and not getattr(args, "simulate", False):
            print(
                "System error timeout ms: "
                f"{AUTOSCALE_SYSTEM_ERROR_TIMEOUT_MS} (temporary)"
            )
            entry = _query_system_error_with_temporary_timeout(
                scope, AUTOSCALE_SYSTEM_ERROR_TIMEOUT_MS
            )
            if entry.code == -113 and getattr(args, "source_channel", None):
                fallback_command = ":AUToscale"
                print(
                    "Autoscale source form was rejected; "
                    f"retrying with {fallback_command}"
                )
                scope.scpi.write(fallback_command)
                commands.append(fallback_command)
                _json_update_result(
                    commands=commands,
                    fallback="bare_autoscale_after_source_undefined_header",
                )
                entry = _query_system_error_with_temporary_timeout(
                    scope, AUTOSCALE_SYSTEM_ERROR_TIMEOUT_MS
                )
        else:
            entry = scope.query_system_error()
        _json_record_system_error(entry)
        print(f"System error: {entry.format()}")
        return 1 if entry.is_error else 0


def _query_system_error_with_temporary_timeout(scope: KeysightScope, timeout_ms: int):
    original_timeout = scope.scpi.timeout
    scope.scpi.set_timeout(timeout_ms)
    try:
        return scope.query_system_error()
    finally:
        scope.scpi.set_timeout(original_timeout)


def _cmd_acquisition_check(args: argparse.Namespace) -> int:
    resource = _require_resource(args)
    if resource is None:
        return 2

    average_count = validate_acquisition_count(args.average_count)
    check_only = bool(getattr(args, "check_only", False))
    stop_on_error = bool(getattr(args, "stop_on_error", False))
    restore_type = bool(getattr(args, "restore_type", False))
    if check_only and restore_type:
        raise KeysightScopeError("--check-only cannot be combined with --restore-type")
    output_dir = _prepare_acquisition_check_output_dir(args.output_dir)
    report_path = output_dir / "report.json"
    scpi_log_path = output_dir / "scpi.log"
    files = _acquisition_check_file_list(output_dir)
    _json_set_files(files)

    report: dict[str, object] = {
        "schema_version": 1,
        "start_time": batch_iso_timestamp(),
        "end_time": None,
        "status": "running",
        "resource": resource,
        "backend": None,
        "timeout_ms": None,
        "idn": None,
        "average_count": average_count,
        "check_only": check_only,
        "stopped_on_error": False,
        "initial_acquisition": None,
        "restore": {
            "requested": restore_type,
            "attempted": False,
            "succeeded": None,
            "error": None,
        },
        "termination_reason": None,
        "steps": [],
        "final_acquisition": None,
        "post_check_error": None,
        "files": files,
        "error": None,
    }

    try:
        with capture_batch_scpi_logging(
            scpi_log_path,
            echo_to_stderr=args.log_scpi,
        ):
            with _open_scope(args, resource) as scope:
                idn = scope.query_idn()
                _json_record_scope(scope, idn)
                report["backend"] = getattr(scope.backend, "backend", None)
                report["timeout_ms"] = getattr(scope.backend, "timeout", None)
                report["idn"] = idn_manifest_dict(idn)
                _print_session_header(scope, resource)
                print(f"Model: {idn.model}")
                print(f"Series: {idn.series or 'unknown'}")
                if scope.capabilities is None:
                    raise KeysightScopeError("Capabilities unavailable for this model")

                steps: list[dict[str, object]] = []
                if check_only:
                    initial_step = _run_acquisition_query_step(scope, "initial-query")
                    steps.append(initial_step)
                    report["initial_acquisition"] = initial_step.get("readback")
                    final_step = initial_step
                    report["termination_reason"] = "check_only"
                else:
                    initial_step = _run_acquisition_query_step(scope, "initial-query")
                    steps.append(initial_step)
                    report["initial_acquisition"] = initial_step.get("readback")
                    final_step = initial_step
                    for step_name, acquisition_type, step_count in (
                        ("set-normal", "normal", None),
                        ("set-average", "average", average_count),
                        ("set-high-resolution", "high_resolution", None),
                        ("set-peak", "peak", None),
                    ):
                        step = _run_acquisition_type_step(
                            scope,
                            step_name,
                            acquisition_type,
                            count=step_count,
                        )
                        steps.append(step)
                        if stop_on_error and step["status"] == "instrument_error":
                            report["stopped_on_error"] = True
                            report["termination_reason"] = "stopped_on_error"
                            final_step = step
                            break
                        if step_name == "set-average":
                            steps.append(_run_acquisition_query_step(scope, "post-average-query"))
                        final_step = step
                    if report["termination_reason"] is None:
                        report["termination_reason"] = "completed"
                    if not report["stopped_on_error"]:
                        final_step = _run_acquisition_query_step(scope, "final-query")
                        steps.append(final_step)

                report["steps"] = steps
                report["final_acquisition"] = final_step.get("readback")
                post_check = _system_error_from_step(final_step)
                report["post_check_error"] = post_check
                report["status"] = (
                    "instrument_error"
                    if any(_step_has_system_error(step) for step in steps)
                    else "completed"
                )
                if report["termination_reason"] == "completed" and report["status"] == "instrument_error":
                    report["termination_reason"] = "completed_with_errors"
                restore_error: KeysightScopeError | None = None
                if report["restore"]["requested"]:
                    report["restore"]["attempted"] = True
                    try:
                        _restore_acquisition_type(scope, report["initial_acquisition"])
                        report["restore"]["succeeded"] = True
                    except KeysightScopeError as exc:
                        report["restore"]["succeeded"] = False
                        report["restore"]["error"] = str(exc)
                        report["status"] = "error"
                        report["termination_reason"] = "restore_failed"
                        restore_error = exc
                report["end_time"] = batch_iso_timestamp()
                _write_json_file(report, report_path, file_kind="acquisition report JSON")
                _json_update_result(
                    status=report["status"],
                    output_dir=str(output_dir),
                    report_path=str(report_path),
                    scpi_log_path=str(scpi_log_path),
                    average_count=average_count,
                    check_only=check_only,
                    stopped_on_error=report["stopped_on_error"],
                    initial_acquisition=report["initial_acquisition"],
                    restore=report["restore"],
                    termination_reason=report["termination_reason"],
                    steps=steps,
                    final_acquisition=report["final_acquisition"],
                    files=files,
                )
                print(f"Output directory: {output_dir}")
                print(f"Report: {report_path}")
                print(f"SCPI log: {scpi_log_path}")
                if post_check is not None:
                    print(f"System error: {post_check['raw']}")
                if restore_error is not None:
                    raise restore_error
                return 1 if report["status"] == "instrument_error" else 0
    except KeysightScopeError as exc:
        report["status"] = "error"
        report["end_time"] = batch_iso_timestamp()
        report["error"] = str(exc)
        _json_update_result(
            status=report["status"],
            output_dir=str(output_dir),
            report_path=str(report_path),
            scpi_log_path=str(scpi_log_path),
            average_count=average_count,
            check_only=check_only,
            stopped_on_error=report["stopped_on_error"],
            initial_acquisition=report["initial_acquisition"],
            restore=report["restore"],
            termination_reason=report["termination_reason"],
            steps=report["steps"],
            final_acquisition=report["final_acquisition"],
            files=files,
            error=str(exc),
        )
        _write_json_file_best_effort(report, report_path)
        raise
    except OSError as exc:
        report["status"] = "error"
        report["end_time"] = batch_iso_timestamp()
        report["error"] = str(exc)
        _write_json_file_best_effort(report, report_path)
        raise KeysightScopeError(
            _format_plain_output_file_error("acquisition output", output_dir, exc)
        ) from exc


def _run_acquisition_query_step(scope: KeysightScope, name: str) -> dict[str, object]:
    commands = [acquisition_type_query(), acquisition_count_query(), ":SYSTem:ERRor?"]
    print(f"Step: {name}")
    print(f"Command: {commands[0]}")
    print(f"Command: {commands[1]}")
    config = scope.query_acquisition_config()
    entry = scope.query_system_error()
    _json_record_system_error(entry)
    print(f"Acquisition type: {config.type}")
    print(f"Average count: {config.count}")
    print(f"System error: {entry.format()}")
    return {
        "name": name,
        "operation": "query",
        "commands": commands,
        "readback": {"type": config.type, "count": config.count},
        "system_error": _system_error_json(entry),
        "status": "instrument_error" if entry.is_error else "completed",
    }


def _run_acquisition_system_error_step(scope: KeysightScope, name: str) -> dict[str, object]:
    command = ":SYSTem:ERRor?"
    print(f"Step: {name}")
    print(f"Command: {command}")
    entry = scope.query_system_error()
    _json_record_system_error(entry)
    print(f"System error: {entry.format()}")
    return {
        "name": name,
        "operation": "query_system_error",
        "commands": [command],
        "readback": None,
        "system_error": _system_error_json(entry),
        "status": "instrument_error" if entry.is_error else "completed",
    }


def _run_acquisition_type_step(
    scope: KeysightScope,
    name: str,
    acquisition_type: str,
    *,
    count: int | None = None,
) -> dict[str, object]:
    normalized = normalize_acquisition_type(acquisition_type)
    commands = [acquisition_type_command(normalized)]
    if count is not None:
        commands.append(acquisition_count_command(count))
    commands.append(":SYSTem:ERRor?")
    print(f"Step: {name}")
    for command in commands[:-1]:
        print(f"Command: {command}")
    scope.set_acquisition_type(acquisition_type)
    if count is not None:
        scope.set_acquisition_count(count)
    entry = scope.query_system_error()
    _json_record_system_error(entry)
    print(f"System error: {entry.format()}")
    return {
        "name": name,
        "operation": "set",
        "type": acquisition_type,
        "scpi_type": normalized,
        "count": count,
        "commands": commands,
        "readback": {
            "type": acquisition_type,
            "count": count,
        },
        "system_error": _system_error_json(entry),
        "status": "instrument_error" if entry.is_error else "completed",
    }


def _step_has_system_error(step: dict[str, object]) -> bool:
    system_error = step.get("system_error")
    return isinstance(system_error, dict) and bool(system_error.get("is_error"))


def _system_error_from_step(step: dict[str, object]) -> dict[str, object] | None:
    system_error = step.get("system_error")
    if isinstance(system_error, dict):
        return system_error
    return None


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


def _default_smoke_output_dir(now: datetime | None = None) -> Path:
    base_path = Path("data") / "hardware_smoke"
    if now is None:
        capture_time = datetime.now(_CAPTURE_DEFAULT_TIMEZONE)
    elif now.tzinfo is None:
        capture_time = now.replace(tzinfo=_CAPTURE_DEFAULT_TIMEZONE)
    else:
        capture_time = now.astimezone(_CAPTURE_DEFAULT_TIMEZONE)

    stem = capture_time.strftime("%Y-%m-%d-%H-%M-%S")
    candidate = base_path / stem
    suffix = 2
    while candidate.exists():
        candidate = base_path / f"{stem}-{suffix}"
        suffix += 1
    return candidate


def _default_acquisition_check_output_dir(now: datetime | None = None) -> Path:
    base_path = Path("data") / "hardware_acquisition"
    if now is None:
        capture_time = datetime.now(_CAPTURE_DEFAULT_TIMEZONE)
    elif now.tzinfo is None:
        capture_time = now.replace(tzinfo=_CAPTURE_DEFAULT_TIMEZONE)
    else:
        capture_time = now.astimezone(_CAPTURE_DEFAULT_TIMEZONE)

    stem = capture_time.strftime("%Y-%m-%d-%H-%M-%S")
    candidate = base_path / stem
    suffix = 2
    while candidate.exists():
        candidate = base_path / f"{stem}-{suffix}"
        suffix += 1
    return candidate


def _prepare_smoke_output_dir(output_dir: str | None) -> Path:
    path = Path(output_dir) if output_dir is not None else _default_smoke_output_dir()
    if path.exists():
        if not path.is_dir():
            raise KeysightScopeError(f"output directory path is not a directory: {path}")
        try:
            if any(path.iterdir()):
                raise KeysightScopeError(f"output directory must be empty: {path}")
        except OSError as exc:
            raise KeysightScopeError(
                f"could not inspect output directory {path}: {exc.strerror or exc}"
            ) from exc
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise KeysightScopeError(
            f"could not create output directory {path}: {exc.strerror or exc}"
        ) from exc
    return path


def _prepare_acquisition_check_output_dir(output_dir: str | None) -> Path:
    path = (
        Path(output_dir)
        if output_dir is not None
        else _default_acquisition_check_output_dir()
    )
    if path.exists():
        if not path.is_dir():
            raise KeysightScopeError(f"output directory path is not a directory: {path}")
        try:
            if any(path.iterdir()):
                raise KeysightScopeError(f"output directory must be empty: {path}")
        except OSError as exc:
            raise KeysightScopeError(
                f"could not inspect output directory {path}: {exc.strerror or exc}"
            ) from exc
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise KeysightScopeError(
            f"could not create output directory {path}: {exc.strerror or exc}"
        ) from exc
    return path


def _smoke_file_list(output_dir: Path) -> list[dict[str, str]]:
    return [
        {"kind": "report", "path": str(output_dir / "report.json")},
        {"kind": "scpi_log", "path": str(output_dir / "scpi.log")},
        {"kind": "csv", "path": str(output_dir / "capture.csv")},
        {"kind": "metadata", "path": str(output_dir / "capture_meta.json")},
        {"kind": "png", "path": str(output_dir / "screen.png")},
    ]


def _acquisition_check_file_list(output_dir: Path) -> list[dict[str, str]]:
    return [
        {"kind": "report", "path": str(output_dir / "report.json")},
        {"kind": "scpi_log", "path": str(output_dir / "scpi.log")},
    ]


def _restore_acquisition_type(scope: KeysightScope, initial_acquisition) -> None:
    if initial_acquisition is None:
        raise KeysightScopeError("initial acquisition state is unavailable for restore")
    if isinstance(initial_acquisition, dict):
        acquisition_type = initial_acquisition.get("type")
        count = initial_acquisition.get("count")
    else:
        acquisition_type = initial_acquisition.type
        count = initial_acquisition.count
    if not isinstance(acquisition_type, str):
        raise KeysightScopeError("initial acquisition state is unavailable for restore")
    scope.set_acquisition_type(acquisition_type)
    if acquisition_type == "average":
        scope.set_acquisition_count(count)


def _cmd_hardware_report(args: argparse.Namespace) -> int:
    for index, path_text in enumerate(args.report_paths):
        path = Path(path_text)
        report = _load_report_json(path)
        if index:
            print()
        print(_render_hardware_report(report, path))
    return 0


def _load_report_json(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise KeysightScopeError(
            _format_plain_output_file_error("report JSON", path, exc)
        ) from exc
    except json.JSONDecodeError as exc:
        raise KeysightScopeError(f"could not parse report JSON {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise KeysightScopeError(f"report JSON must contain an object: {path}")
    return data


def _render_hardware_report(report: dict[str, object], path: Path) -> str:
    report_type = _detect_hardware_report_type(report)
    lines = [f"# Hardware Report: {path}"]
    lines.append(f"- Type: {report_type}")
    lines.append(f"- Status: {report.get('status')}")
    lines.append(f"- Model: {_report_model(report)}")
    lines.append(f"- Firmware: {_report_firmware(report)}")
    lines.append(f"- Resource: {_report_resource(report)}")
    lines.append(f"- Backend: {_report_backend(report)}")
    lines.append("")
    lines.append("## Commands")
    for command in _report_commands(report):
        lines.append(f"- {command}")
    lines.append("")
    lines.append("## Output Files")
    for kind, file_path in _report_files(report):
        lines.append(f"- {kind}: {file_path}")
    lines.append("")
    lines.append("## Result")
    lines.extend(_render_report_result(report))
    errors = _report_errors(report)
    if errors:
        lines.append("")
        lines.append("## Errors")
        lines.extend(errors)
    cleanup = _report_cleanup(report)
    if cleanup:
        lines.append("")
        lines.append("## Cleanup")
        lines.extend(cleanup)
    return "\n".join(lines)


def _detect_hardware_report_type(report: dict[str, object]) -> str:
    if "doctor" in report or "capture" in report or "screenshot" in report:
        return "smoke"
    if "steps" in report or "average_count" in report or "check_only" in report:
        return "acquisition-check"
    return "unknown"


def _report_model(report: dict[str, object]) -> str:
    idn = report.get("idn")
    if isinstance(idn, dict):
        model = idn.get("model")
        if isinstance(model, str) and model:
            return model
    return "unknown"


def _report_firmware(report: dict[str, object]) -> str:
    idn = report.get("idn")
    if isinstance(idn, dict):
        firmware = idn.get("firmware")
        if isinstance(firmware, str) and firmware:
            return firmware
    return "unknown"


def _report_resource(report: dict[str, object]) -> str:
    value = report.get("resource")
    return str(value) if value is not None else "unknown"


def _report_backend(report: dict[str, object]) -> str:
    value = report.get("backend")
    return str(value) if value is not None else "unknown"


def _report_commands(report: dict[str, object]) -> list[str]:
    commands: list[str] = []
    if report.get("idn") is not None:
        commands.append("*IDN?")
    steps = report.get("steps")
    saw_final_error_query = False
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_commands = step.get("commands")
            if isinstance(step_commands, list):
                commands.extend(str(command) for command in step_commands)
            if step.get("name") in {"final-query", "final-system-error"}:
                saw_final_error_query = True
    if isinstance(report.get("capture"), dict):
        commands.extend(["<capture waveform>", "<capture screenshot>"])
    if saw_final_error_query and ":SYSTem:ERRor?" not in commands:
        commands.append(":SYSTem:ERRor?")
    return commands or ["unknown"]


def _report_files(report: dict[str, object]) -> list[tuple[str, str]]:
    files = []
    for entry in report.get("files", []):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        path = entry.get("path")
        if isinstance(kind, str) and isinstance(path, str):
            files.append((kind, path))
    if not files:
        if "report" in report:
            files.append(("report", str(report.get("report"))))
    return files


def _render_report_result(report: dict[str, object]) -> list[str]:
    lines: list[str] = []
    status = report.get("status")
    lines.append(f"- Status: {status}")
    if "average_count" in report:
        lines.append(f"- Average Count: {report.get('average_count')}")
    if "check_only" in report:
        lines.append(f"- Check Only: {report.get('check_only')}")
    if "stopped_on_error" in report:
        lines.append(f"- Stopped On Error: {report.get('stopped_on_error')}")
    if report.get("initial_acquisition") is not None:
        lines.append(f"- Initial Acquisition: {report.get('initial_acquisition')}")
    if report.get("final_acquisition") is not None:
        lines.append(f"- Final Acquisition: {report.get('final_acquisition')}")
    if report.get("termination_reason") is not None:
        lines.append(f"- Termination Reason: {report.get('termination_reason')}")
    if isinstance(report.get("doctor"), dict):
        lines.append(f"- Doctor: {report.get('doctor')}")
    if isinstance(report.get("measurements"), list):
        lines.append(f"- Measurements: {len(report.get('measurements', []))}")
    if isinstance(report.get("capture"), dict):
        lines.append(f"- Capture: {report.get('capture')}")
    if isinstance(report.get("screenshot"), dict):
        lines.append(f"- Screenshot: {report.get('screenshot')}")
    if report.get("post_check_error") is not None:
        lines.append(f"- Post Check Error: {report.get('post_check_error')}")
    return lines


def _report_errors(report: dict[str, object]) -> list[str]:
    lines: list[str] = []
    error = report.get("error")
    if error is not None:
        lines.append(f"- Report Error: {error}")
    restore = report.get("restore")
    if isinstance(restore, dict):
        restore_error = restore.get("error")
        if restore_error is not None:
            lines.append(f"- Restore Error: {restore_error}")
    for step in report.get("steps", []):
        if not isinstance(step, dict):
            continue
        system_error = step.get("system_error")
        if isinstance(system_error, dict) and system_error.get("is_error"):
            lines.append(
                f"- {step.get('name')}: {system_error.get('code')} {system_error.get('message')}"
            )
    return lines


def _report_cleanup(report: dict[str, object]) -> list[str]:
    lines: list[str] = []
    restore = report.get("restore")
    if isinstance(restore, dict):
        lines.append(f"- Restore Requested: {restore.get('requested')}")
        lines.append(f"- Restore Attempted: {restore.get('attempted')}")
        lines.append(f"- Restore Succeeded: {restore.get('succeeded')}")
    return lines


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


def _format_optional_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


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


def _resolve_sweep_channels(
    raw_channels: Sequence[int | str] | None,
    capabilities: ScopeCapabilities,
) -> tuple[int, ...]:
    return _resolve_capture_channels(raw_channels or ("all",), capabilities)


def _parse_measurement_item_list(value: str, *, allow_pair: bool) -> tuple[str, ...]:
    items = []
    for token in value.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        item = normalize_measurement_item(stripped)
        if allow_pair:
            if not is_pair_measurement_item(item):
                raise KeysightScopeError(
                    "--pair-items can only contain phase or delay measurements"
                )
        elif is_pair_measurement_item(item):
            raise KeysightScopeError(
                "--items can only contain single-channel measurements"
            )
        items.append(item)
    if not items:
        option = "--pair-items" if allow_pair else "--items"
        raise KeysightScopeError(f"{option} must contain at least one measurement item")
    return tuple(items)


def _parse_stats_items(value: str) -> tuple[str, ...]:
    items = tuple(token.strip() for token in value.split(",") if token.strip())
    try:
        return validate_statistics_items(items)
    except KeysightScopeError:
        raise


def _parse_pair_specs(
    values: Sequence[str],
    capabilities: ScopeCapabilities,
) -> tuple[tuple[int, int], ...]:
    pairs = []
    for value in values:
        parts = value.split(":")
        if len(parts) != 2:
            raise KeysightScopeError("--pair must use SRC:REF, for example 1:2")
        try:
            source = int(parts[0])
            reference = int(parts[1])
        except ValueError as exc:
            raise KeysightScopeError("--pair channels must be integers") from exc
        source = validate_analog_channel(source, capabilities)
        reference = validate_analog_channel(reference, capabilities)
        if source == reference:
            raise KeysightScopeError("--pair source and reference channels must differ")
        pairs.append((source, reference))
    return tuple(pairs)


def _doctor_snapshot(scope: KeysightScope) -> dict[str, object]:
    if scope.capabilities is None:
        raise KeysightScopeError("Capabilities unavailable for this model")
    acquisition = scope.query_acquisition_config()
    channels = []
    for channel in range(1, scope.capabilities.analog_channels + 1):
        channels.append(
            {
                "channel": channel,
                "display": scope.query_channel_display(channel),
                "scale_volts_per_division": scope.query_channel_scale(channel),
                "offset_volts": scope.query_channel_offset(channel),
                "coupling": scope.query_channel_coupling(channel),
                "probe_ratio": scope.query_channel_probe_ratio(channel),
                "bandwidth_limit": scope.query_channel_bandwidth_limit(channel),
            }
        )
    timebase = {
        "scale_seconds_per_division": scope.query_timebase_scale(),
        "position_seconds": scope.query_timebase_position(),
    }
    trigger = scope.query_edge_trigger()
    return {
        **_scope_backend_json(scope),
        "acquisition": {
            "type": acquisition.type,
            "count": acquisition.count,
        },
        "channels": channels,
        "timebase": timebase,
        "edge_trigger": {
            "source_channel": trigger.source_channel,
            "level_volts": trigger.level_volts,
            "slope": trigger.slope,
        },
    }


def _run_sweep_measurement(
    scope: KeysightScope,
    command: str,
    channel: int,
    item: str,
) -> dict[str, object]:
    try:
        result = scope.query_measurement(channel, item)
        system_error = scope.query_system_error()
        _json_record_system_error(system_error)
        return {
            "command": command,
            **_measurement_result_json(result, parameters={}),
            "system_error": _system_error_json(system_error),
        }
    except KeysightScopeError as exc:
        system_error = _query_system_error_best_effort(scope)
        return _sweep_error_record(
            item=item,
            channel=channel,
            reference_channel=None,
            command=command,
            exc=exc,
            system_error=system_error,
        )


def _run_sweep_pair_measurement(
    scope: KeysightScope,
    command: str,
    source_channel: int,
    reference_channel: int,
    item: str,
) -> dict[str, object]:
    try:
        result = scope.query_pair_measurement(source_channel, reference_channel, item)
        system_error = scope.query_system_error()
        _json_record_system_error(system_error)
        return {
            "command": command,
            **_measurement_result_json(result, parameters={}),
            "system_error": _system_error_json(system_error),
        }
    except KeysightScopeError as exc:
        system_error = _query_system_error_best_effort(scope)
        return _sweep_error_record(
            item=item,
            channel=source_channel,
            reference_channel=reference_channel,
            command=command,
            exc=exc,
            system_error=system_error,
        )


def _query_system_error_best_effort(scope: KeysightScope):
    try:
        entry = scope.query_system_error()
        _json_record_system_error(entry)
        return entry
    except KeysightScopeError:
        return None


def _sweep_error_record(
    *,
    item: str,
    channel: int,
    reference_channel: int | None,
    command: str | None,
    exc: KeysightScopeError,
    system_error,
) -> dict[str, object]:
    return {
        "item": item,
        "channel": channel,
        "reference_channel": reference_channel,
        "value": None,
        "unit": None,
        "valid": False,
        "raw_value": None,
        "reason": str(exc),
        "command": command,
        "system_error": None if system_error is None else _system_error_json(system_error),
        "error": {"type": type(exc).__name__, "message": str(exc)},
    }


def _measure_sweep_summary(measurements: Sequence[dict[str, object]]) -> dict[str, int]:
    valid_count = 0
    invalid_count = 0
    error_count = 0
    for measurement in measurements:
        if measurement.get("error") is not None:
            error_count += 1
        elif measurement.get("valid") is True:
            valid_count += 1
        else:
            invalid_count += 1
    return {
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "error_count": error_count,
    }


def _write_capture_csv(
    capture: WaveformCapture | MultiChannelWaveformCapture,
    csv_path: Path,
    *,
    allow_time_axis_tolerance: bool = False,
) -> Path:
    try:
        if isinstance(capture, MultiChannelWaveformCapture):
            return write_waveforms_csv(
                capture,
                csv_path,
                allow_time_axis_tolerance=allow_time_axis_tolerance,
            )
        return write_waveform_csv(capture, csv_path)
    except OSError as exc:
        raise KeysightScopeError(_format_output_file_error("CSV", csv_path, exc)) from exc


def _write_capture_metadata(
    capture: WaveformCapture | MultiChannelWaveformCapture,
    meta_path: Path,
    *,
    idn,
    resource: str,
    time_axis_tolerance: dict[str, object] | None = None,
) -> Path:
    try:
        if isinstance(capture, MultiChannelWaveformCapture):
            if time_axis_tolerance is None:
                return write_waveforms_metadata(
                    capture,
                    meta_path,
                    idn=idn,
                    resource=resource,
                )
            return write_waveforms_metadata(
                capture,
                meta_path,
                idn=idn,
                resource=resource,
                time_axis_tolerance=time_axis_tolerance,
            )
        return write_waveform_metadata(capture, meta_path, idn=idn, resource=resource)
    except OSError as exc:
        raise KeysightScopeError(
            _format_output_file_error("metadata JSON", meta_path, exc)
        ) from exc


def _write_capture_plot(
    capture: WaveformCapture | MultiChannelWaveformCapture,
    plot_path: Path,
) -> Path:
    try:
        return write_waveform_plot_png(capture, plot_path)
    except OSError as exc:
        raise KeysightScopeError(
            _format_plain_output_file_error("waveform plot PNG", plot_path, exc)
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


def _update_measure_log_json_from_manifest(manifest_path: Path) -> None:
    if _JSON_RECORD is None:
        return
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest_data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return

    rows = manifest_data.get("rows")
    last_system_error = None
    if isinstance(rows, list) and rows:
        last_row = rows[-1]
        if isinstance(last_row, dict):
            last_system_error = last_row.get("system_error")
            if isinstance(last_system_error, dict):
                _JSON_RECORD["system_error"] = last_system_error

    _json_update_result(
        status=manifest_data.get("status"),
        completed_rows=manifest_data.get("completed_rows", 0),
        error=manifest_data.get("error"),
        rows=rows if isinstance(rows, list) else [],
    )


def _write_json_file(
    payload: dict[str, object],
    path: Path,
    *,
    file_kind: str,
) -> Path:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path
    except OSError as exc:
        raise KeysightScopeError(_format_plain_output_file_error(file_kind, path, exc)) from exc


def _write_json_file_best_effort(payload: dict[str, object], path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
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


def _holdoff_seconds_arg(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    try:
        return validate_trigger_holdoff(parsed)
    except KeysightScopeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _setup_slot_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0 or parsed > 9:
        raise argparse.ArgumentTypeError("must be between 0 and 9")
    return parsed


def _positive_plain_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not parsed == parsed or parsed in (float("inf"), float("-inf")):
        raise argparse.ArgumentTypeError("must be finite")
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


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
