"""Hardware-free backend for tests and examples."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, MutableMapping, Sequence

from .errors import BackendClosedError, KeysightScopeError

DEFAULT_IDN = "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY00000000,02.50"


class FakeBackendError(KeysightScopeError):
    """Raised when a fake response has not been configured."""


@dataclass
class FakeBackend:
    """A deterministic SCPI backend that records command order."""

    responses: MutableMapping[str, str] = field(
        default_factory=lambda: {
            "*IDN?": DEFAULT_IDN,
            ":SYSTem:ERRor?": '+0,"No error"',
        }
    )
    raw_response: bytes = b""
    binary_responses: MutableMapping[str, Sequence[Any]] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    resource_name: str = "FAKE::SCOPE"
    backend: str = "fake"
    timeout: int | None = None
    closed: bool = False

    def write(self, command: str) -> None:
        """Record a SCPI write."""

        self._ensure_open()
        self.history.append(command)

    def query(self, command: str) -> str:
        """Record a SCPI query and return a configured response."""

        self._ensure_open()
        self.history.append(command)
        try:
            return self.responses[command]
        except KeyError as exc:
            raise FakeBackendError(f"No fake response configured for query: {command}") from exc

    def read_raw(self) -> bytes:
        """Return configured raw bytes."""

        self._ensure_open()
        return self.raw_response

    def query_binary_values(self, command: str, **kwargs: Any) -> Sequence[Any]:
        """Record a binary query and return configured values."""

        del kwargs
        self._ensure_open()
        self.history.append(command)
        try:
            return self.binary_responses[command]
        except KeyError as exc:
            raise FakeBackendError(
                f"No fake binary response configured for query: {command}"
            ) from exc

    def close(self) -> None:
        """Mark the fake backend as closed."""

        self.closed = True

    def _ensure_open(self) -> None:
        if self.closed:
            raise BackendClosedError("Fake backend is closed.")
