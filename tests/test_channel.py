import pytest

from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.channel import (
    ChannelController,
    channel_bandwidth_limit_command,
    channel_bandwidth_limit_query,
    channel_coupling_command,
    channel_coupling_query,
    channel_display_command,
    channel_display_query,
    channel_offset_command,
    channel_offset_query,
    channel_probe_ratio_command,
    channel_probe_ratio_query,
    channel_scale_command,
    channel_scale_query,
    normalize_channel_coupling,
    parse_channel_bool,
    parse_channel_coupling,
    parse_channel_display,
    parse_channel_float,
    validate_analog_channel,
    validate_channel_offset,
    validate_channel_scale,
    validate_probe_ratio,
)
from keysight_scope.errors import ChannelResponseError, ParameterValidationError
from keysight_scope.fake_backend import FakeBackend
from keysight_scope.scpi import SCPIClient


def test_channel_display_command_uses_keysight_channel_syntax():
    assert channel_display_command(1, True) == ":CHANnel1:DISPlay ON"
    assert channel_display_command(2, False) == ":CHANnel2:DISPlay OFF"
    assert channel_display_query(3) == ":CHANnel3:DISPlay?"


def test_channel_scale_and_offset_commands_use_keysight_channel_syntax():
    assert channel_scale_command(1, 0.5) == ":CHANnel1:SCALe 0.5"
    assert channel_scale_query(2) == ":CHANnel2:SCALe?"
    assert channel_offset_command(3, -0.125) == ":CHANnel3:OFFSet -0.125"
    assert channel_offset_query(4) == ":CHANnel4:OFFSet?"


def test_channel_parameter_commands_use_keysight_channel_syntax():
    assert channel_coupling_command(1, "ac") == ":CHANnel1:COUPling AC"
    assert channel_coupling_query(2) == ":CHANnel2:COUPling?"
    assert channel_probe_ratio_command(3, 10) == ":CHANnel3:PROBe 10"
    assert channel_probe_ratio_query(4) == ":CHANnel4:PROBe?"
    assert channel_bandwidth_limit_command(1, True) == ":CHANnel1:BWLimit ON"
    assert channel_bandwidth_limit_command(2, False) == ":CHANnel2:BWLimit OFF"
    assert channel_bandwidth_limit_query(3) == ":CHANnel3:BWLimit?"


@pytest.mark.parametrize("raw", ["1", "+1", "ON", " on "])
def test_parse_channel_display_enabled(raw):
    assert parse_channel_display(raw) is True


@pytest.mark.parametrize("raw", ["0", "+0", "OFF", " off "])
def test_parse_channel_display_disabled(raw):
    assert parse_channel_display(raw) is False


def test_parse_channel_display_rejects_unexpected_response():
    with pytest.raises(ChannelResponseError):
        parse_channel_display("MAYBE")


@pytest.mark.parametrize("raw", ["1", "+1", "ON", " on "])
def test_parse_channel_bool_enabled(raw):
    assert parse_channel_bool(raw, "bandwidth limit") is True


@pytest.mark.parametrize("raw", ["0", "+0", "OFF", " off "])
def test_parse_channel_bool_disabled(raw):
    assert parse_channel_bool(raw, "bandwidth limit") is False


@pytest.mark.parametrize("raw, expected", [("AC", "ac"), (" dc ", "dc")])
def test_parse_channel_coupling(raw, expected):
    assert parse_channel_coupling(raw) == expected


@pytest.mark.parametrize("raw", ["GND", "MAYBE", ""])
def test_parse_channel_coupling_rejects_unexpected_response(raw):
    with pytest.raises(ChannelResponseError):
        parse_channel_coupling(raw)


@pytest.mark.parametrize("raw, expected", [("5.0E-1", 0.5), (" -1.25E-1 ", -0.125)])
def test_parse_channel_float(raw, expected):
    assert parse_channel_float(raw, "scale") == expected


@pytest.mark.parametrize("raw", ["MAYBE", "NaN", "INF"])
def test_parse_channel_float_rejects_unexpected_response(raw):
    with pytest.raises(ChannelResponseError):
        parse_channel_float(raw, "scale")


def test_validate_analog_channel_uses_capability_channel_count():
    capabilities = capabilities_for_model("DSOX4022A")

    assert validate_analog_channel(2, capabilities) == 2
    with pytest.raises(ParameterValidationError):
        validate_analog_channel(3, capabilities)


