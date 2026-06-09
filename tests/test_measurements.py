import pytest

from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.errors import MeasurementResponseError, ParameterValidationError
from keysight_scope.fake_backend import FakeBackend
from keysight_scope.measurements import (
    INVALID_MEASUREMENT_REASON,
    MeasurementController,
    measurement_query,
    measurement_unit,
    normalize_measurement_item,
    parse_measurement_result,
)
from keysight_scope.scpi import SCPIClient


def test_measurement_query_uses_keysight_measure_syntax():
    assert measurement_query("vpp", 1) == ":MEASure:VPP? CHANnel1"
    assert measurement_query("frequency", 2) == ":MEASure:FREQuency? CHANnel2"
    assert measurement_query("freq", 2) == ":MEASure:FREQuency? CHANnel2"
    assert measurement_query("period", 1) == ":MEASure:PERiod? CHANnel1"
    assert measurement_query("vavg", 1) == ":MEASure:VAVerage? DISPlay,CHANnel1"
    assert measurement_query("vrms", 1) == ":MEASure:VRMS? DISPlay,DC,CHANnel1"
    assert measurement_query("minimum", 1) == ":MEASure:VMIN? CHANnel1"
    assert measurement_query("maximum", 1) == ":MEASure:VMAX? CHANnel1"
    assert measurement_query("rise_time", 1) == ":MEASure:RISetime? CHANnel1"
    assert measurement_query("fall_time", 1) == ":MEASure:FALLtime? CHANnel1"
    assert measurement_query("vmin", 1) == ":MEASure:VMIN? CHANnel1"
    assert measurement_query("vmax", 1) == ":MEASure:VMAX? CHANnel1"
    assert measurement_query("risetime", 1) == ":MEASure:RISetime? CHANnel1"
    assert measurement_query("falltime", 1) == ":MEASure:FALLtime? CHANnel1"


def test_measurement_item_normalization_accepts_aliases():
    assert normalize_measurement_item("freq") == "frequency"
    assert normalize_measurement_item("min") == "minimum"
    assert normalize_measurement_item("vmin") == "minimum"
    assert normalize_measurement_item("max") == "maximum"
    assert normalize_measurement_item("vmax") == "maximum"
    assert normalize_measurement_item("risetime") == "rise_time"
    assert normalize_measurement_item("rise-time") == "rise_time"
    assert normalize_measurement_item("falltime") == "fall_time"
    assert normalize_measurement_item("fall-time") == "fall_time"
    assert measurement_unit("frequency") == "Hz"
    assert measurement_unit("period") == "s"
    assert measurement_unit("vpp") == "V"
    assert measurement_unit("vavg") == "V"
    assert measurement_unit("vrms") == "V"
    assert measurement_unit("minimum") == "V"
    assert measurement_unit("maximum") == "V"
    assert measurement_unit("rise_time") == "s"
    assert measurement_unit("fall_time") == "s"


def test_measurement_item_normalization_rejects_unknown_item():
    with pytest.raises(ParameterValidationError):
        normalize_measurement_item("duty")


def test_parse_measurement_result_keeps_valid_numeric_value():
    result = parse_measurement_result("5.0E-1", item="vpp", channel=1)

    assert result.valid is True
    assert result.value == 0.5
    assert result.raw_value == "5.0E-1"
    assert result.reason is None
    assert result.unit == "V"


@pytest.mark.parametrize("raw", ["9.9E+37", "9.900000E+37", "-9.9E+37"])
def test_parse_measurement_result_marks_invalid_sentinel_without_losing_raw(raw):
    result = parse_measurement_result(raw, item="frequency", channel=1)

    assert result.valid is False
    assert result.value is None
    assert result.raw_value == raw
    assert result.reason == INVALID_MEASUREMENT_REASON
    assert result.unit == "Hz"


@pytest.mark.parametrize("raw", ["not-a-number", "NaN", "INF"])
def test_parse_measurement_result_rejects_unparseable_response(raw):
    with pytest.raises(MeasurementResponseError):
        parse_measurement_result(raw, item="vpp", channel=1)


def test_measurement_controller_queries_vpp_for_channel():
    backend = FakeBackend(responses={":MEASure:VPP? CHANnel1": "1.25E+0"})
    controller = MeasurementController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    result = controller.query(1, "vpp")

    assert result.valid is True
    assert result.value == 1.25
    assert backend.history == [":MEASure:VPP? CHANnel1"]


@pytest.mark.parametrize(
    ("item", "response", "expected_value", "expected_history"),
    [
        ("period", "1.25E-4", 0.000125, [":MEASure:PERiod? CHANnel1"]),
        ("vavg", "-2.5E-2", -0.025, [":MEASure:VAVerage? DISPlay,CHANnel1"]),
        ("vrms", "7.07E-1", 0.707, [":MEASure:VRMS? DISPlay,DC,CHANnel1"]),
        ("minimum", "-1.25E+0", -1.25, [":MEASure:VMIN? CHANnel1"]),
        ("maximum", "1.25E+0", 1.25, [":MEASure:VMAX? CHANnel1"]),
        ("rise_time", "1.00E-6", 0.000001, [":MEASure:RISetime? CHANnel1"]),
        ("fall_time", "1.50E-6", 0.0000015, [":MEASure:FALLtime? CHANnel1"]),
    ],
)
def test_measurement_controller_queries_additional_read_only_items(
    item, response, expected_value, expected_history
):
    backend = FakeBackend(responses={expected_history[0]: response})
    controller = MeasurementController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    result = controller.query(1, item)

    assert result.valid is True
    assert result.value == expected_value
    assert backend.history == expected_history


def test_measurement_controller_rejects_invalid_channel_before_scpi():
    backend = FakeBackend()
    controller = MeasurementController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.query(3, "vpp")

    assert backend.history == []
