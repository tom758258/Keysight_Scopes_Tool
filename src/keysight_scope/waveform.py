"""Waveform capture helpers."""

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

SUPPORTED_WAVEFORM_POINTS = (1000, 5000, 10000)
SUPPORTED_BYTE_POINTS = SUPPORTED_WAVEFORM_POINTS
SUPPORTED_WORD_POINTS = SUPPORTED_WAVEFORM_POINTS
WORD_BYTE_ORDER = "MSBFirst"
WORD_UNSIGNED = True


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
    byte_order: str | None = None
    unsigned: bool | None = None


@dataclass(frozen=True)
class MultiChannelWaveformCapture:
    """Converted waveform data for multiple analog channels."""

    captures: tuple[WaveformCapture, ...]

    def __post_init__(self) -> None:
        captures = tuple(self.captures)
        if not captures:
            raise WaveformResponseError(
                "Multi-channel waveform capture requires at least one channel."
            )

        channels = tuple(capture.channel for capture in captures)
        if len(set(channels)) != len(channels):
            raise WaveformResponseError(
                "Multi-channel waveform capture contains duplicate channels."
            )

        formats = {capture.format_name for capture in captures}
        if len(formats) != 1:
            raise WaveformResponseError(
                "Multi-channel waveform capture contains mixed formats."
            )

        requested_points = {capture.requested_points for capture in captures}
        if len(requested_points) != 1:
            raise WaveformResponseError(
                "Multi-channel waveform capture contains mixed point counts."
            )

        object.__setattr__(self, "captures", captures)

    @property
    def channels(self) -> tuple[int, ...]:
        """Ordered analog channel numbers."""

        return tuple(capture.channel for capture in self.captures)

    @property
    def requested_points(self) -> int:
        """Requested point count shared by all channel captures."""

        return self.captures[0].requested_points

    @property
    def format_name(self) -> str:
        """Waveform transfer format shared by all channel captures."""

        return self.captures[0].format_name


class WaveformController:
    """Controls for waveform capture."""

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

    def capture_word(self, channel: int, points: int = 1000) -> WaveformCapture:
        """Capture one analog channel using WORD waveform format."""

        channel = validate_analog_channel(channel, self.capabilities)
        points = validate_waveform_points(points, self.capabilities)
        self.scpi.write(waveform_source_command(channel))
        self.scpi.write(waveform_format_word_command())
        self.scpi.write(waveform_byte_order_command(WORD_BYTE_ORDER))
        self.scpi.write(waveform_unsigned_command(WORD_UNSIGNED))
        self.scpi.write(waveform_points_command(points))
        preamble = parse_waveform_preamble(self.scpi.query(waveform_preamble_query()))
        if preamble.format_code != 1:
            raise WaveformResponseError(
                f"Expected WORD waveform preamble format 1, got {preamble.format_code}."
            )
        raw_samples = tuple(
            int(value)
            for value in self.scpi.query_binary_values(
                waveform_data_query(),
                datatype="H",
                is_big_endian=True,
            )
        )
        if not raw_samples:
            raise WaveformResponseError("Waveform data query returned no samples.")
        return convert_word_waveform(channel, points, preamble, raw_samples)

    def capture_channels_byte(
        self, channels: Sequence[int], points: int = 1000
    ) -> MultiChannelWaveformCapture:
        """Capture multiple analog channels using BYTE waveform format."""

        channels = validate_waveform_channels(channels, self.capabilities)
        points = validate_waveform_points(points, self.capabilities)
        captures = tuple(self.capture_byte(channel, points=points) for channel in channels)
        return MultiChannelWaveformCapture(captures)

    def capture_channels_word(
        self, channels: Sequence[int], points: int = 1000
    ) -> MultiChannelWaveformCapture:
        """Capture multiple analog channels using WORD waveform format."""

        channels = validate_waveform_channels(channels, self.capabilities)
        points = validate_waveform_points(points, self.capabilities)
        captures = tuple(self.capture_word(channel, points=points) for channel in channels)
        return MultiChannelWaveformCapture(captures)


def validate_waveform_channels(
    channels: Sequence[int], capabilities: ScopeCapabilities
) -> tuple[int, ...]:
    """Validate ordered waveform channel selection and reject duplicates."""

    if isinstance(channels, (str, bytes)):
        raise ParameterValidationError(
            "waveform channels must be a sequence of integers."
        )
    try:
        normalized = tuple(
            validate_analog_channel(channel, capabilities) for channel in channels
        )
    except TypeError as exc:
        raise ParameterValidationError(
            "waveform channels must be a sequence of integers."
        ) from exc
    if not normalized:
        raise ParameterValidationError("waveform capture requires at least one channel.")
    if len(set(normalized)) != len(normalized):
        seen: set[int] = set()
        duplicates = []
        for channel in normalized:
            if channel in seen and channel not in duplicates:
                duplicates.append(channel)
            seen.add(channel)
        duplicate_text = ", ".join(f"CH{channel}" for channel in duplicates)
        raise ParameterValidationError(
            f"duplicate waveform channels are not allowed: {duplicate_text}."
        )
    return normalized


