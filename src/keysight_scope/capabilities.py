"""Conservative model capability profiles."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .errors import UnsupportedModelError
from .idn import detect_series


@dataclass(frozen=True)
class ScopeCapabilities:
    """Conservative capability profile for an oscilloscope model."""

    series: str
    analog_channels: int
    default_waveform_points: int
    safe_max_waveform_points: int
    supports_word_format: bool
    supports_raw_points_mode: bool
    supports_measurements: bool
    supports_screenshot: bool
    supports_segmented_memory: bool
    supports_serial_decode: bool


_BASE_PROFILES = {
    "2000X": ScopeCapabilities(
        series="2000X",
        analog_channels=4,
        default_waveform_points=1000,
        safe_max_waveform_points=10000,
        supports_word_format=False,
        supports_raw_points_mode=False,
        supports_measurements=False,
        supports_screenshot=False,
        supports_segmented_memory=False,
        supports_serial_decode=False,
    ),
    "3000X": ScopeCapabilities(
        series="3000X",
        analog_channels=4,
        default_waveform_points=1000,
        safe_max_waveform_points=10000,
        supports_word_format=False,
        supports_raw_points_mode=False,
        supports_measurements=False,
        supports_screenshot=False,
        supports_segmented_memory=False,
        supports_serial_decode=False,
    ),
    "4000X": ScopeCapabilities(
        series="4000X",
        analog_channels=4,
        default_waveform_points=1000,
        safe_max_waveform_points=10000,
        supports_word_format=False,
        supports_raw_points_mode=False,
        supports_measurements=False,
        supports_screenshot=False,
        supports_segmented_memory=False,
        supports_serial_decode=False,
    ),
}

SUPPORTED_SERIES = tuple(_BASE_PROFILES)
_CHANNEL_COUNT_RE = re.compile(r"^(?:DSO|MSO)X\d{3}(?P<channels>[24])[A-Z]?$", re.IGNORECASE)


def capabilities_for_model(model: str) -> ScopeCapabilities:
    """Return the conservative capability profile for a model string."""

    series = detect_series(model)
    if series is None or series not in _BASE_PROFILES:
        raise UnsupportedModelError(f"Unsupported or unrecognized oscilloscope model: {model}")

    channels = _channel_count_from_model(model)
    profile = _BASE_PROFILES[series]
    if channels is None:
        return profile
    return replace(profile, analog_channels=channels)


def _channel_count_from_model(model: str) -> int | None:
    match = _CHANNEL_COUNT_RE.match(model.strip().upper())
    if match is None:
        return None
    return int(match.group("channels"))
