"""Acquisition configuration controls."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .errors import AcquisitionResponseError, ParameterValidationError
from .scpi import SCPIClient


_TYPE_COMMANDS = {
    "normal": "NORMal",
    "norm": "NORMal",
    "average": "AVERage",
    "aver": "AVERage",
    "avg": "AVERage",
    "high_resolution": "HRESolution",
    "high-resolution": "HRESolution",
    "hresolution": "HRESolution",
    "hres": "HRESolution",
    "peak": "PEAK",
    "peak_detect": "PEAK",
    "peak-detect": "PEAK",
}

_TYPE_READBACKS = {
    "NORM": "normal",
    "NORMAL": "normal",
    "AVER": "average",
    "AVERAGE": "average",
    "HRES": "high_resolution",
    "HRESOLUTION": "high_resolution",
    "PEAK": "peak",
}


@dataclass(frozen=True)
class AcquisitionConfig:
    """Readback state for acquisition settings."""

    type: str
    count: int


class AcquisitionController:
    """Controls for oscilloscope acquisition settings."""

    def __init__(self, scpi: SCPIClient) -> None:
        self.scpi = scpi

    def set_type(self, acquisition_type: str) -> None:
        """Set the acquisition type."""

        normalized = normalize_acquisition_type(acquisition_type)
        self.scpi.write(acquisition_type_command(normalized))

    def query_type(self) -> str:
        """Query the current acquisition type."""

        raw = self.scpi.query(acquisition_type_query())
        return parse_acquisition_type(raw)

    def set_count(self, count: int) -> None:
        """Set the average count for average acquisition mode."""

        validated = validate_acquisition_count(count)
        self.scpi.write(acquisition_count_command(validated))

    def query_count(self) -> int:
        """Query the current average count."""

        raw = self.scpi.query(acquisition_count_query())
        return parse_acquisition_count(raw)

    def query_config(self) -> AcquisitionConfig:
        """Query both acquisition type and count."""

        acq_type = self.query_type()
        count = self.query_count()
        return AcquisitionConfig(type=acq_type, count=count)


def normalize_acquisition_type(value: str) -> str:
    """Normalize a user-facing acquisition type into a SCPI argument."""

    normalized = value.strip().lower()
    try:
        return _TYPE_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "acquisition type must be one of: normal, average, high_resolution, peak."
        ) from exc


def parse_acquisition_type(raw: str) -> str:
    """Parse an acquisition type readback."""

    normalized = raw.strip().upper()
    try:
        return _TYPE_READBACKS[normalized]
    except KeyError as exc:
        raise AcquisitionResponseError(f"Could not parse acquisition type response: {raw!r}") from exc


def validate_acquisition_count(count: int) -> int:
    """Validate an average count value before sending it to the instrument."""

    if isinstance(count, bool):
        raise ParameterValidationError("acquisition count must be an integer.")
    if isinstance(count, float):
        if not math.isfinite(count):
            raise ParameterValidationError("acquisition count must be a finite number.")
        raise ParameterValidationError("acquisition count must be an integer.")
    if not isinstance(count, int):
        raise ParameterValidationError("acquisition count must be an integer.")
    if count < 2 or count > 65536:
        raise ParameterValidationError("acquisition count must be between 2 and 65536.")
    return count


def parse_acquisition_count(raw: str) -> int:
    """Parse an acquisition count readback."""

    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise AcquisitionResponseError(f"Could not parse acquisition count response: {raw!r}") from exc
    if not math.isfinite(value):
        raise AcquisitionResponseError(f"Could not parse acquisition count response: {raw!r}")
    return value


def acquisition_type_command(acquisition_type: str) -> str:
    """Build the SCPI command for acquisition type."""

    return f":ACQuire:TYPE {acquisition_type}"


def acquisition_type_query() -> str:
    """Build the SCPI query for acquisition type."""

    return ":ACQuire:TYPE?"


def acquisition_count_command(count: int) -> str:
    """Build the SCPI command for acquisition count."""

    return f":ACQuire:COUNt {count}"


def sample_rate_query() -> str:
    """Return the SCPI query for the current analog acquisition sample rate."""

    return ":ACQuire:SRATe?"


def parse_sample_rate(response: str) -> float:
    """Parse an NR3 sample-rate response in Hz."""

    raw = response.strip()
    if not raw:
        raise AcquisitionResponseError(
            f"Could not parse sample rate response: {response!r}"
        )
    try:
        value = float(raw)
    except ValueError as exc:
        raise AcquisitionResponseError(
            f"Could not parse sample rate response: {response!r}"
        ) from exc
    if not math.isfinite(value):
        raise AcquisitionResponseError(
            f"Could not parse sample rate response: {response!r}"
        )
    if value <= 0:
        raise AcquisitionResponseError(
            f"Could not parse sample rate response: {response!r}"
        )
    return value


def acquisition_count_query() -> str:
    """Build the SCPI query for acquisition count."""

    return ":ACQuire:COUNt?"

def memory_depth_query() -> str:
    """Return the SCPI query for the current analog acquisition memory depth."""

    return ":ACQuire:POINts:ANALog?"


def parse_memory_depth(response: str) -> int:
    """Parse an analog acquisition memory-depth response in points."""

    raw = response.strip()
    if not raw:
        raise AcquisitionResponseError(
            f"Could not parse memory depth response: {response!r}"
        )
    try:
        value = float(raw)
    except ValueError as exc:
        raise AcquisitionResponseError(
            f"Could not parse memory depth response: {response!r}"
        ) from exc
    if not math.isfinite(value):
        raise AcquisitionResponseError(
            f"Could not parse memory depth response: {response!r}"
        )
    if value <= 0:
        raise AcquisitionResponseError(
            f"Could not parse memory depth response: {response!r}"
        )
    if not value.is_integer():
        raise AcquisitionResponseError(
            f"Could not parse memory depth response: {response!r}"
        )
    return int(value)
