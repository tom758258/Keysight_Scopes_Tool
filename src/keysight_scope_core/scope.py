"""High-level oscilloscope object."""

from __future__ import annotations

from typing import Sequence

from .acquisition import AcquisitionConfig, AcquisitionController
from .advanced import (
    CursorController,
    CursorState,
    FFTController,
    FFTState,
    SetupController,
    TriggerHoldoffController,
)
from .capabilities import ScopeCapabilities, capabilities_for_model
from .channel import ChannelController
from .display import AnnotationState, DisplayController, DisplayPersistence
from .errors import ParameterValidationError, UnsupportedModelError
from .idn import IDN, parse_idn
from .measurements import MeasurementController, MeasurementResult, MeasurementStatisticsResult
from .scpi import SCPIBackend, SCPIClient
from .screenshot import ScreenshotCapture, ScreenshotController
from .status import SystemErrorEntry, parse_system_error
from .timebase import TimebaseController
from .trigger import EdgeTriggerController, EdgeTriggerState, GlitchTriggerController, GlitchTriggerState
from .visa_backend import VisaBackend
from .waveform import MultiChannelWaveformCapture, WaveformCapture, WaveformController


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

    def set_channel_coupling(self, channel: int, coupling: str) -> None:
        """Set one analog channel input coupling."""

        self._channel_controller().set_coupling(channel, coupling)

    def query_channel_coupling(self, channel: int) -> str:
        """Query one analog channel input coupling."""

        return self._channel_controller().query_coupling(channel)

    def set_channel_probe_ratio(self, channel: int, ratio: float) -> None:
        """Set one analog channel probe attenuation ratio."""

        self._channel_controller().set_probe_ratio(channel, ratio)

    def query_channel_probe_ratio(self, channel: int) -> float:
        """Query one analog channel probe attenuation ratio."""

        return self._channel_controller().query_probe_ratio(channel)

    def set_channel_bandwidth_limit(self, channel: int, enabled: bool) -> None:
        """Turn one analog channel bandwidth limit on or off."""

        self._channel_controller().set_bandwidth_limit(channel, enabled)

    def query_channel_bandwidth_limit(self, channel: int) -> bool:
        """Query whether one analog channel bandwidth limit is enabled."""

        return self._channel_controller().query_bandwidth_limit(channel)

    def set_channel_impedance(self, channel: int, impedance: str) -> None:
        """Set one analog channel input impedance."""

        self._channel_controller().set_impedance(channel, impedance)

    def query_channel_impedance(self, channel: int) -> str:
        """Query one analog channel input impedance."""

        return self._channel_controller().query_impedance(channel)

    def set_channel_invert(self, channel: int, enabled: bool) -> None:
        """Turn one analog channel inversion on or off."""

        self._channel_controller().set_invert(channel, enabled)

    def query_channel_invert(self, channel: int) -> bool:
        """Query whether one analog channel inversion is enabled."""

        return self._channel_controller().query_invert(channel)

    def set_channel_range(self, channel: int, volts: float) -> None:
        """Set one analog channel full-scale range in volts."""

        self._channel_controller().set_range(channel, volts)

    def query_channel_range(self, channel: int) -> float:
        """Query one analog channel full-scale range in volts."""

        return self._channel_controller().query_range(channel)

    def set_channel_units(self, channel: int, units: str) -> None:
        """Set one analog channel units."""

        self._channel_controller().set_units(channel, units)

    def query_channel_units(self, channel: int) -> str:
        """Query one analog channel units."""

        return self._channel_controller().query_units(channel)

    def set_channel_vernier(self, channel: int, enabled: bool) -> None:
        """Turn one analog channel vernier scaling on or off."""

        self._channel_controller().set_vernier(channel, enabled)

    def query_channel_vernier(self, channel: int) -> bool:
        """Query whether one analog channel vernier scaling is enabled."""

        return self._channel_controller().query_vernier(channel)

    def set_channel_probe_skew(self, channel: int, seconds: float) -> None:
        """Set one analog channel probe skew in seconds."""

        self._channel_controller().set_probe_skew(channel, seconds)

    def query_channel_probe_skew(self, channel: int) -> float:
        """Query one analog channel probe skew in seconds."""

        return self._channel_controller().query_probe_skew(channel)

    def set_channel_label(self, channel: int, text: str) -> None:
        """Set one analog channel label."""

        self._channel_controller().set_label(channel, text)

    def query_channel_label(self, channel: int) -> str:
        """Query one analog channel label."""

        return self._channel_controller().query_label(channel)

    def set_display_label(self, enabled: bool) -> None:
        """Turn display labels on or off."""

        self._display_controller().set_label(enabled)

    def query_display_label(self) -> bool:
        """Query whether display labels are enabled."""

        return self._display_controller().query_label()

    def clear_display(self) -> None:
        """Clear waveform display data and associated measurements."""

        self._display_controller().clear_display()

    def set_display_persistence(self, value: str | float) -> None:
        self._display_controller().set_persistence(value)

    def query_display_persistence(self) -> DisplayPersistence:
        return self._display_controller().query_persistence()

    def set_display_intensity(self, value: int) -> None:
        self._display_controller().set_intensity(value)

    def query_display_intensity(self) -> tuple[int, str]:
        return self._display_controller().query_intensity()

    def set_display_vectors_on(self) -> None:
        self._display_controller().set_vectors_on()

    def query_display_vectors(self) -> tuple[bool, str]:
        return self._display_controller().query_vectors()

    def set_annotation_enabled(self, enabled: bool, *, slot: int = 1) -> None:
        self._display_controller().set_annotation_enabled(enabled, slot=slot)

    def clear_annotation(self, *, slot: int = 1) -> None:
        self._display_controller().clear_annotation(slot=slot)

    def set_annotation_text(self, text: str, *, slot: int = 1) -> None:
        self._display_controller().set_annotation_text(text, slot=slot)

    def set_annotation_color(self, color: str, *, slot: int = 1) -> None:
        self._display_controller().set_annotation_color(color, slot=slot)

    def set_annotation_background(self, background: str, *, slot: int = 1) -> None:
        self._display_controller().set_annotation_background(background, slot=slot)

    def set_annotation_position(
        self, x: int | None = None, y: int | None = None, *, slot: int = 1
    ) -> None:
        self._display_controller().set_annotation_position(x=x, y=y, slot=slot)

    def query_annotation(self, *, slot: int = 1) -> AnnotationState:
        return self._display_controller().query_annotation(slot=slot)

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

    def configure_glitch_trigger(
        self,
        *,
        channel: int,
        polarity: str,
        qualifier: str,
        time_seconds: float | None = None,
        min_time_seconds: float | None = None,
        max_time_seconds: float | None = None,
        level_volts: float | None = None,
    ) -> None:
        """Configure analog pulse-width glitch trigger settings."""

        self._glitch_trigger_controller().configure(
            channel=channel,
            polarity=polarity,
            qualifier=qualifier,
            time_seconds=time_seconds,
            min_time_seconds=min_time_seconds,
            max_time_seconds=max_time_seconds,
            level_volts=level_volts,
        )

    def query_glitch_trigger(self) -> GlitchTriggerState:
        """Query pulse-width glitch trigger settings."""

        return self._glitch_trigger_controller().query()

    def capture_waveform_byte(self, channel: int, points: int = 1000) -> WaveformCapture:
        """Capture one analog channel using BYTE waveform format."""

        return self._waveform_controller().capture_byte(channel, points=points)

    def capture_waveform_word(self, channel: int, points: int = 1000) -> WaveformCapture:
        """Capture one analog channel using WORD waveform format."""

        return self._waveform_controller().capture_word(channel, points=points)

    def capture_waveforms_byte(
        self, channels: Sequence[int], points: int = 1000
    ) -> MultiChannelWaveformCapture:
        """Capture multiple analog channels using BYTE waveform format."""

        return self._waveform_controller().capture_channels_byte(channels, points=points)

    def capture_waveforms_word(
        self, channels: Sequence[int], points: int = 1000
    ) -> MultiChannelWaveformCapture:
        """Capture multiple analog channels using WORD waveform format."""

        return self._waveform_controller().capture_channels_word(channels, points=points)

    def query_measurement(
        self,
        channel: int,
        item: str,
        *,
        time_s: float | None = None,
        level: float | None = None,
        slope: str | None = None,
        occurrence: int | None = None,
    ) -> MeasurementResult:
        """Query one read-only measurement item for one analog channel."""

        return self._measurement_controller().query(
            channel,
            item,
            time_s=time_s,
            level=level,
            slope=slope,
            occurrence=occurrence,
        )

    def query_pair_measurement(
        self,
        source_channel: int,
        reference_channel: int,
        item: str,
    ) -> MeasurementResult:
        """Query one read-only measurement item comparing two analog channels."""

        return self._measurement_controller().query_pair(
            source_channel,
            reference_channel,
            item,
        )

    def configure_cursor(
        self,
        source_channel: int,
        x1_seconds: float,
        x2_seconds: float,
        *,
        y1_volts: float | None = None,
        y2_volts: float | None = None,
        auto_timebase: bool = False,
        auto_vertical: bool = False,
    ) -> None:
        self._cursor_controller().set_manual(
            source_channel,
            x1_seconds,
            x2_seconds,
            y1_volts=y1_volts,
            y2_volts=y2_volts,
            auto_timebase=auto_timebase,
            auto_vertical=auto_vertical,
        )

    def cursor_off(self) -> None:
        self._cursor_controller().off()

    def query_cursor(self) -> CursorState:
        return self._cursor_controller().query()

    def set_trigger_holdoff(self, seconds: float) -> None:
        self._trigger_holdoff_controller().set_seconds(seconds)

    def query_trigger_holdoff(self) -> float:
        return self._trigger_holdoff_controller().query_seconds()

    def query_measurement_statistics(
        self,
        channel: int,
        items: Sequence[str],
        *,
        mode: str = "all",
        reset: bool = False,
        max_count: int | None = None,
        settle_seconds: float | None = None,
    ) -> MeasurementStatisticsResult:
        return self._measurement_controller().statistics(
            channel,
            items,
            mode=mode,
            reset=reset,
            max_count=max_count,
            settle_seconds=settle_seconds,
        )

    def autoscale(
        self,
        channels: Sequence[int] | None,
        *,
        acquire_mode: str | None = None,
        channels_mode: str | None = None,
    ) -> None:
        self._setup_controller().autoscale(
            channels,
            acquire_mode=acquire_mode,
            channels_mode=channels_mode,
            capabilities=self.capabilities,
        )

    def save_setup(self, *, slot: int | None = None, file_spec: str | None = None) -> None:
        self._setup_controller().save(slot=slot, file_spec=file_spec)

    def recall_setup(self, *, slot: int | None = None, file_spec: str | None = None) -> None:
        self._setup_controller().recall(slot=slot, file_spec=file_spec)

    def configure_fft(
        self,
        function: int,
        source_channel: int,
        *,
        units: str | None = None,
        window: str | None = None,
        center_hz: float | None = None,
        span_hz: float | None = None,
        display: bool | None = None,
    ) -> None:
        self._fft_controller().configure(
            function,
            source_channel,
            units=units,
            window=window,
            center_hz=center_hz,
            span_hz=span_hz,
            display=display,
        )

    def query_fft(self, function: int) -> FFTState:
        return self._fft_controller().query(function)

    def capture_screenshot_png(self, *, background: str = "black") -> ScreenshotCapture:
        """Capture the current screen as a color PNG image."""

        return self._screenshot_controller().capture_png(background=background)

    def set_acquisition_type(self, acquisition_type: str) -> None:
        """Set the acquisition type."""

        self._acquisition_controller().set_type(acquisition_type)

    def query_acquisition_type(self) -> str:
        """Query the current acquisition type."""

        return self._acquisition_controller().query_type()

    def set_acquisition_count(self, count: int) -> None:
        """Set the average count for average acquisition mode."""

        self._acquisition_controller().set_count(count)

    def query_acquisition_count(self) -> int:
        """Query the current average count."""

        return self._acquisition_controller().query_count()

    def query_acquisition_config(self) -> AcquisitionConfig:
        """Query both acquisition type and count."""

        return self._acquisition_controller().query_config()

    def close(self) -> None:
        """Close the underlying backend."""

        self.backend.close()

    def _channel_controller(self) -> ChannelController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Channel operations require known capabilities; call query_idn() first."
            )
        return ChannelController(self.scpi, self.capabilities)

    def _display_controller(self) -> DisplayController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Display operations require known capabilities; call query_idn() first."
            )
        return DisplayController(self.scpi, self.capabilities)

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

    def _glitch_trigger_controller(self) -> GlitchTriggerController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Glitch trigger operations require known capabilities; call query_idn() first."
            )
        return GlitchTriggerController(self.scpi, self.capabilities)

    def _waveform_controller(self) -> WaveformController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Waveform operations require known capabilities; call query_idn() first."
            )
        return WaveformController(self.scpi, self.capabilities)

    def _measurement_controller(self) -> MeasurementController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Measurement operations require known capabilities; call query_idn() first."
            )
        return MeasurementController(self.scpi, self.capabilities)

    def _cursor_controller(self) -> CursorController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Cursor operations require known capabilities; call query_idn() first."
            )
        return CursorController(self.scpi, self.capabilities)

    def _trigger_holdoff_controller(self) -> TriggerHoldoffController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Trigger holdoff operations require known capabilities; call query_idn() first."
            )
        return TriggerHoldoffController(self.scpi)

    def _setup_controller(self) -> SetupController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Setup operations require known capabilities; call query_idn() first."
            )
        return SetupController(self.scpi)

    def _fft_controller(self) -> FFTController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "FFT operations require known capabilities; call query_idn() first."
            )
        return FFTController(self.scpi, self.capabilities)

    def _screenshot_controller(self) -> ScreenshotController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Screenshot operations require known capabilities; call query_idn() first."
            )
        return ScreenshotController(self.scpi, self.capabilities)

    def _acquisition_controller(self) -> AcquisitionController:
        if self.capabilities is None:
            raise ParameterValidationError(
                "Acquisition operations require known capabilities; call query_idn() first."
            )
        return AcquisitionController(self.scpi)

    def __enter__(self) -> "KeysightScope":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()
