"""Read-only oscilloscope measurement queries."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .capabilities import ScopeCapabilities
from .channel import validate_analog_channel
from .errors import MeasurementResponseError, ParameterValidationError
from .scpi import SCPIClient

INVALID_MEASUREMENT_SENTINEL_ABS_MIN = 9.0e37
INVALID_MEASUREMENT_REASON = "invalid measurement sentinel"

_MEASUREMENT_QUERY_TEMPLATES = {
    "vpp": ":MEASure:VPP? CHANnel{channel}",
    "frequency": ":MEASure:FREQuency? CHANnel{channel}",
    "period": ":MEASure:PERiod? CHANnel{channel}",
    "vavg": ":MEASure:VAVerage? DISPlay,CHANnel{channel}",
    "vrms": ":MEASure:VRMS? DISPlay,DC,CHANnel{channel}",
    "minimum": ":MEASure:VMIN? CHANnel{channel}",
    "maximum": ":MEASure:VMAX? CHANnel{channel}",
    "rise_time": ":MEASure:RISetime? CHANnel{channel}",
    "fall_time": ":MEASure:FALLtime? CHANnel{channel}",
}

_MEASUREMENT_ALIASES = {
    "freq": "frequency",
    "min": "minimum",
    "vmin": "minimum",
    "max": "maximum",
    "vmax": "maximum",
    "risetime": "rise_time",
    "rise-time": "rise_time",
    "falltime": "fall_time",
    "fall-time": "fall_time",
}

_MEASUREMENT_UNITS = {
    "vpp": "V",
    "frequency": "Hz",
    "period": "s",
    "vavg": "V",
    "vrms": "V",
    "minimum": "V",
    "maximum": "V",
    "rise_time": "s",
    "fall_time": "s",
}

SUPPORTED_MEASUREMENT_ITEMS = tuple(_MEASUREMENT_QUERY_TEMPLATES)
MEASUREMENT_ITEM_CHOICES = SUPPORTED_MEASUREMENT_ITEMS + tuple(_MEASUREMENT_ALIASES)


@dataclass(frozen=True)
class MeasurementResult:
    """Parsed result from one read-only measurement query."""

    item: str
    channel: int
    value: float | None
    raw_value: str
    valid: bool
    unit: str
    reason: str | None = None


class MeasurementController:
    """Read-only measurement query controls."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def query(self, channel: int, item: str) -> MeasurementResult:
        """Query one measurement without changing acquisition or display state."""

        channel = validate_analog_channel(channel, self.capabilities)
        item = normalize_measurement_item(item)
        raw = self.scpi.query(measurement_query(item, channel))
        return parse_measurement_result(raw, item=item, channel=channel)


def normalize_measurement_item(item: str) -> str:
    """Normalize a user-facing measurement item."""

    normalized = item.strip().lower()
    normalized = _MEASUREMENT_ALIASES.get(normalized, normalized)
    if normalized not in _MEASUREMENT_QUERY_TEMPLATES:
        supported = ", ".join(MEASUREMENT_ITEM_CHOICES)
        raise ParameterValidationError(f"measurement item must be one of: {supported}.")
    return normalized


def measurement_query(item: str, channel: int) -> str:
    """Build a read-only measurement query for one analog channel."""

    item = normalize_measurement_item(item)
    return _MEASUREMENT_QUERY_TEMPLATES[item].format(channel=channel)


def measurement_unit(item: str) -> str:
    """Return the display unit for a supported measurement item."""

    return _MEASUREMENT_UNITS[normalize_measurement_item(item)]


def parse_measurement_result(raw: str, *, item: str, channel: int) -> MeasurementResult:
    """Parse a numeric measurement response, preserving invalid sentinels."""

    item = normalize_measurement_item(item)
    raw_value = raw.strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise MeasurementResponseError(f"Could not parse measurement response: {raw!r}") from exc

    if not math.isfinite(value):
        raise MeasurementResponseError(f"Could not parse measurement response: {raw!r}")

    if abs(value) >= INVALID_MEASUREMENT_SENTINEL_ABS_MIN:
        return MeasurementResult(
            item=item,
            channel=channel,
            value=None,
            raw_value=raw_value,
            valid=False,
            unit=measurement_unit(item),
            reason=INVALID_MEASUREMENT_REASON,
        )

    return MeasurementResult(
        item=item,
        channel=channel,
        value=value,
        raw_value=raw_value,
        valid=True,
        unit=measurement_unit(item),
    )
