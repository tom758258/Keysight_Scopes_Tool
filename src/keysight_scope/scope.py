"""High-level oscilloscope object."""

from __future__ import annotations

from .capabilities import ScopeCapabilities, capabilities_for_model
from .channel import ChannelController
from .errors import ParameterValidationError, UnsupportedModelError
from .idn import IDN, parse_idn
from .scpi import SCPIBackend, SCPIClient
from .status import SystemErrorEntry, parse_system_error
from .timebase import TimebaseController
from .trigger import EdgeTriggerController, EdgeTriggerState
from .visa_backend import VisaBackend
from .waveform import WaveformCapture, WaveformController


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

    def set_channel_scale(self, channel: int, volts_per_division: float) -> None:
        """Set one analog channel vertical scale in volts per division."""

        self._channel_controller().set_scale(channel, volts_per_division)

    def query_channel_scale(self, channel: int) -> float:
        """Query one analog channel vertical scale in volts per division."""

        return self._channel_controller().query_scale(channel)

    def set_channel_offset(self, channel: int, volts: float) -> None:
        """Set one analog channel vertical offset in volts."""

        self._channel_controller().set_offset(channel, volts)

    def query_channel_offset(self, channel: int) -> float:
        """Query one analog channel vertical offset in volts."""

        return self._channel_controller().query_offset(channel)

    def set_timebase_scale(self, seconds_per_division: float) -> None:
        """Set the horizontal scale in seconds per division."""

        self._timebase_controller().set_scale(seconds_per_division)

    def query_timebase_scale(self) -> float:
        """Query the horizontal scale in seconds per division."""

        return self._timebase_controller().query_scale()

    def set_timebase_position(self, seconds: float) -> None:
        """Set the horizontal position in seconds."""

        self._timebase_controller().set_position(seconds)

    def query_timebase_position(self) -> float:
        """Query the horizontal position in seconds."""

        return self._timebase_controller().query_position()

    def configure_edge_trigger(self, source_channel: int, level_volts: float, slope: str) -> None:
        """Configure analog edge trigger source, level, and slope."""

        self._edge_trigger_controller().configure(source_channel, level_volts, slope)

    def query_edge_trigger(self) -> EdgeTriggerState:
        """Query analog edge trigger source, level, and slope."""

        return self._edge_trigger_controller().query()

    def capture_waveform_byte(self, channel: int, points: int = 1000) -> WaveformCapture:
        """Capture one analog channel using BYTE waveform format."""

        return self._waveform_controller().capture_byte(channel, points=points)

    def capture_waveform_word(self, channel: int, points: int = 1000) -> WaveformCapture:
        """Capture one analog channel using WORD waveform format."""

        return self._waveform_controller().capture_word(channel, points=points)

    def close(self) -> None:
        """Close the underlying backend."""

        self.backend.close()

    def _channel_controller(self) -> ChannelController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Channel operations require known capabilities; call query_idn() first."
        )
        return ChannelController(self.scpi, self.capabilities)

    def _timebase_controller(self) -> TimebaseController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Timebase operations require known capabilities; call query_idn() first."
        )
        return TimebaseController(self.scpi)

    def _edge_trigger_controller(self) -> EdgeTriggerController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Edge trigger operations require known capabilities; call query_idn() first."
            )
        return EdgeTriggerController(self.scpi, self.capabilities)

    def _waveform_controller(self) -> WaveformController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Waveform operations require known capabilities; call query_idn() first."
            )
        return WaveformController(self.scpi, self.capabilities)

    def __enter__(self) -> "KeysightScope":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()
