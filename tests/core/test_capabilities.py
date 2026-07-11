import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import UnsupportedModelError


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


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("DSOX2004A", False),
        ("DSOX3024A", True),
        ("DSOX4024A", True),
    ],
)
def test_impedance_50_ohm_support_comes_from_capability_profile(model, expected):
    assert capabilities_for_model(model).supports_50_ohm_impedance is expected


@pytest.mark.parametrize(
    "model, modes",
    [
        ("DSOX2004A", {"serial1"}),
        ("DSOX3024A", {"edge", "glitch", "runt", "transition", "serial1", "serial2"}),
        ("DSOX4034A", {"edge", "glitch", "runt", "transition", "serial1", "serial2", "peak"}),
    ],
)
def test_search_basic_support_comes_from_capability_profile(model, modes):
    capabilities = capabilities_for_model(model)
    assert capabilities.supports_search_basic is True
    assert capabilities.search_modes == frozenset(modes)


@pytest.mark.parametrize("model", ["DSOX2004A", "DSOX3024A", "DSOX4024A"])
def test_runtime_capabilities_enable_word_and_measurements(model):
    capabilities = capabilities_for_model(model)

    assert capabilities.supports_word_format is True
    assert capabilities.supports_measurements is True


def test_capabilities_keep_unsupported_future_surfaces_disabled():
    capabilities = capabilities_for_model("DSOX4024A")

    assert capabilities.supports_raw_points_mode is False
    assert capabilities.supports_segmented_memory is False
    assert capabilities.supports_serial_decode is False


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("DSOX2004A", False),
        ("DSOX3024A", False),
        ("DSOX4024A", True),
    ],
)
def test_delay_measurement_support_comes_from_capability_profile(model, expected):
    assert capabilities_for_model(model).supports_delay_measurement is expected


def test_capabilities_reject_unknown_model():
    with pytest.raises(UnsupportedModelError):
        capabilities_for_model("DSO-X-UNKNOWN")
