"""Oscilloscope screen image capture helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .capabilities import ScopeCapabilities
from .errors import ParameterValidationError, ScreenshotResponseError
from .scpi import SCPIClient

SCREENSHOT_FORMAT = "PNG"
SCREENSHOT_PALETTE = "COLor"
SCREENSHOT_TIMEOUT_MS = 10000
DEFAULT_SCREENSHOT_BACKGROUND = "black"
SCREENSHOT_BACKGROUND_CHOICES = ("black", "white")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class ScreenshotCapture:
    """Captured oscilloscope screen image bytes."""

    format_name: str
    palette: str
    data: bytes
    background: str


class ScreenshotController:
    """Controls for current screen image capture."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def capture_png(
        self,
        *,
        background: str = DEFAULT_SCREENSHOT_BACKGROUND,
        timeout_ms: int = SCREENSHOT_TIMEOUT_MS,
    ) -> ScreenshotCapture:
        """Capture the current screen as a color PNG image."""

        if not self.capabilities.supports_screenshot:
            raise ParameterValidationError(
                f"screenshot capture is not enabled for {self.capabilities.series} capabilities."
            )

        background = normalize_screenshot_background(background)
        raw_values = self._capture_png_values(background, timeout_ms)
        data = screenshot_bytes_from_values(raw_values)
        return ScreenshotCapture(
            format_name=SCREENSHOT_FORMAT,
            palette=SCREENSHOT_PALETTE,
            data=data,
            background=background,
        )

    def _capture_png_values(self, background: str, timeout_ms: int) -> Sequence[int]:
        original_inksaver = parse_hardcopy_inksaver(self.scpi.query(hardcopy_inksaver_query()))
        desired_inksaver = hardcopy_inksaver_for_background(background)
        if original_inksaver != desired_inksaver:
            self.scpi.write(hardcopy_inksaver_command(desired_inksaver))
        try:
            return self._query_screenshot_data(timeout_ms)
        finally:
            if original_inksaver != desired_inksaver:
                self.scpi.write(hardcopy_inksaver_command(original_inksaver))

    def _query_screenshot_data(self, timeout_ms: int) -> Sequence[int]:
        original_timeout = self.scpi.timeout
        self.scpi.set_timeout(timeout_ms)
        try:
            return self.scpi.query_binary_values(screenshot_data_query(), datatype="B")
        finally:
            self.scpi.set_timeout(original_timeout)


def normalize_screenshot_background(background: str) -> str:
    """Normalize a screenshot background option."""

    normalized = background.strip().lower()
    if normalized not in SCREENSHOT_BACKGROUND_CHOICES:
        supported = ", ".join(SCREENSHOT_BACKGROUND_CHOICES)
        raise ParameterValidationError(f"screenshot background must be one of: {supported}.")
    return normalized


def hardcopy_inksaver_for_background(background: str) -> bool:
    """Return the `:HARDcopy:INKSaver` state needed for a background option."""

    background = normalize_screenshot_background(background)
    return background == "white"


def hardcopy_inksaver_query() -> str:
    """Build the SCPI query for hardcopy ink saver state."""

    return ":HARDcopy:INKSaver?"


def hardcopy_inksaver_command(enabled: bool) -> str:
    """Build the SCPI command for hardcopy ink saver state."""

    return f":HARDcopy:INKSaver {'ON' if enabled else 'OFF'}"


def parse_hardcopy_inksaver(response: str) -> bool:
    """Parse a hardcopy ink saver query response."""

    value = response.strip()
    if value == "0":
        return False
    if value == "1":
        return True
    raise ScreenshotResponseError(f"Could not parse hardcopy ink saver response: {response!r}")


def screenshot_data_query() -> str:
    """Build the SCPI query for a color PNG screenshot."""

    return f":DISPlay:DATA? {SCREENSHOT_FORMAT}, {SCREENSHOT_PALETTE}"


def screenshot_bytes_from_values(values: Sequence[int]) -> bytes:
    """Convert binary query values to PNG bytes and validate the response."""

    data = bytes(_validate_byte_value(value) for value in values)
    if not data:
        raise ScreenshotResponseError("Screenshot data query returned no bytes.")
    if not data.startswith(PNG_SIGNATURE):
        raise ScreenshotResponseError("Screenshot data is not a PNG image.")
    return data


def write_screenshot_png(capture: ScreenshotCapture, path: str | Path) -> Path:
    """Write captured screenshot bytes to a PNG file."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(capture.data)
    return output_path


def _validate_byte_value(value: int) -> int:
    byte_value = int(value)
    if byte_value < 0 or byte_value > 255:
        raise ScreenshotResponseError(f"Screenshot byte out of range: {value!r}")
    return byte_value
