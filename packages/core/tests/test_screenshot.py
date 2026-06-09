import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import ParameterValidationError, ScreenshotResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.screenshot import (
    PNG_SIGNATURE,
    ScreenshotCapture,
    ScreenshotController,
    hardcopy_inksaver_command,
    hardcopy_inksaver_for_background,
    hardcopy_inksaver_query,
    normalize_screenshot_background,
    parse_hardcopy_inksaver,
    screenshot_bytes_from_values,
    screenshot_data_query,
    write_screenshot_png,
)


PNG_BYTES = PNG_SIGNATURE + b"\x00\x00\x00\rIHDR"


def test_screenshot_command_uses_keysight_display_data_syntax():
    assert screenshot_data_query() == ":DISPlay:DATA? PNG, COLor"
    assert hardcopy_inksaver_query() == ":HARDcopy:INKSaver?"
    assert hardcopy_inksaver_command(False) == ":HARDcopy:INKSaver OFF"
    assert hardcopy_inksaver_command(True) == ":HARDcopy:INKSaver ON"


def test_screenshot_background_options_map_to_inksaver_state():
    assert normalize_screenshot_background("BLACK") == "black"
    assert normalize_screenshot_background("white") == "white"
    assert hardcopy_inksaver_for_background("black") is False
    assert hardcopy_inksaver_for_background("white") is True


def test_screenshot_background_rejects_unknown_value():
    with pytest.raises(ParameterValidationError):
        normalize_screenshot_background("blue")


def test_parse_hardcopy_inksaver():
    assert parse_hardcopy_inksaver("0") is False
    assert parse_hardcopy_inksaver("1") is True
    with pytest.raises(ScreenshotResponseError):
        parse_hardcopy_inksaver("ON")


def test_screenshot_bytes_from_values_validates_png_signature():
    assert screenshot_bytes_from_values(PNG_BYTES) == PNG_BYTES


@pytest.mark.parametrize("values", [b"", b"not png"])
def test_screenshot_bytes_from_values_rejects_invalid_png(values):
    with pytest.raises(ScreenshotResponseError):
        screenshot_bytes_from_values(values)


def test_screenshot_bytes_from_values_rejects_out_of_range_byte():
    with pytest.raises(ScreenshotResponseError):
        screenshot_bytes_from_values([256])


def test_screenshot_controller_captures_png_data_with_temporary_timeout():
    backend = FakeBackend(
        responses={":HARDcopy:INKSaver?": "1"},
        binary_responses={":DISPlay:DATA? PNG, COLor": list(PNG_BYTES)},
        timeout=2000,
    )
    controller = ScreenshotController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    capture = controller.capture_png()

    assert capture.format_name == "PNG"
    assert capture.palette == "COLor"
    assert capture.background == "black"
    assert capture.data == PNG_BYTES
    assert backend.history == [
        ":HARDcopy:INKSaver?",
        ":HARDcopy:INKSaver OFF",
        ":DISPlay:DATA? PNG, COLor",
        ":HARDcopy:INKSaver ON",
    ]
    assert backend.binary_query_kwargs == [{"datatype": "B"}]
    assert backend.timeout_history == [10000, 2000]
    assert backend.timeout == 2000


def test_screenshot_controller_supports_white_background():
    backend = FakeBackend(
        responses={":HARDcopy:INKSaver?": "0"},
        binary_responses={":DISPlay:DATA? PNG, COLor": list(PNG_BYTES)},
    )
    controller = ScreenshotController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    capture = controller.capture_png(background="white")

    assert capture.background == "white"
    assert backend.history == [
        ":HARDcopy:INKSaver?",
        ":HARDcopy:INKSaver ON",
        ":DISPlay:DATA? PNG, COLor",
        ":HARDcopy:INKSaver OFF",
    ]


def test_screenshot_controller_rejects_disabled_capability():
    capabilities = capabilities_for_model("DSOX4024A")
    disabled = capabilities.__class__(
        series=capabilities.series,
        analog_channels=capabilities.analog_channels,
        default_waveform_points=capabilities.default_waveform_points,
        safe_max_waveform_points=capabilities.safe_max_waveform_points,
        supports_word_format=capabilities.supports_word_format,
        supports_raw_points_mode=capabilities.supports_raw_points_mode,
        supports_measurements=capabilities.supports_measurements,
        supports_screenshot=False,
        supports_segmented_memory=capabilities.supports_segmented_memory,
        supports_serial_decode=capabilities.supports_serial_decode,
    )
    backend = FakeBackend()
    controller = ScreenshotController(SCPIClient(backend), disabled)

    with pytest.raises(ParameterValidationError):
        controller.capture_png()

    assert backend.history == []


def test_screenshot_export_writes_png(tmp_path):
    capture = ScreenshotCapture(
        format_name="PNG",
        palette="COLor",
        data=PNG_BYTES,
        background="black",
    )
    output_path = tmp_path / "screens" / "screen.png"

    written = write_screenshot_png(capture, output_path)

    assert written == output_path
    assert output_path.read_bytes() == PNG_BYTES
