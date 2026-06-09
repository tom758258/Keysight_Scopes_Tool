"""Analog channel controls."""

from __future__ import annotations

import math

from .capabilities import ScopeCapabilities
from .errors import ChannelResponseError, ParameterValidationError
from .scpi import SCPIClient


class ChannelController:
    """Controls for analog oscilloscope channels."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def set_display(self, channel: int, enabled: bool) -> None:
        """Turn one analog channel display on or off."""

        channel = validate_analog_channel(channel, self.capabilities)
        self.scpi.write(channel_display_command(channel, enabled))

    def query_display(self, channel: int) -> bool:
        """Query whether one analog channel display is enabled."""

        channel = validate_analog_channel(channel, self.capabilities)
        return parse_channel_display(self.scpi.query(channel_display_query(channel)))

    def set_scale(self, channel: int, volts_per_division: float) -> None:
        """Set one analog channel vertical scale in volts per division."""

        channel = validate_analog_channel(channel, self.capabilities)
        volts_per_division = validate_channel_scale(volts_per_division)
        self.scpi.write(channel_scale_command(channel, volts_per_division))

    def query_scale(self, channel: int) -> float:
        """Query one analog channel vertical scale in volts per division."""

        channel = validate_analog_channel(channel, self.capabilities)
        return parse_channel_float(self.scpi.query(channel_scale_query(channel)), "scale")

    def set_offset(self, channel: int, volts: float) -> None:
        """Set one analog channel vertical offset in volts."""

        channel = validate_analog_channel(channel, self.capabilities)
        volts = validate_channel_offset(volts)
        self.scpi.write(channel_offset_command(channel, volts))

    def query_offset(self, channel: int) -> float:
        """Query one analog channel vertical offset in volts."""

        channel = validate_analog_channel(channel, self.capabilities)
        return parse_channel_float(self.scpi.query(channel_offset_query(channel)), "offset")

    def set_coupling(self, channel: int, coupling: str) -> None:
        """Set one analog channel input coupling."""

        channel = validate_analog_channel(channel, self.capabilities)
        coupling = normalize_channel_coupling(coupling)
        self.scpi.write(channel_coupling_command(channel, coupling))

    def query_coupling(self, channel: int) -> str:
        """Query one analog channel input coupling."""

        channel = validate_analog_channel(channel, self.capabilities)
        return parse_channel_coupling(self.scpi.query(channel_coupling_query(channel)))

    def set_probe_ratio(self, channel: int, ratio: float) -> None:
        """Set one analog channel probe attenuation ratio."""

        channel = validate_analog_channel(channel, self.capabilities)
        ratio = validate_probe_ratio(ratio)
        self.scpi.write(channel_probe_ratio_command(channel, ratio))

    def query_probe_ratio(self, channel: int) -> float:
        """Query one analog channel probe attenuation ratio."""

        channel = validate_analog_channel(channel, self.capabilities)
        return parse_channel_float(
            self.scpi.query(channel_probe_ratio_query(channel)),
            "probe ratio",
        )

    def set_bandwidth_limit(self, channel: int, enabled: bool) -> None:
        """Turn one analog channel bandwidth limit on or off."""

        channel = validate_analog_channel(channel, self.capabilities)
        self.scpi.write(channel_bandwidth_limit_command(channel, enabled))

    def query_bandwidth_limit(self, channel: int) -> bool:
        """Query whether one analog channel bandwidth limit is enabled."""

        channel = validate_analog_channel(channel, self.capabilities)
        return parse_channel_bool(
            self.scpi.query(channel_bandwidth_limit_query(channel)),
            "bandwidth limit",
        )


def validate_analog_channel(channel: int, capabilities: ScopeCapabilities) -> int:
    """Validate an analog channel number against a capability profile."""

    if channel < 1:
        raise ParameterValidationError("channel must be at least 1.")

    max_channel = capabilities.analog_channels
    if channel > max_channel:
        raise ParameterValidationError(
            f"channel {channel} is not available on this scope; valid range is 1-{max_channel}."
        )
    return channel


def validate_channel_scale(volts_per_division: float) -> float:
    """Validate a vertical scale value before sending it to the instrument."""

    try:
        value = float(volts_per_division)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("channel scale must be a number.") from exc
    if not math.isfinite(value):
        raise ParameterValidationError("channel scale must be a finite number.")
    if value <= 0:
        raise ParameterValidationError("channel scale must be greater than 0 V/div.")
    return value


def validate_channel_offset(volts: float) -> float:
    """Validate a vertical offset value before sending it to the instrument."""

    try:
        value = float(volts)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("channel offset must be a number.") from exc
    if not math.isfinite(value):
        raise ParameterValidationError("channel offset must be a finite number.")
    return value


def validate_probe_ratio(ratio: float) -> float:
    """Validate a probe attenuation ratio before sending it to the instrument."""

    try:
        value = float(ratio)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("probe ratio must be a number.") from exc
    if not math.isfinite(value):
        raise ParameterValidationError("probe ratio must be a finite number.")
    if value <= 0:
        raise ParameterValidationError("probe ratio must be greater than 0.")
    return value


def normalize_channel_coupling(coupling: str) -> str:
    """Normalize a supported analog channel input coupling."""

    normalized = str(coupling).strip().lower()
    if normalized in {"ac", "dc"}:
        return normalized
    raise ParameterValidationError("channel coupling must be 'ac' or 'dc'.")


def channel_display_command(channel: int, enabled: bool) -> str:
    """Build the SCPI command for analog channel display control."""

    state = "ON" if enabled else "OFF"
    return f":CHANnel{channel}:DISPlay {state}"


def channel_display_query(channel: int) -> str:
    """Build the SCPI query for analog channel display state."""

    return f":CHANnel{channel}:DISPlay?"


def channel_scale_command(channel: int, volts_per_division: float) -> str:
    """Build the SCPI command for analog channel vertical scale."""

    return f":CHANnel{channel}:SCALe {_format_scpi_float(volts_per_division)}"


def channel_scale_query(channel: int) -> str:
    """Build the SCPI query for analog channel vertical scale."""

    return f":CHANnel{channel}:SCALe?"


def channel_offset_command(channel: int, volts: float) -> str:
    """Build the SCPI command for analog channel vertical offset."""

    return f":CHANnel{channel}:OFFSet {_format_scpi_float(volts)}"


def channel_offset_query(channel: int) -> str:
    """Build the SCPI query for analog channel vertical offset."""

    return f":CHANnel{channel}:OFFSet?"


def channel_coupling_command(channel: int, coupling: str) -> str:
    """Build the SCPI command for analog channel input coupling."""

    normalized = normalize_channel_coupling(coupling)
    return f":CHANnel{channel}:COUPling {normalized.upper()}"


def channel_coupling_query(channel: int) -> str:
    """Build the SCPI query for analog channel input coupling."""

    return f":CHANnel{channel}:COUPling?"


def channel_probe_ratio_command(channel: int, ratio: float) -> str:
    """Build the SCPI command for analog channel probe attenuation ratio."""

    ratio = validate_probe_ratio(ratio)
    return f":CHANnel{channel}:PROBe {_format_scpi_float(ratio)}"


def channel_probe_ratio_query(channel: int) -> str:
    """Build the SCPI query for analog channel probe attenuation ratio."""

    return f":CHANnel{channel}:PROBe?"


def channel_bandwidth_limit_command(channel: int, enabled: bool) -> str:
    """Build the SCPI command for analog channel bandwidth limit control."""

    state = "ON" if enabled else "OFF"
    return f":CHANnel{channel}:BWLimit {state}"


def channel_bandwidth_limit_query(channel: int) -> str:
    """Build the SCPI query for analog channel bandwidth limit state."""

    return f":CHANnel{channel}:BWLimit?"


def parse_channel_display(raw: str) -> bool:
    """Parse a channel display query response."""

    return parse_channel_bool(raw, "display")


def parse_channel_bool(raw: str, setting_name: str) -> bool:
    """Parse a channel boolean query response."""

    normalized = raw.strip().upper()
    if normalized in {"1", "+1", "ON"}:
        return True
    if normalized in {"0", "+0", "OFF"}:
        return False
    raise ChannelResponseError(
        f"Could not parse channel {setting_name} response: {raw!r}"
    )


def parse_channel_coupling(raw: str) -> str:
    """Parse a channel coupling query response."""

    normalized = raw.strip().lower()
    if normalized in {"ac", "dc"}:
        return normalized
    raise ChannelResponseError(f"Could not parse channel coupling response: {raw!r}")


def parse_channel_float(raw: str, setting_name: str) -> float:
    """Parse a numeric channel query response."""

    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise ChannelResponseError(
            f"Could not parse channel {setting_name} response: {raw!r}"
        ) from exc
    if not math.isfinite(value):
        raise ChannelResponseError(
            f"Could not parse channel {setting_name} response: {raw!r}"
        )
    return value


def _format_scpi_float(value: float) -> str:
    return f"{value:.12g}"
