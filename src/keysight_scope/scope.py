"""High-level oscilloscope object for Phase 1 functionality."""

from __future__ import annotations

from .capabilities import ScopeCapabilities, capabilities_for_model
from .errors import UnsupportedModelError
from .idn import IDN, parse_idn
from .scpi import SCPIBackend, SCPIClient
from .visa_backend import VisaBackend


class KeysightScope:
    """High-level oscilloscope session wrapper."""

    def __init__(self, backend: SCPIBackend) -> None:
        self.backend = backend
        self.scpi = SCPIClient(backend)
        self.idn: IDN | None = None
        self.capabilities: ScopeCapabilities | None = None

    @classmethod
    def open(cls, resource_name: str, visa_library: str | None = None) -> "KeysightScope":
        """Open a PyVISA-backed oscilloscope session."""

        return cls(VisaBackend(resource_name, visa_library=visa_library))

    def query_idn(self) -> IDN:
        """Query, parse, and store `*IDN?` information."""

        parsed = parse_idn(self.scpi.query("*IDN?"))
        self.idn = parsed
        try:
            self.capabilities = capabilities_for_model(parsed.model)
        except UnsupportedModelError:
            self.capabilities = None
        return parsed

    def close(self) -> None:
        """Close the underlying backend."""

        self.backend.close()

    def __enter__(self) -> "KeysightScope":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()
