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
    "ac_rms": ":MEASure:VRMS? DISPlay,AC,CHANnel{channel}",
    "minimum": ":MEASure:VMIN? CHANnel{channel}",
    "maximum": ":MEASure:VMAX? CHANnel{channel}",
    "x_at_max": ":MEASure:XMAX? CHANnel{channel}",
    "x_at_min": ":MEASure:XMIN? CHANnel{channel}",
    "rise_time": ":MEASure:RISetime? CHANnel{channel}",
    "fall_time": ":MEASure:FALLtime? CHANnel{channel}",
    "amplitude": ":MEASure:VAMPlitude? CHANnel{channel}",
    "top": ":MEASure:VTOP? CHANnel{channel}",
    "base": ":MEASure:VBASe? CHANnel{channel}",
    "overshoot": ":MEASure:OVERshoot? CHANnel{channel}",
    "preshoot": ":MEASure:PREShoot? CHANnel{channel}",
    "positive_width": ":MEASure:PWIDth? CHANnel{channel}",
    "negative_width": ":MEASure:NWIDth? CHANnel{channel}",
    "duty_cycle": ":MEASure:DUTYcycle? CHANnel{channel}",
    "negative_duty_cycle": ":MEASure:NDUTy? CHANnel{channel}",
    "area": ":MEASure:AREA? CHANnel{channel}",
    "positive_edges": ":MEASure:PEDGes? CHANnel{channel}",
    "negative_edges": ":MEASure:NEDGes? CHANnel{channel}",
    "positive_pulses": ":MEASure:PPULses? CHANnel{channel}",
    "negative_pulses": ":MEASure:NPULses? CHANnel{channel}",
}

_MEASUREMENT_ALIASES = {
    "freq": "frequency",
    "acrms": "ac_rms",
    "vrms_ac": "ac_rms",
    "min": "minimum",
    "vmin": "minimum",
    "max": "maximum",
    "vmax": "maximum",
    "xmax": "x_at_max",
    "x-at-max": "x_at_max",
    "xmin": "x_at_min",
    "x-at-min": "x_at_min",
    "risetime": "rise_time",
    "rise-time": "rise_time",
    "falltime": "fall_time",
    "fall-time": "fall_time",
    "vamp": "amplitude",
    "vtop": "top",
    "vbase": "base",
    "pwidth": "positive_width",
    "positive-width": "positive_width",
    "pwid": "positive_width",
    "nwidth": "negative_width",
    "negative-width": "negative_width",
    "nwid": "negative_width",
    "duty": "duty_cycle",
    "dutycycle": "duty_cycle",
    "duty-cycle": "duty_cycle",
    "nduty": "negative_duty_cycle",
    "negative-duty": "negative_duty_cycle",
    "negative-duty-cycle": "negative_duty_cycle",
    "pedges": "positive_edges",
    "positive-edges": "positive_edges",
    "nedges": "negative_edges",
    "negative-edges": "negative_edges",
    "ppulses": "positive_pulses",
    "positive-pulses": "positive_pulses",
    "npulses": "negative_pulses",
    "negative-pulses": "negative_pulses",
}

_MEASUREMENT_UNITS = {
    "vpp": "V",
    "frequency": "Hz",
    "period": "s",
    "vavg": "V",
    "vrms": "V",
    "ac_rms": "V",
    "minimum": "V",
    "maximum": "V",
    "x_at_max": "s",
    "x_at_min": "s",
    "rise_time": "s",
    "fall_time": "s",
    "amplitude": "V",
    "top": "V",
    "base": "V",
    "overshoot": "%",
    "preshoot": "%",
    "positive_width": "s",
    "negative_width": "s",
    "duty_cycle": "%",
    "negative_duty_cycle": "%",
    "area": "V*s",
    "positive_edges": "count",
    "negative_edges": "count",
    "positive_pulses": "count",
    "negative_pulses": "count",
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
