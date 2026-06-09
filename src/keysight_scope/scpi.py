"""Small SCPI client wrapper with command logging."""

from __future__ import annotations

import logging
from typing import Any, Protocol, Sequence

from .log import get_logger


class SCPIBackend(Protocol):
    """Backend protocol used by `SCPIClient`."""

    def write(self, command: str) -> None:
        """Send a command without reading a response."""

    def query(self, command: str) -> str:
        """Send a command and return the response string."""

    def read_raw(self) -> bytes:
        """Read raw bytes from the backend."""

    def query_binary_values(self, command: str, **kwargs: Any) -> Sequence[Any]:
        """Send a binary query and return decoded values."""

    def close(self) -> None:
        """Close the backend session."""


class SCPIClient:
    """Narrow SCPI API used by higher-level modules."""

    def __init__(self, backend: SCPIBackend, logger: logging.Logger | None = None) -> None:
        self.backend = backend
        self.logger = logger or get_logger("scpi")

    def write(self, command: str) -> None:
        """Write one SCPI command and log it."""

        command = _normalize_command(command)
        self.logger.debug("SCPI >> %s", command)
        self.backend.write(command)

    def query(self, command: str) -> str:
        """Query one SCPI command and log the command and response."""

        command = _normalize_command(command)
        self.logger.debug("SCPI >> %s", command)
        response = self.backend.query(command).strip()
        self.logger.debug("SCPI << %s", response)
        return response

    def query_float(self, command: str) -> float:
        """Query a SCPI command and parse the response as a float."""

        return float(self.query(command))

    def read_raw(self) -> bytes:
        """Read raw bytes from the backend."""

        payload = self.backend.read_raw()
        self.logger.debug("SCPI << %d raw bytes", len(payload))
        return payload

    def query_binary_values(self, command: str, **kwargs: Any) -> Sequence[Any]:
        """Query binary values through the backend."""

        command = _normalize_command(command)
        self.logger.debug("SCPI >> %s", command)
        values = self.backend.query_binary_values(command, **kwargs)
        self.logger.debug("SCPI << %d binary values", len(values))
        return values


def _normalize_command(command: str) -> str:
    normalized = command.strip()
    if not normalized:
        raise ValueError("SCPI command cannot be empty.")
    return normalized
