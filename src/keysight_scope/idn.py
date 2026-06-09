"""Parsing and model detection for `*IDN?` responses."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import IDNParseError

_MODEL_RE = re.compile(r"^(?:DSO|MSO)X(?P<series>[234])\d{3}[A-Z]?$", re.IGNORECASE)


@dataclass(frozen=True)
class IDN:
    """Parsed fields from an oscilloscope `*IDN?` response."""

    vendor: str
    model: str
    serial: str
    firmware: str
    raw: str

    @property
    def series(self) -> str | None:
        """Return the detected InfiniiVision series, if recognized."""

        return detect_series(self.model)


def parse_idn(response: str) -> IDN:
    """Parse a standard four-field `*IDN?` response."""

    raw = response.strip()
    parts = [part.strip() for part in raw.split(",", 3)]
    if len(parts) != 4 or not all(parts):
        raise IDNParseError(
            "Expected `*IDN?` response with vendor, model, serial, and firmware fields."
        )

    vendor, model, serial, firmware = parts
    return IDN(
        vendor=vendor,
        model=model.upper(),
        serial=serial,
        firmware=firmware,
        raw=raw,
    )


def detect_series(model: str) -> str | None:
    """Detect 2000X, 3000X, or 4000X series from a Keysight model string."""

    match = _MODEL_RE.match(model.strip().upper())
    if match is None:
        return None
    return f"{match.group('series')}000X"
