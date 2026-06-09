"""Deterministic hardware-free backend for agent workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Sequence

from .errors import BackendClosedError, KeysightScopeError


class SimulatorBackendError(KeysightScopeError):
    """Raised when the simulator receives unsupported SCPI."""


_SUPPORTED_WAVEFORM_POINTS = (1000, 5000, 10000)
_INVALID_MEASUREMENT_SENTINEL = "9.9E+37"
_SIGNAL_FREQUENCY_HZ = 1000.0


def simulator_idn(model: str) -> str:
    """Return a deterministic IDN string for a simulated model."""

    return f"KEYSIGHT TECHNOLOGIES,{model},SIM000000,07.20"


@dataclass
class SimulatorBackend:
    """Small oscilloscope simulator that records SCPI command order."""

    model: str = "DSOX4024A"
    resource_name: str | None = None
    strict_unknown_commands: bool = True
    system_errors: list[str] = field(default_factory=list)
    query_overrides: dict[str, str] = field(default_factory=dict)
    binary_overrides: dict[str, Sequence[Any]] = field(default_factory=dict)
    write_failures: dict[str, Exception] = field(default_factory=dict)
    query_failures: dict[str, Exception] = field(default_factory=dict)
    binary_failures: dict[str, Exception] = field(default_factory=dict)
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
    waveform_byte_order: str = "MSBFirst"
    waveform_unsigned: bool = True
    hardcopy_inksaver: bool = False
    acquisition_type: str = "NORMal"
    acquisition_count: int = 8
    run_state: str = "stopped"
    timebase_scale: float = 1e-3
    timebase_position: float = 0.0
    trigger_source: int = 1
    trigger_mode: str = "EDGE"
    trigger_level: float = 0.0
    trigger_slope: str = "POSitive"
    invalid_measurement_channels: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.resource_name is None:
            self.resource_name = f"SIM::{self.model}::INSTR"
        self.system_errors = list(self.system_errors)

    def write(self, command: str) -> None:
        """Record and apply a simple SCPI write."""

        self._ensure_open()
        self.history.append(command)
        self._raise_configured_failure(self.write_failures, command)
        upper = command.upper()
        if upper in {":RUN", ":STOP", ":SINGLE"}:
            self.run_state = {"RUN": "running", "STOP": "stopped", "SINGLE": "single"}[upper[1:]]
        elif upper.startswith(":WAVEFORM:SOURCE CHANNEL"):
            self.waveform_source = int(command.rsplit("CHANnel", 1)[1])
        elif upper == ":WAVEFORM:FORMAT BYTE":
            self.waveform_format = "BYTE"
        elif upper == ":WAVEFORM:FORMAT WORD":
            self.waveform_format = "WORD"
        elif upper.startswith(":WAVEFORM:BYTEORDER "):
            self.waveform_byte_order = command.rsplit(" ", 1)[1]
        elif upper.startswith(":WAVEFORM:UNSIGNED "):
            self.waveform_unsigned = upper.endswith(" ON")
        elif upper.startswith(":WAVEFORM:POINTS "):
            points = int(command.rsplit(" ", 1)[1])
            if points not in _SUPPORTED_WAVEFORM_POINTS:
                if self.strict_unknown_commands:
                    raise SimulatorBackendError(
                        f"Unsupported simulator waveform point count: {points}"
                    )
                points = 1000
            self.waveform_points = points
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
        elif upper.startswith(":TRIGGER:MODE "):
            self.trigger_mode = command.rsplit(" ", 1)[1]
        elif upper.startswith(":TRIGGER:EDGE:SOURCE CHANNEL"):
            self.trigger_source = int(command.rsplit("CHANnel", 1)[1])
        elif upper.startswith(":TRIGGER:EDGE:LEVEL "):
            self.trigger_level = float(command.rsplit(" ", 1)[1])
        elif upper.startswith(":TRIGGER:EDGE:SLOPE "):
            self.trigger_slope = command.rsplit(" ", 1)[1]
        elif not self._apply_channel_write(command):
            self._handle_unknown("write", command)

    def query(self, command: str) -> str:
        """Record one query and return a deterministic response."""

        self._ensure_open()
        self.history.append(command)
        self._raise_configured_failure(self.query_failures, command)
        if command in self.query_overrides:
            return self.query_overrides[command]
        upper = command.upper()
        if upper == "*IDN?":
            return simulator_idn(self.model)
        if upper == ":SYSTEM:ERROR?":
            if self.system_errors:
                return self.system_errors.pop(0)
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
        return self._handle_unknown("query", command)

    def read_raw(self) -> bytes:
        """Return empty raw bytes; current CLI uses binary queries instead."""

        self._ensure_open()
        return b""

    def query_binary_values(self, command: str, **kwargs: Any) -> Sequence[Any]:
        """Record one binary query and return waveform or PNG bytes."""

        self._ensure_open()
        self.history.append(command)
        self._raise_configured_failure(self.binary_failures, command)
        if command in self.binary_overrides:
            return self.binary_overrides[command]
        if command.upper().startswith(":DISPLAY:DATA?"):
            return tuple(_SIMULATED_PNG)
        if not command.upper().startswith(":WAVEFORM:DATA?"):
            return self._handle_unknown("binary query", command)
        self._validate_waveform_points()
        if kwargs.get("datatype") == "H":
            return tuple(
                self._encode_word_sample(self._waveform_voltage_at_index(index))
                for index in range(self.waveform_points)
            )
        return tuple(
            self._encode_byte_sample(self._waveform_voltage_at_index(index))
            for index in range(self.waveform_points)
        )

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

    def _raise_configured_failure(
        self, failures: dict[str, Exception], command: str
    ) -> None:
        exc = failures.get(command)
        if exc is not None:
            raise exc

    def _handle_unknown(self, operation: str, command: str):
        if self.strict_unknown_commands:
            raise SimulatorBackendError(f"Unsupported simulator {operation}: {command}")
        return "0"

    def _waveform_preamble(self) -> str:
        self._validate_waveform_points()
        x_increment = self._waveform_x_increment()
        x_origin = self._waveform_x_origin()
        y_origin = self._signal_center_v(self.waveform_source)
        if self.waveform_format == "WORD":
            return (
                f"1,0,{self.waveform_points},1,{x_increment:.12E},"
                f"{x_origin:.12E},0,{self._word_y_increment():.12E},"
                f"{y_origin:.12E},32768"
            )
        return (
            f"0,0,{self.waveform_points},1,{x_increment:.12E},"
            f"{x_origin:.12E},0,{self._byte_y_increment():.12E},"
            f"{y_origin:.12E},128"
        )

    def _measurement_value(self, command: str) -> str:
        parsed = self._parse_measurement_command(command)
        if parsed is None:
            return self._handle_unknown("query", command)

        item, channel, reference_channel, args = parsed
        if channel in self.invalid_measurement_channels:
            return _INVALID_MEASUREMENT_SENTINEL
        if (
            reference_channel is not None
            and reference_channel in self.invalid_measurement_channels
        ):
            return _INVALID_MEASUREMENT_SENTINEL

        if item == "time_at_value":
            level = float(args["level"])
            signal = self._signal(channel)
            if level < signal["minimum"] or level > signal["maximum"]:
                return _INVALID_MEASUREMENT_SENTINEL

        value = self._measurement_numeric_value(item, channel, reference_channel, args)
        return f"{value:.6E}"

    def _validate_waveform_points(self) -> None:
        if self.waveform_points not in _SUPPORTED_WAVEFORM_POINTS:
            if self.strict_unknown_commands:
                raise SimulatorBackendError(
                    f"Unsupported simulator waveform point count: {self.waveform_points}"
                )
            self.waveform_points = 1000

    def _waveform_window_s(self) -> float:
        return 10.0 * self.timebase_scale

    def _waveform_x_increment(self) -> float:
        return self._waveform_window_s() / self.waveform_points

    def _waveform_x_origin(self) -> float:
        return self.timebase_position - self._waveform_window_s() / 2.0

    def _waveform_voltage_at_index(self, index: int) -> float:
        time_s = self._waveform_x_origin() + index * self._waveform_x_increment()
        return self._signal_voltage(self.waveform_source, time_s)

    def _byte_y_increment(self) -> float:
        return self.channel_scale.get(self.waveform_source, 1.0) / 50.0

    def _word_y_increment(self) -> float:
        return self.channel_scale.get(self.waveform_source, 1.0) / 10000.0

    def _encode_byte_sample(self, voltage: float) -> int:
        raw = round(
            (voltage - self._signal_center_v(self.waveform_source))
            / self._byte_y_increment()
            + 128
        )
        return max(0, min(255, raw))

    def _encode_word_sample(self, voltage: float) -> int:
        raw = round(
            (voltage - self._signal_center_v(self.waveform_source))
            / self._word_y_increment()
            + 32768
        )
        return max(0, min(65535, raw))

    def _signal(self, channel: int) -> dict[str, float]:
        center = self._signal_center_v(channel)
        vpp = 0.5 * channel
        amplitude = vpp / 2.0
        return {
            "frequency": _SIGNAL_FREQUENCY_HZ,
            "period": 1.0 / _SIGNAL_FREQUENCY_HZ,
            "phase_deg": (channel - 1) * 45.0,
            "center": center,
            "vpp": vpp,
            "amplitude": amplitude,
            "minimum": center - amplitude,
            "maximum": center + amplitude,
        }

    def _signal_center_v(self, channel: int) -> float:
        return self.channel_offset.get(channel, 0.0)

    def _signal_voltage(self, channel: int, time_s: float) -> float:
        signal = self._signal(channel)
        angle = (
            2.0 * math.pi * signal["frequency"] * time_s
            + math.radians(signal["phase_deg"])
        )
        return signal["center"] + signal["amplitude"] * math.sin(angle)

    def _measurement_numeric_value(
        self,
        item: str,
        channel: int,
        reference_channel: int | None,
        args: dict[str, float],
    ) -> float:
        signal = self._signal(channel)
        frequency = signal["frequency"]
        period = signal["period"]
        amplitude = signal["amplitude"]
        window_s = self._waveform_window_s()
        cycles = frequency * window_s

        if item in {"vpp", "amplitude"}:
            return signal["vpp"]
        if item == "frequency":
            return frequency
        if item == "period":
            return period
        if item == "vavg":
            return signal["center"]
        if item == "vrms":
            return math.hypot(signal["center"], amplitude / math.sqrt(2.0))
        if item == "ac_rms":
            return amplitude / math.sqrt(2.0)
        if item in {"minimum", "base"}:
            return signal["minimum"]
        if item in {"maximum", "top"}:
            return signal["maximum"]
        if item == "overshoot" or item == "preshoot":
            return 0.0
        if item == "x_at_max":
            return self._edge_time(channel, 0.25, 1)
        if item == "x_at_min":
            return self._edge_time(channel, 0.75, 1)
        if item in {"rise_time", "fall_time"}:
            return 0.8 / (2.0 * math.pi * frequency)
        if item in {"positive_width", "negative_width"}:
            return period / 2.0
        if item in {"duty_cycle", "negative_duty_cycle"}:
            return 50.0
        if item == "area":
            return signal["center"] * window_s
        if item in {"positive_edges", "negative_edges"}:
            return float(max(1, int(round(cycles))))
        if item in {"positive_pulses", "negative_pulses"}:
            return float(max(1, int(math.floor(cycles))))
        if item == "y_at_x":
            return self._signal_voltage(channel, float(args["time_s"]))
        if item == "time_at_edge":
            occurrence = int(args["occurrence"])
            phase = 0.0 if occurrence > 0 else 0.5
            return self._edge_time(channel, phase, abs(occurrence))
        if item == "time_at_value":
            return self._time_at_value(
                channel,
                level=float(args["level"]),
                occurrence=int(args["occurrence"]),
            )
        if item == "phase" and reference_channel is not None:
            return self._phase_difference_deg(channel, reference_channel)
        if item == "delay" and reference_channel is not None:
            return (
                self._phase_difference_deg(channel, reference_channel)
                / 360.0
                / frequency
            )
        raise SimulatorBackendError(f"Unsupported simulator measurement query item: {item}")

    def _phase_difference_deg(self, channel: int, reference_channel: int) -> float:
        return (
            self._signal(reference_channel)["phase_deg"]
            - self._signal(channel)["phase_deg"]
        )

    def _edge_time(self, channel: int, phase_cycles: float, occurrence: int) -> float:
        signal = self._signal(channel)
        channel_phase_cycles = signal["phase_deg"] / 360.0
        return (
            phase_cycles + occurrence - 1 - channel_phase_cycles
        ) / signal["frequency"]

    def _time_at_value(self, channel: int, *, level: float, occurrence: int) -> float:
        signal = self._signal(channel)
        normalized = (level - signal["center"]) / signal["amplitude"]
        normalized = max(-1.0, min(1.0, normalized))
        angle = math.asin(normalized)
        if occurrence < 0:
            angle = math.pi - angle
        phase_cycles = (angle / (2.0 * math.pi)) % 1.0
        return self._edge_time(channel, phase_cycles, abs(occurrence))

    def _parse_measurement_command(
        self, command: str
    ) -> tuple[str, int, int | None, dict[str, float]] | None:
        pair_match = re.fullmatch(
            r":MEASure:(PHASe|DELay)\?\s+(?:AUTO,)?CHANnel(\d+),CHANnel(\d+)",
            command,
            flags=re.IGNORECASE,
        )
        if pair_match:
            raw_item, channel, reference = pair_match.groups()
            item = "phase" if raw_item.upper() == "PHASE" else "delay"
            return item, int(channel), int(reference), {}

        y_at_x_match = re.fullmatch(
            r":MEASure:VTIMe\?\s+([^,]+),CHANnel(\d+)",
            command,
            flags=re.IGNORECASE,
        )
        if y_at_x_match:
            time_s, channel = y_at_x_match.groups()
            return "y_at_x", int(channel), None, {"time_s": float(time_s)}

        edge_match = re.fullmatch(
            r":MEASure:TEDGe\?\s+([+-]?\d+),CHANnel(\d+)",
            command,
            flags=re.IGNORECASE,
        )
        if edge_match:
            occurrence, channel = edge_match.groups()
            return "time_at_edge", int(channel), None, {"occurrence": int(occurrence)}

        value_match = re.fullmatch(
            r":MEASure:TVALue\?\s+([^,]+),([+-]?\d+),CHANnel(\d+)",
            command,
            flags=re.IGNORECASE,
        )
        if value_match:
            level, occurrence, channel = value_match.groups()
            return (
                "time_at_value",
                int(channel),
                None,
                {"level": float(level), "occurrence": int(occurrence)},
            )

        single_match = re.fullmatch(
            r":MEASure:([A-Za-z]+)\?\s+(?:DISPlay,(?:(AC|DC),)?)?CHANnel(\d+)",
            command,
            flags=re.IGNORECASE,
        )
        if not single_match:
            return None

        raw_item, rms_mode, channel = single_match.groups()
        item = self._single_measurement_item(raw_item, rms_mode)
        if item is None:
            return None
        return item, int(channel), None, {}

    def _single_measurement_item(self, raw_item: str, rms_mode: str | None) -> str | None:
        normalized = raw_item.upper()
        items = {
            "VPP": "vpp",
            "FREQUENCY": "frequency",
            "PERIOD": "period",
            "VAVERAGE": "vavg",
            "VMIN": "minimum",
            "VMAX": "maximum",
            "XMAX": "x_at_max",
            "XMIN": "x_at_min",
            "RISETIME": "rise_time",
            "FALLTIME": "fall_time",
            "VAMPLITUDE": "amplitude",
            "VTOP": "top",
            "VBASE": "base",
            "OVERSHOOT": "overshoot",
            "PRESHOOT": "preshoot",
            "PWIDTH": "positive_width",
            "NWIDTH": "negative_width",
            "DUTYCYCLE": "duty_cycle",
            "NDUTY": "negative_duty_cycle",
            "AREA": "area",
            "PEDGES": "positive_edges",
            "NEDGES": "negative_edges",
            "PPULSES": "positive_pulses",
            "NPULSES": "negative_pulses",
        }
        if normalized == "VRMS":
            return "ac_rms" if rms_mode and rms_mode.upper() == "AC" else "vrms"
        return items.get(normalized)

    def _apply_channel_write(self, command: str) -> bool:
        channel = _extract_channel(command)
        if channel is None:
            return False
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
        else:
            return False
        return True

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
