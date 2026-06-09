"""Analog channel controls."""

from __future__ import annotations

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


def channel_display_command(channel: int, enabled: bool) -> str:
    """Build the SCPI command for analog channel display control."""

    state = "ON" if enabled else "OFF"
    return f":CHANnel{channel}:DISPlay {state}"


def channel_display_query(channel: int) -> str:
    """Build the SCPI query for analog channel display state."""

    return f":CHANnel{channel}:DISPlay?"


def parse_channel_display(raw: str) -> bool:
    """Parse a channel display query response."""

    normalized = raw.strip().upper()
    if normalized in {"1", "+1", "ON"}:
        return True
    if normalized in {"0", "+0", "OFF"}:
        return False
    raise ChannelResponseError(f"Could not parse channel display response: {raw!r}")
