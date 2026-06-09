import pytest

from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.errors import UnsupportedModelError


@pytest.mark.parametrize(
    ("model", "series", "channels"),
    [
        ("DSOX2004A", "2000X", 4),
        ("DSO-X 2004A", "2000X", 4),
        ("DSOX3024A", "3000X", 4),
        ("DSO-X 3024A", "3000X", 4),
        ("DSOX4024A", "4000X", 4),
        ("DSO-X 4024A", "4000X", 4),
        ("DSOX4034A", "4000X", 4),
        ("DSOX4022A", "4000X", 2),
    ],
)
def test_capabilities_for_supported_models(model, series, channels):
    capabilities = capabilities_for_model(model)

    assert capabilities.series == series
    assert capabilities.analog_channels == channels
    assert capabilities.default_waveform_points == 1000
    assert capabilities.safe_max_waveform_points == 10000
    assert capabilities.supports_screenshot is True


def test_capabilities_are_conservative_for_phase_1():
    capabilities = capabilities_for_model("DSOX4024A")

    assert capabilities.supports_word_format is False
    assert capabilities.supports_raw_points_mode is False
    assert capabilities.supports_segmented_memory is False
    assert capabilities.supports_serial_decode is False


def test_capabilities_reject_unknown_model():
    with pytest.raises(UnsupportedModelError):
        capabilities_for_model("DSO-X-UNKNOWN")
