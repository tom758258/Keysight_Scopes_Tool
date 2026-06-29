"""Trigger controls."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .capabilities import ScopeCapabilities
from .channel import validate_analog_channel
from .errors import ParameterValidationError, TriggerResponseError
from .scpi import SCPIClient


_SLOPE_COMMANDS = {
    "positive": "POSitive",
    "pos": "POSitive",
    "rising": "POSitive",
    "negative": "NEGative",
    "neg": "NEGative",
    "falling": "NEGative",
    "either": "EITHer",
    "eith": "EITHer",
    "alternate": "ALTernate",
    "alt": "ALTernate",
}

_SLOPE_READBACKS = {
    "POS": "positive",
    "POSITIVE": "positive",
    "NEG": "negative",
    "NEGATIVE": "negative",
    "EITH": "either",
    "EITHER": "either",
    "ALT": "alternate",
    "ALTERNATE": "alternate",
}


@dataclass(frozen=True)
class EdgeTriggerState:
    """Readback state for analog edge trigger settings."""

    source_channel: int
    level_volts: float
    slope: str


class EdgeTriggerController:
    """Controls for analog edge trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(self, source_channel: int, level_volts: float, slope: str) -> None:
        """Configure analog edge trigger source, level, and slope."""

        source_channel = validate_analog_channel(source_channel, self.capabilities)
        level_volts = validate_trigger_level(level_volts)
        slope_command = normalize_edge_slope(slope)
        self.scpi.write(trigger_mode_edge_command())
        self.scpi.write(edge_trigger_source_command(source_channel))
        self.scpi.write(edge_trigger_level_command(level_volts))
        self.scpi.write(edge_trigger_slope_command(slope_command))

    def query(self) -> EdgeTriggerState:
        """Query analog edge trigger source, level, and slope."""

        source_channel = parse_edge_trigger_source(self.scpi.query(edge_trigger_source_query()))
        validate_analog_channel(source_channel, self.capabilities)
        level_volts = parse_trigger_float(self.scpi.query(edge_trigger_level_query()), "level")
        slope = parse_edge_slope(self.scpi.query(edge_trigger_slope_query()))
        return EdgeTriggerState(source_channel=source_channel, level_volts=level_volts, slope=slope)


def validate_trigger_level(level_volts: float) -> float:
    """Validate a trigger level before sending it to the instrument."""

    try:
        value = float(level_volts)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("trigger level must be a number.") from exc
    if not math.isfinite(value):
        raise ParameterValidationError("trigger level must be a finite number.")
    return value


def normalize_edge_slope(slope: str) -> str:
    """Normalize a user-facing edge slope into a SCPI argument."""

    normalized = slope.strip().lower()
    try:
        return _SLOPE_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "edge trigger slope must be one of: positive, negative, either, alternate."
        ) from exc


def trigger_mode_edge_command() -> str:
    """Build the SCPI command that selects edge trigger mode."""

    return ":TRIGger:MODE EDGE"


def edge_trigger_source_command(channel: int) -> str:
    """Build the SCPI command for analog edge trigger source."""

    return f":TRIGger:EDGE:SOURce CHANnel{channel}"


def edge_trigger_source_query() -> str:
    """Build the SCPI query for edge trigger source."""

    return ":TRIGger:EDGE:SOURce?"


def edge_trigger_level_command(level_volts: float) -> str:
    """Build the SCPI command for edge trigger level."""

    return f":TRIGger:EDGE:LEVel {_format_scpi_float(level_volts)}"


def edge_trigger_level_query() -> str:
    """Build the SCPI query for edge trigger level."""

    return ":TRIGger:EDGE:LEVel?"


def edge_trigger_slope_command(slope_command: str) -> str:
    """Build the SCPI command for edge trigger slope."""

    return f":TRIGger:EDGE:SLOPe {slope_command}"


def edge_trigger_slope_query() -> str:
    """Build the SCPI query for edge trigger slope."""

    return ":TRIGger:EDGE:SLOPe?"


def parse_edge_trigger_source(raw: str) -> int:
    """Parse an edge trigger source readback into an analog channel number."""

    normalized = raw.strip().upper()
    if normalized.startswith("CHANNEL"):
        suffix = normalized.removeprefix("CHANNEL")
    elif normalized.startswith("CHAN"):
        suffix = normalized.removeprefix("CHAN")
    else:
        raise TriggerResponseError(f"Could not parse edge trigger source response: {raw!r}")

    try:
        channel = int(suffix)
    except ValueError as exc:
        raise TriggerResponseError(f"Could not parse edge trigger source response: {raw!r}") from exc
    if channel < 1:
        raise TriggerResponseError(f"Could not parse edge trigger source response: {raw!r}")
    return channel


def parse_edge_slope(raw: str) -> str:
    """Parse an edge trigger slope readback."""

    normalized = raw.strip().upper()
    try:
        return _SLOPE_READBACKS[normalized]
    except KeyError as exc:
        raise TriggerResponseError(f"Could not parse edge trigger slope response: {raw!r}") from exc


def parse_trigger_float(raw: str, setting_name: str) -> float:
    """Parse a numeric trigger query response."""

    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise TriggerResponseError(
            f"Could not parse trigger {setting_name} response: {raw!r}"
        ) from exc
    if not math.isfinite(value):
        raise TriggerResponseError(f"Could not parse trigger {setting_name} response: {raw!r}")
    return value


def _format_scpi_float(value: float) -> str:
    return f"{value:.12g}"


def force_trigger_command() -> str:
    """Return the SCPI command that forces one trigger event.

    The command is a one-shot state-changing write. It must not be combined with
    trigger wait loops, acquisition completion polling, or capture workflows.
    """

    return ":TRIGger:FORCe"