def validate_waveform_points(points: int, capabilities: ScopeCapabilities) -> int:
    """Validate supported waveform point count."""

    try:
        value = int(points)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("waveform points must be an integer.") from exc
    if value not in SUPPORTED_WAVEFORM_POINTS:
        supported = ", ".join(str(point_count) for point_count in SUPPORTED_WAVEFORM_POINTS)
        raise ParameterValidationError(
            f"waveform capture supports only these point counts: {supported}."
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


def waveform_format_word_command() -> str:
    """Build the SCPI command for WORD waveform format."""

    return ":WAVeform:FORMat WORD"


def waveform_byte_order_command(byte_order: str = WORD_BYTE_ORDER) -> str:
    """Build the SCPI command for WORD byte order."""

    return f":WAVeform:BYTeorder {byte_order}"


def waveform_unsigned_command(unsigned: bool = WORD_UNSIGNED) -> str:
    """Build the SCPI command for waveform unsigned mode."""

    return f":WAVeform:UNSigned {'ON' if unsigned else 'OFF'}"


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


def convert_word_waveform(
    channel: int,
    requested_points: int,
    preamble: WaveformPreamble,
    raw_samples: Sequence[int],
) -> WaveformCapture:
    """Convert unsigned WORD waveform samples to time and voltage tuples."""

    samples = tuple(_validate_word_sample(value) for value in raw_samples)
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
        format_name="WORD",
        preamble=preamble,
        raw_samples=samples,
        time_s=time_s,
        voltage_v=voltage_v,
        byte_order=WORD_BYTE_ORDER,
        unsigned=WORD_UNSIGNED,
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
    if capture.byte_order is not None:
        metadata["byte_order"] = capture.byte_order
    if capture.unsigned is not None:
        metadata["unsigned"] = capture.unsigned
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output_path


def write_waveforms_csv(capture: MultiChannelWaveformCapture, path: str | Path) -> Path:
    """Write aligned multi-channel waveform data to CSV."""

    _validate_aligned_waveforms(capture)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reference = capture.captures[0]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ("time_s", *(f"ch{item.channel}_v" for item in capture.captures))
        )
        for index, time_value in enumerate(reference.time_s):
            writer.writerow(
                (time_value, *(item.voltage_v[index] for item in capture.captures))
            )
    return output_path


def write_waveforms_metadata(
    capture: MultiChannelWaveformCapture,
    path: str | Path,
    *,
    idn: IDN,
    resource: str,
) -> Path:
    """Write multi-channel capture metadata to JSON."""

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
        "requested_points": capture.requested_points,
        "format": capture.format_name,
        "channels": [_waveform_channel_metadata(item) for item in capture.captures],
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output_path


def _waveform_channel_metadata(capture: WaveformCapture) -> dict[str, object]:
    metadata: dict[str, object] = {
        "channel": capture.channel,
        "actual_points": len(capture.raw_samples),
        "preamble": asdict(capture.preamble),
    }
    if capture.byte_order is not None:
        metadata["byte_order"] = capture.byte_order
    if capture.unsigned is not None:
        metadata["unsigned"] = capture.unsigned
    return metadata


def _validate_aligned_waveforms(capture: MultiChannelWaveformCapture) -> None:
    reference = capture.captures[0]
    reference_count = _validate_capture_sample_lengths(reference)
    for item in capture.captures[1:]:
        item_count = _validate_capture_sample_lengths(item)
        if item_count != reference_count:
            raise WaveformResponseError(
                "Cannot write multi-channel waveform CSV: "
                f"CH{item.channel} has {item_count} samples, "
                f"CH{reference.channel} has {reference_count}."
            )
        if item.time_s != reference.time_s:
            raise WaveformResponseError(
                "Cannot write multi-channel waveform CSV: "
                f"CH{item.channel} time axis does not match CH{reference.channel}."
            )


def _validate_capture_sample_lengths(capture: WaveformCapture) -> int:
    sample_count = len(capture.raw_samples)
    if len(capture.time_s) != sample_count:
        raise WaveformResponseError(
            f"CH{capture.channel} has {sample_count} samples "
            f"but {len(capture.time_s)} time values."
        )
    if len(capture.voltage_v) != sample_count:
        raise WaveformResponseError(
            f"CH{capture.channel} has {sample_count} samples "
            f"but {len(capture.voltage_v)} voltages."
        )
    return sample_count


def _validate_byte_sample(value: int) -> int:
    sample = int(value)
    if sample < 0 or sample > 255:
        raise WaveformResponseError(f"BYTE waveform sample out of range: {value!r}")
    return sample


def _validate_word_sample(value: int) -> int:
    sample = int(value)
    if sample < 0 or sample > 65535:
        raise WaveformResponseError(f"WORD waveform sample out of range: {value!r}")
    return sample
