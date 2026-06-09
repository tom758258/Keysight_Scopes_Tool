"""Keysight InfiniiVision oscilloscope helpers."""

from .capabilities import ScopeCapabilities, capabilities_for_model
from .channel import ChannelController, parse_channel_display
from .idn import IDN, detect_series, parse_idn
from .scope import KeysightScope
from .status import SystemErrorEntry, parse_system_error
from .timebase import TimebaseController

__all__ = [
    "ChannelController",
    "IDN",
    "KeysightScope",
    "ScopeCapabilities",
    "SystemErrorEntry",
    "TimebaseController",
    "capabilities_for_model",
    "detect_series",
    "parse_channel_display",
    "parse_idn",
    "parse_system_error",
]

__version__ = "0.1.0"
