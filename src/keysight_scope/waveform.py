"""Single-channel waveform capture helpers."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Sequence

from .capabilities import ScopeCapabilities
from .channel import validate_analog_channel
from .errors import ParameterValidationError, WaveformResponseError
from .idn import IDN
from .scpi import SCPIClient

SUPPORTED_BYTE_POINTS = (1000,)


@dataclass(frozen=True)
class WaveformPreamble:
    """Parsed `:WAVeform:PREamble?` response."""

    raw: str
    format_code: int
    type_code: int
    points: int
    count: int
    x_increment: float
    x_origin: float
    x_reference: int
    y_increment: float
    y_origin: float
    y_reference: int


@dataclass(frozen=True)
class WaveformCapture:
    """Converted single-channel waveform data."""

    channel: int
    requested_points: int
    format_name: str
    preamble: WaveformPreamble
    raw_samples: tuple[int, ...]
    time_s: tuple[float, ...]
    voltage_v: tuple[float, ...]


class WaveformController:
    """Controls for single-channel waveform capture."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def capture_byte(self, channel: int, points: int = 1000) -> WaveformCapture:
        """Capture one analog channel using BYTE waveform format."""

        channel = validate_analog_channel(channel, self.capabilities)
        points = validate_waveform_points(points, self.capabilities)
        self.scpi.write(waveform_source_command(channel))
        self.scpi.write(waveform_format_byte_command())
        self.scpi.write(waveform_points_command(points))
        preamble = parse_waveform_preamble(self.scpi.query(waveform_preamble_query()))
        if preamble.format_code != 0:
            raise WaveformResponseError(
                f"Expected BYTE waveform preamble format 0, got {preamble.format_code}."
            )
        raw_samples = tuple(int(value) for value in self.scpi.query_binary_values(waveform_data_query(), datatype="B"))
        if not raw_samples:
            raise WaveformResponseError("Waveform data query returned no samples.")
        return convert_byte_waveform(channel, points, preamble, raw_samples)


def validate_waveform_points(points: int, capabilities: ScopeCapabilities) -> int:
    """Validate first-slice waveform point count."""

    try:
        value = int(points)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("waveform points must be an integer.") from exc
    if value not in SUPPORTED_BYTE_POINTS:
        supported = ", ".join(str(point_count) for point_count in SUPPORTED_BYTE_POINTS)
        raise ParameterValidationError(
            f"first waveform capture slice supports only these point counts: {supported}."
        )
    if value > capabilities.safe_max_waveform_points:
        raise ParameterValidationError(
            f"waveform points {value} exceed safe maximum {capabilities.safe_max_waveform_points}."
        )
    return value


def waveform_source_command(channel: int) -> str:
    """Build the SCPI command for waveform source."""

    return f":WAVeform:SOURce CHANnel{channel}"


def waveform_format_byte_command() -> str:
    """Build the SCPI command for BYTE waveform format."""

    return ":WAVeform:FORMat BYTE"


def waveform_points_command(points: int) -> str:
    """Build the SCPI command for waveform point count."""

    return f":WAVeform:POINts {points}"


def waveform_preamble_query() -> str:
    """Build the SCPI query for waveform preamble."""

    return ":WAVeform:PREamble?"


def waveform_data_query() -> str:
    """Build the SCPI query for waveform data."""

    return ":WAVeform:DATA?"


def parse_waveform_preamble(raw: str) -> WaveformPreamble:
    """Parse a Keysight waveform preamble."""

    parts = [part.strip() for part in raw.strip().split(",")]
    if len(parts) != 10:
        raise WaveformResponseError(f"Expected 10 waveform preamble fields, got {len(parts)}: {raw!r}")
    try:
        format_code = int(parts[0])
        type_code = int(parts[1])
        points = int(parts[2])
        count = int(parts[3])
        x_increment = float(parts[4])
        x_origin = float(parts[5])
        x_reference = int(parts[6])
        y_increment = float(parts[7])
        y_origin = float(parts[8])
        y_reference = int(parts[9])
    except ValueError as exc:
        raise WaveformResponseError(f"Could not parse waveform preamble: {raw!r}") from exc
    numeric_values = (x_increment, x_origin, y_increment, y_origin)
    if not all(math.isfinite(value) for value in numeric_values):
        raise WaveformResponseError(f"Could not parse waveform preamble: {raw!r}")
    if points < 1:
        raise WaveformResponseError(f"Waveform preamble points must be positive: {raw!r}")
    return WaveformPreamble(
        raw=raw.strip(),
        format_code=format_code,
        type_code=type_code,
        points=points,
        count=count,
        x_increment=x_increment,
        x_origin=x_origin,
        x_reference=x_reference,
        y_increment=y_increment,
        y_origin=y_origin,
        y_reference=y_reference,
    )


def convert_byte_waveform(
    channel: int,
    requested_points: int,
    preamble: WaveformPreamble,
    raw_samples: Sequence[int],
) -> WaveformCapture:
    """Convert BYTE waveform samples to time and voltage tuples."""

    samples = tuple(_validate_byte_sample(value) for value in raw_samples)
    time_s = tuple(
        (index - preamble.x_reference) * preamble.x_increment + preamble.x_origin
        for index in range(len(samples))
    )
    voltage_v = tuple(
        (sample - preamble.y_reference) * preamble.y_increment + preamble.y_origin
        for sample in samples
    )
    return WaveformCapture(
        channel=channel,
        requested_points=requested_points,
        format_name="BYTE",
        preamble=preamble,
        raw_samples=samples,
        time_s=time_s,
        voltage_v=voltage_v,
    )


def write_waveform_csv(capture: WaveformCapture, path: str | Path) -> Path:
    """Write converted waveform data to CSV."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time_s", f"ch{capture.channel}_v"))
        writer.writerows(zip(capture.time_s, capture.voltage_v))
    return output_path


def write_waveform_metadata(
    capture: WaveformCapture,
    path: str | Path,
    *,
    idn: IDN,
    resource: str,
) -> Path:
    """Write capture metadata to JSON."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "idn": idn.raw,
        "vendor": idn.vendor,
        "model": idn.model,
        "series": idn.series,
        "serial": idn.serial,
        "firmware": idn.firmware,
        "resource": resource,
        "channel": capture.channel,
        "requested_points": capture.requested_points,
        "actual_points": len(capture.raw_samples),
        "format": capture.format_name,
        "preamble": asdict(capture.preamble),
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output_path


def _validate_byte_sample(value: int) -> int:
    sample = int(value)
    if sample < 0 or sample > 255:
        raise WaveformResponseError(f"BYTE waveform sample out of range: {value!r}")
    return sample
