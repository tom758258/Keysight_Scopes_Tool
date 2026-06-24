"""Instrument status and error parsing helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from .errors import SystemErrorParseError


@dataclass(frozen=True)
class SystemErrorEntry:
    """One entry read from the oscilloscope system error queue."""

    code: int
    message: str
    raw: str

    @property
    def is_error(self) -> bool:
        """Return whether this entry represents an instrument error."""

        return self.code != 0

    def format(self) -> str:
        """Return a stable human-readable representation."""

        return f'{self.code:+d}, "{self.message}"'


def parse_system_error(response: str) -> SystemErrorEntry:
    """Parse one `:SYSTem:ERRor?` response."""

    raw = response.strip()
    try:
        row = next(csv.reader([raw], skipinitialspace=True))
    except csv.Error as exc:
        raise SystemErrorParseError(f"Invalid system error response: {response!r}") from exc

    if len(row) != 2:
        raise SystemErrorParseError(f"Invalid system error response: {response!r}")

    code_text, message = row
    try:
        code = int(code_text)
    except ValueError as exc:
        raise SystemErrorParseError(f"Invalid system error code: {code_text!r}") from exc

    return SystemErrorEntry(code=code, message=message, raw=raw)
