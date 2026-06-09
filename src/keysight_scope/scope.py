"""High-level oscilloscope object."""

from __future__ import annotations

from .capabilities import ScopeCapabilities, capabilities_for_model
from .channel import ChannelController
from .errors import ParameterValidationError, UnsupportedModelError
from .idn import IDN, parse_idn
from .scpi import SCPIBackend, SCPIClient
from .status import SystemErrorEntry, parse_system_error
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

    def query_system_error(self) -> SystemErrorEntry:
        """Read one entry from the system error queue.

        This is a destructive queue read on the instrument: the returned entry is
        removed from the oscilloscope's error queue.
        """

        return parse_system_error(self.scpi.query(":SYSTem:ERRor?"))

    def drain_system_errors(self, max_reads: int = 30) -> tuple[SystemErrorEntry, ...]:
        """Read system errors until the queue reports no error or `max_reads` is hit."""

        if max_reads < 1:
            raise ValueError("max_reads must be at least 1.")

        entries = []
        for _ in range(max_reads):
            entry = self.query_system_error()
            entries.append(entry)
            if not entry.is_error:
                break
        return tuple(entries)

    def run(self) -> None:
        """Start repetitive acquisitions."""

        self.scpi.write(":RUN")

    def stop(self) -> None:
        """Stop acquisitions."""

        self.scpi.write(":STOP")

    def single(self) -> None:
        """Start one single acquisition without waiting for completion."""

        self.scpi.write(":SINGle")

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        """Turn one analog channel display on or off."""

        self._channel_controller().set_display(channel, enabled)

    def query_channel_display(self, channel: int) -> bool:
        """Query whether one analog channel display is enabled."""

        return self._channel_controller().query_display(channel)

    def close(self) -> None:
        """Close the underlying backend."""

        self.backend.close()

    def _channel_controller(self) -> ChannelController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Channel operations require known capabilities; call query_idn() first."
            )
        return ChannelController(self.scpi, self.capabilities)

    def __enter__(self) -> "KeysightScope":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()
