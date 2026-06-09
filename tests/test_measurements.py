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
    assert measurement_query("amplitude", 1) == ":MEASure:VAMPlitude? CHANnel1"
    assert measurement_query("top", 1) == ":MEASure:VTOP? CHANnel1"
    assert measurement_query("base", 1) == ":MEASure:VBASe? CHANnel1"
    assert measurement_query("overshoot", 1) == ":MEASure:OVERshoot? CHANnel1"
    assert measurement_query("preshoot", 1) == ":MEASure:PREShoot? CHANnel1"
    assert measurement_query("positive_width", 1) == ":MEASure:PWIDth? CHANnel1"
    assert measurement_query("negative_width", 1) == ":MEASure:NWIDth? CHANnel1"
    assert measurement_query("duty_cycle", 1) == ":MEASure:DUTYcycle? CHANnel1"
    assert measurement_query("negative_duty_cycle", 1) == ":MEASure:NDUTy? CHANnel1"
    assert measurement_query("area", 1) == ":MEASure:AREA? CHANnel1"
    assert measurement_query("vmin", 1) == ":MEASure:VMIN? CHANnel1"
    assert measurement_query("vmax", 1) == ":MEASure:VMAX? CHANnel1"
    assert measurement_query("risetime", 1) == ":MEASure:RISetime? CHANnel1"
    assert measurement_query("falltime", 1) == ":MEASure:FALLtime? CHANnel1"
    assert measurement_query("vamp", 1) == ":MEASure:VAMPlitude? CHANnel1"
    assert measurement_query("vtop", 1) == ":MEASure:VTOP? CHANnel1"
    assert measurement_query("vbase", 1) == ":MEASure:VBASe? CHANnel1"
    assert measurement_query("pwidth", 1) == ":MEASure:PWIDth? CHANnel1"
    assert measurement_query("positive-width", 1) == ":MEASure:PWIDth? CHANnel1"
    assert measurement_query("pwid", 1) == ":MEASure:PWIDth? CHANnel1"
    assert measurement_query("nwidth", 1) == ":MEASure:NWIDth? CHANnel1"
    assert measurement_query("negative-width", 1) == ":MEASure:NWIDth? CHANnel1"
    assert measurement_query("nwid", 1) == ":MEASure:NWIDth? CHANnel1"
    assert measurement_query("duty", 1) == ":MEASure:DUTYcycle? CHANnel1"
    assert measurement_query("dutycycle", 1) == ":MEASure:DUTYcycle? CHANnel1"
    assert measurement_query("duty-cycle", 1) == ":MEASure:DUTYcycle? CHANnel1"
    assert measurement_query("nduty", 1) == ":MEASure:NDUTy? CHANnel1"
    assert measurement_query("negative-duty", 1) == ":MEASure:NDUTy? CHANnel1"
    assert measurement_query("negative-duty-cycle", 1) == ":MEASure:NDUTy? CHANnel1"


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
    assert normalize_measurement_item("vamp") == "amplitude"
    assert normalize_measurement_item("vtop") == "top"
    assert normalize_measurement_item("vbase") == "base"
    assert normalize_measurement_item("pwidth") == "positive_width"
    assert normalize_measurement_item("positive-width") == "positive_width"
    assert normalize_measurement_item("pwid") == "positive_width"
    assert normalize_measurement_item("nwidth") == "negative_width"
    assert normalize_measurement_item("negative-width") == "negative_width"
    assert normalize_measurement_item("nwid") == "negative_width"
    assert normalize_measurement_item("duty") == "duty_cycle"
    assert normalize_measurement_item("dutycycle") == "duty_cycle"
    assert normalize_measurement_item("duty-cycle") == "duty_cycle"
    assert normalize_measurement_item("nduty") == "negative_duty_cycle"
    assert normalize_measurement_item("negative-duty") == "negative_duty_cycle"
    assert normalize_measurement_item("negative-duty-cycle") == "negative_duty_cycle"
    assert measurement_unit("frequency") == "Hz"
    assert measurement_unit("period") == "s"
    assert measurement_unit("vpp") == "V"
    assert measurement_unit("vavg") == "V"
    assert measurement_unit("vrms") == "V"
    assert measurement_unit("minimum") == "V"
    assert measurement_unit("maximum") == "V"
    assert measurement_unit("rise_time") == "s"
    assert measurement_unit("fall_time") == "s"
    assert measurement_unit("amplitude") == "V"
    assert measurement_unit("top") == "V"
    assert measurement_unit("base") == "V"
    assert measurement_unit("overshoot") == "%"
    assert measurement_unit("preshoot") == "%"
    assert measurement_unit("positive_width") == "s"
    assert measurement_unit("negative_width") == "s"
    assert measurement_unit("duty_cycle") == "%"
    assert measurement_unit("negative_duty_cycle") == "%"
    assert measurement_unit("area") == "V*s"


def test_measurement_item_normalization_rejects_unknown_item():
    with pytest.raises(ParameterValidationError):
        normalize_measurement_item("delay")


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


@pytest.mark.parametrize(
    ("item", "unit"),
    [
        ("overshoot", "%"),
        ("positive_width", "s"),
        ("area", "V*s"),
    ],
)
def test_parse_measurement_result_preserves_invalid_sentinel_for_new_units(item, unit):
    result = parse_measurement_result("9.9E+37", item=item, channel=1)

    assert result.valid is False
    assert result.value is None
    assert result.raw_value == "9.9E+37"
    assert result.reason == INVALID_MEASUREMENT_REASON
    assert result.unit == unit


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
        ("amplitude", "1.20E+0", 1.2, [":MEASure:VAMPlitude? CHANnel1"]),
        ("top", "7.50E-1", 0.75, [":MEASure:VTOP? CHANnel1"]),
        ("base", "-4.50E-1", -0.45, [":MEASure:VBASe? CHANnel1"]),
        ("overshoot", "5.50E+0", 5.5, [":MEASure:OVERshoot? CHANnel1"]),
        ("preshoot", "2.50E+0", 2.5, [":MEASure:PREShoot? CHANnel1"]),
        ("positive_width", "2.00E-6", 0.000002, [":MEASure:PWIDth? CHANnel1"]),
        ("negative_width", "3.00E-6", 0.000003, [":MEASure:NWIDth? CHANnel1"]),
        ("duty_cycle", "4.80E+1", 48.0, [":MEASure:DUTYcycle? CHANnel1"]),
        ("negative_duty_cycle", "5.20E+1", 52.0, [":MEASure:NDUTy? CHANnel1"]),
        ("area", "1.20E-6", 0.0000012, [":MEASure:AREA? CHANnel1"]),
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
