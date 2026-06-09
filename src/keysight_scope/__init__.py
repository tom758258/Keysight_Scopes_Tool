"""Keysight InfiniiVision oscilloscope helpers."""

from .capabilities import ScopeCapabilities, capabilities_for_model
from .idn import IDN, detect_series, parse_idn
from .scope import KeysightScope

__all__ = [
    "IDN",
    "KeysightScope",
    "ScopeCapabilities",
    "capabilities_for_model",
    "detect_series",
    "parse_idn",
]

__version__ = "0.1.0"