@pytest.mark.parametrize("value", [1.0, 0.5, "0.001"])
def test_validate_channel_scale_accepts_positive_finite_values(value):
    assert validate_channel_scale(value) == float(value)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan"), "abc"])
def test_validate_channel_scale_rejects_non_positive_or_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_channel_scale(value)


@pytest.mark.parametrize("value", [0.0, -1.25, "0.5"])
def test_validate_channel_offset_accepts_finite_values(value):
    assert validate_channel_offset(value) == float(value)


@pytest.mark.parametrize("value", [float("inf"), float("nan"), "abc"])
def test_validate_channel_offset_rejects_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_channel_offset(value)


@pytest.mark.parametrize("value, expected", [("ac", "ac"), (" DC ", "dc")])
def test_normalize_channel_coupling_accepts_ac_and_dc(value, expected):
    assert normalize_channel_coupling(value) == expected


@pytest.mark.parametrize("value", ["gnd", "", None])
def test_normalize_channel_coupling_rejects_unsupported_values(value):
    with pytest.raises(ParameterValidationError):
        normalize_channel_coupling(value)


@pytest.mark.parametrize("value", [1.0, 10, "100"])
def test_validate_probe_ratio_accepts_positive_finite_values(value):
    assert validate_probe_ratio(value) == float(value)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan"), "abc"])
def test_validate_probe_ratio_rejects_non_positive_or_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_probe_ratio(value)


def test_channel_controller_sets_display_and_reads_back_state():
    backend = FakeBackend(responses={":CHANnel1:DISPlay?": "1"})
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_display(1, True)
    enabled = controller.query_display(1)

    assert enabled is True
    assert backend.history == [":CHANnel1:DISPlay ON", ":CHANnel1:DISPlay?"]


def test_channel_controller_rejects_invalid_channel_before_display_scpi():
    backend = FakeBackend()
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.set_display(3, True)

    assert backend.history == []


def test_channel_controller_sets_scale_and_reads_back_value():
    backend = FakeBackend(responses={":CHANnel1:SCALe?": "5.0E-1"})
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_scale(1, 0.5)
    scale = controller.query_scale(1)

    assert scale == 0.5
    assert backend.history == [":CHANnel1:SCALe 0.5", ":CHANnel1:SCALe?"]


def test_channel_controller_sets_offset_and_reads_back_value():
    backend = FakeBackend(responses={":CHANnel2:OFFSet?": "-1.25E-1"})
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_offset(2, -0.125)
    offset = controller.query_offset(2)

    assert offset == -0.125
    assert backend.history == [":CHANnel2:OFFSet -0.125", ":CHANnel2:OFFSet?"]


def test_channel_controller_sets_coupling_probe_and_bandwidth_limit():
    backend = FakeBackend(
        responses={
            ":CHANnel1:COUPling?": "DC",
            ":CHANnel1:PROBe?": "1.0E+1",
            ":CHANnel1:BWLimit?": "1",
        }
    )
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_coupling(1, "ac")
    coupling = controller.query_coupling(1)
    controller.set_probe_ratio(1, 10)
    ratio = controller.query_probe_ratio(1)
    controller.set_bandwidth_limit(1, True)
    bandwidth_limit = controller.query_bandwidth_limit(1)

    assert coupling == "dc"
    assert ratio == 10
    assert bandwidth_limit is True
    assert backend.history == [
        ":CHANnel1:COUPling AC",
        ":CHANnel1:COUPling?",
        ":CHANnel1:PROBe 10",
        ":CHANnel1:PROBe?",
        ":CHANnel1:BWLimit ON",
        ":CHANnel1:BWLimit?",
    ]


def test_channel_controller_rejects_invalid_scale_before_scpi():
    backend = FakeBackend()
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    with pytest.raises(ParameterValidationError):
        controller.set_scale(1, 0.0)

    assert backend.history == []


def test_channel_controller_rejects_invalid_channel_before_scale_offset_scpi():
    backend = FakeBackend()
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.set_scale(3, 0.5)
    with pytest.raises(ParameterValidationError):
        controller.set_offset(3, 0.0)

    assert backend.history == []


def test_channel_controller_rejects_invalid_parameter_values_before_scpi():
    backend = FakeBackend()
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    with pytest.raises(ParameterValidationError):
        controller.set_coupling(1, "gnd")
    with pytest.raises(ParameterValidationError):
        controller.set_probe_ratio(1, 0)

    assert backend.history == []
