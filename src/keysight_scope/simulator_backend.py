"""Deterministic hardware-free backend for agent workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .errors import BackendClosedError


def simulator_idn(model: str) -> str:
    """Return a deterministic IDN string for a simulated model."""

    return f"KEYSIGHT TECHNOLOGIES,{model},SIM000000,07.20"


@dataclass
class SimulatorBackend:
    """Small oscilloscope simulator that records SCPI command order."""

    model: str = "DSOX4024A"
    resource_name: str | None = None
    history: list[str] = field(default_factory=list)
    backend: str = "Keysight simulator"
    timeout: int | None = 2000
    closed: bool = False
    channel_display: dict[int, bool] = field(default_factory=dict)
    channel_scale: dict[int, float] = field(default_factory=dict)
    channel_offset: dict[int, float] = field(default_factory=dict)
    channel_coupling: dict[int, str] = field(default_factory=dict)
    channel_probe: dict[int, float] = field(default_factory=dict)
    channel_bandwidth_limit: dict[int, bool] = field(default_factory=dict)
    waveform_source: int = 1
    waveform_format: str = "BYTE"
    waveform_points: int = 1000
    hardcopy_inksaver: bool = False
    acquisition_type: str = "NORMal"
    acquisition_count: int = 8
    timebase_scale: float = 1e-3
    timebase_position: float = 0.0
    trigger_source: int = 1
    trigger_level: float = 0.0
    trigger_slope: str = "POSitive"

    def __post_init__(self) -> None:
        if self.resource_name is None:
            self.resource_name = f"SIM::{self.model}::INSTR"

    def write(self, command: str) -> None:
        """Record and apply a simple SCPI write."""

        self._ensure_open()
        self.history.append(command)
        upper = command.upper()
        if upper.startswith(":WAVEFORM:SOURCE CHANNEL"):
            self.waveform_source = int(command.rsplit("CHANnel", 1)[1])
        elif upper == ":WAVEFORM:FORMAT BYTE":
            self.waveform_format = "BYTE"
        elif upper == ":WAVEFORM:FORMAT WORD":
            self.waveform_format = "WORD"
        elif upper.startswith(":WAVEFORM:POINTS "):
            self.waveform_points = int(command.rsplit(" ", 1)[1])
        elif upper.startswith(":HARDCOPY:INKSAVER "):
            self.hardcopy_inksaver = upper.endswith(" ON")
        elif upper.startswith(":ACQUIRE:TYPE "):
            self.acquisition_type = command.rsplit(" ", 1)[1]
        elif upper.startswith(":ACQUIRE:COUNT "):
            self.acquisition_count = int(command.rsplit(" ", 1)[1])
        elif upper.startswith(":TIMEBASE:SCALE "):
            self.timebase_scale = float(command.rsplit(" ", 1)[1])
        elif upper.startswith(":TIMEBASE:POSITION "):
            self.timebase_position = float(command.rsplit(" ", 1)[1])
        elif upper.startswith(":TRIGGER:EDGE:SOURCE CHANNEL"):
            self.trigger_source = int(command.rsplit("CHANnel", 1)[1])
        elif upper.startswith(":TRIGGER:EDGE:LEVEL "):
            self.trigger_level = float(command.rsplit(" ", 1)[1])
        elif upper.startswith(":TRIGGER:EDGE:SLOPE "):
            self.trigger_slope = command.rsplit(" ", 1)[1]
        else:
            self._apply_channel_write(command)

    def query(self, command: str) -> str:
        """Record one query and return a deterministic response."""

        self._ensure_open()
        self.history.append(command)
        upper = command.upper()
        if upper == "*IDN?":
            return simulator_idn(self.model)
        if upper == ":SYSTEM:ERROR?":
            return '+0,"No error"'
        if upper == ":WAVEFORM:PREAMBLE?":
            return self._waveform_preamble()
        if upper == ":HARDCOPY:INKSAVER?":
            return "1" if self.hardcopy_inksaver else "0"
        if upper == ":ACQUIRE:TYPE?":
            return self.acquisition_type
        if upper == ":ACQUIRE:COUNT?":
            return str(self.acquisition_count)
        if upper == ":TIMEBASE:SCALE?":
            return f"{self.timebase_scale:.12g}"
        if upper == ":TIMEBASE:POSITION?":
            return f"{self.timebase_position:.12g}"
        if upper == ":TRIGGER:EDGE:SOURCE?":
            return f"CHANnel{self.trigger_source}"
        if upper == ":TRIGGER:EDGE:LEVEL?":
            return f"{self.trigger_level:.12g}"
        if upper == ":TRIGGER:EDGE:SLOPE?":
            return self.trigger_slope
        if upper.startswith(":MEASURE:") or upper.startswith(":MEASURE?"):
            return self._measurement_value(command)
        channel_response = self._query_channel(command)
        if channel_response is not None:
            return channel_response
        return "0"

    def read_raw(self) -> bytes:
        """Return empty raw bytes; current CLI uses binary queries instead."""

        self._ensure_open()
        return b""

    def query_binary_values(self, command: str, **kwargs: Any) -> Sequence[Any]:
        """Record one binary query and return waveform or PNG bytes."""

        self._ensure_open()
        self.history.append(command)
        if command.upper().startswith(":DISPLAY:DATA?"):
            return tuple(_SIMULATED_PNG)
        count = max(2, min(self.waveform_points, 1000))
        if kwargs.get("datatype") == "H":
            return tuple(32768 + ((index + self.waveform_source) % 64) for index in range(count))
        return tuple(128 + ((index + self.waveform_source) % 32) for index in range(count))

    def set_timeout(self, timeout_ms: int | None) -> None:
        """Set simulated timeout."""

        self._ensure_open()
        self.timeout = timeout_ms

    def close(self) -> None:
        """Close the simulated session."""

        self.closed = True

    def _ensure_open(self) -> None:
        if self.closed:
            raise BackendClosedError("Simulator backend is closed.")

    def _waveform_preamble(self) -> str:
        points = max(2, min(self.waveform_points, 1000))
        if self.waveform_format == "WORD":
            return f"1,0,{points},1,1.0E-6,0,0,1.0E-4,0,32768"
        return f"0,0,{points},1,1.0E-6,0,0,2.0E-2,-2.56,128"

    def _measurement_value(self, command: str) -> str:
        upper = command.upper()
        if "FREQUENCY" in upper:
            return "1.000000E+3"
        if "PERIOD" in upper:
            return "1.000000E-3"
        if "PHASE" in upper:
            return "4.500000E+1"
        if "DELAY" in upper or "TIME" in upper or "RISE" in upper or "FALL" in upper:
            return "1.000000E-6"
        if "EDGE" in upper or "PULSE" in upper:
            return "5"
        return f"{0.25 * self.waveform_source:.6E}"

    def _apply_channel_write(self, command: str) -> None:
        channel = _extract_channel(command)
        if channel is None:
            return
        upper = command.upper()
        value = command.rsplit(" ", 1)[1] if " " in command else ""
        if ":DISPLAY " in upper:
            self.channel_display[channel] = upper.endswith(" ON")
        elif ":SCALE " in upper:
            self.channel_scale[channel] = float(value)
        elif ":OFFSET " in upper:
            self.channel_offset[channel] = float(value)
        elif ":COUPLING " in upper:
            self.channel_coupling[channel] = value.upper()
        elif ":PROBE " in upper:
            self.channel_probe[channel] = float(value)
        elif ":BWLIMIT " in upper:
            self.channel_bandwidth_limit[channel] = upper.endswith(" ON")

    def _query_channel(self, command: str) -> str | None:
        channel = _extract_channel(command)
        if channel is None:
            return None
        upper = command.upper()
        if ":DISPLAY?" in upper:
            return "1" if self.channel_display.get(channel, True) else "0"
        if ":SCALE?" in upper:
            return f"{self.channel_scale.get(channel, 1.0):.12g}"
        if ":OFFSET?" in upper:
            return f"{self.channel_offset.get(channel, 0.0):.12g}"
        if ":COUPLING?" in upper:
            return self.channel_coupling.get(channel, "DC")
        if ":PROBE?" in upper:
            return f"{self.channel_probe.get(channel, 10.0):.12g}"
        if ":BWLIMIT?" in upper:
            return "1" if self.channel_bandwidth_limit.get(channel, False) else "0"
        return None


def _extract_channel(command: str) -> int | None:
    marker = ":CHANnel"
    if marker not in command:
        return None
    remainder = command.split(marker, 1)[1]
    digits = []
    for char in remainder:
        if char.isdigit():
            digits.append(char)
        else:
            break
    return int("".join(digits)) if digits else None


_SIMULATED_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\xf6\x178U"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
