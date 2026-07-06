import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.channel import (
    ChannelController,
    channel_bandwidth_limit_command,
    channel_bandwidth_limit_query,
    channel_coupling_command,
    channel_coupling_query,
    channel_display_command,
    channel_display_query,
    channel_impedance_command,
    channel_impedance_query,
    channel_invert_command,
    channel_invert_query,
    channel_label_command,
    channel_label_query,
    channel_offset_command,
    channel_offset_query,
    channel_probe_skew_command,
    channel_probe_skew_query,
    channel_probe_ratio_command,
    channel_probe_ratio_query,
    channel_range_command,
    channel_range_query,
    channel_scale_command,
    channel_scale_query,
    channel_units_command,
    channel_units_query,
    channel_vernier_command,
    channel_vernier_query,
    normalize_channel_coupling,
    normalize_channel_impedance,
    normalize_channel_units,
    parse_channel_bool,
    parse_channel_coupling,
    parse_channel_display,
    parse_channel_float,
    parse_channel_impedance,
    parse_channel_label,
    parse_channel_units,
    validate_analog_channel,
    validate_channel_impedance_supported,
    validate_channel_offset,
    validate_channel_label,
    validate_channel_range,
    validate_channel_scale,
    validate_probe_skew,
    validate_probe_ratio,
)
from keysight_scope_core.errors import ChannelResponseError, ParameterValidationError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient


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


def test_channel_advanced_commands_use_keysight_channel_syntax():
    assert channel_impedance_command(1, "one_meg") == ":CHANnel1:IMPedance ONEMeg"
    assert channel_impedance_command(1, "fifty") == ":CHANnel1:IMPedance FIFTy"
    assert channel_impedance_query(2) == ":CHANnel2:IMPedance?"
    assert channel_invert_command(1, True) == ":CHANnel1:INVert ON"
    assert channel_invert_command(2, False) == ":CHANnel2:INVert OFF"
    assert channel_invert_query(3) == ":CHANnel3:INVert?"
    assert channel_range_command(1, 4.0) == ":CHANnel1:RANGe 4"
    assert channel_range_query(2) == ":CHANnel2:RANGe?"
    assert channel_units_command(1, "volt") == ":CHANnel1:UNITs VOLT"
    assert channel_units_command(2, "amp") == ":CHANnel2:UNITs AMP"
    assert channel_units_query(3) == ":CHANnel3:UNITs?"
    assert channel_vernier_command(1, True) == ":CHANnel1:VERNier ON"
    assert channel_vernier_query(2) == ":CHANnel2:VERNier?"
    assert channel_probe_skew_command(1, 1e-9) == ":CHANnel1:PROBe:SKEW 1e-09"
    assert channel_probe_skew_query(2) == ":CHANnel2:PROBe:SKEW?"


def test_channel_label_commands_use_keysight_channel_syntax():
    capabilities = capabilities_for_model("DSOX4024A")

    assert channel_label_command(1, "Input a", capabilities) == ':CHANnel1:LABel "Input a"'
    assert channel_label_query(2) == ":CHANnel2:LABel?"


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


@pytest.mark.parametrize("raw, expected", [("ONEMeg", "one_meg"), ("ONEM", "one_meg"), ("FIFTy", "fifty")])
def test_parse_channel_impedance(raw, expected):
    assert parse_channel_impedance(raw) == expected


@pytest.mark.parametrize("raw", ["HIGH", "MAYBE", ""])
def test_parse_channel_impedance_rejects_unexpected_response(raw):
    with pytest.raises(ChannelResponseError):
        parse_channel_impedance(raw)


@pytest.mark.parametrize("raw, expected", [("VOLT", "volt"), ("AMP", "amp"), ("AMPere", "amp")])
def test_parse_channel_units(raw, expected):
    assert parse_channel_units(raw) == expected


@pytest.mark.parametrize("raw", ["V", "WATT", ""])
def test_parse_channel_units_rejects_unexpected_response(raw):
    with pytest.raises(ChannelResponseError):
        parse_channel_units(raw)


@pytest.mark.parametrize("raw, expected", [("5.0E-1", 0.5), (" -1.25E-1 ", -0.125)])
def test_parse_channel_float(raw, expected):
    assert parse_channel_float(raw, "scale") == expected


@pytest.mark.parametrize("raw", ["MAYBE", "NaN", "INF"])
def test_parse_channel_float_rejects_unexpected_response(raw):
    with pytest.raises(ChannelResponseError):
        parse_channel_float(raw, "scale")


def test_parse_channel_label_accepts_quoted_or_plain_response():
    assert parse_channel_label('"Input a"') == "Input a"
    assert parse_channel_label("Input a") == "Input a"


def test_validate_analog_channel_uses_capability_channel_count():
    capabilities = capabilities_for_model("DSOX4022A")

    assert validate_analog_channel(2, capabilities) == 2
    with pytest.raises(ParameterValidationError):
        validate_analog_channel(3, capabilities)


def test_validate_channel_label_enforces_model_length_and_ascii():
    assert validate_channel_label("lower ok", capabilities_for_model("DSOX3024A")) == "lower ok"
    with pytest.raises(ParameterValidationError):
        validate_channel_label("12345678901", capabilities_for_model("DSOX3024A"))
    assert validate_channel_label("x" * 32, capabilities_for_model("DSOX4024A")) == "x" * 32
    with pytest.raises(ParameterValidationError):
        validate_channel_label('bad"quote', capabilities_for_model("DSOX4024A"))
    with pytest.raises(ParameterValidationError):
        validate_channel_label("bad\nline", capabilities_for_model("DSOX4024A"))
    with pytest.raises(ParameterValidationError):
        validate_channel_label("non-ascii-\u00e9", capabilities_for_model("DSOX4024A"))


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


@pytest.mark.parametrize("value, expected", [("one-meg", "one_meg"), (" one_meg ", "one_meg"), ("50", "fifty"), ("fifty", "fifty")])
def test_normalize_channel_impedance_accepts_supported_values(value, expected):
    assert normalize_channel_impedance(value) == expected


@pytest.mark.parametrize("value", ["high", "", None])
def test_normalize_channel_impedance_rejects_unsupported_values(value):
    with pytest.raises(ParameterValidationError):
        normalize_channel_impedance(value)


@pytest.mark.parametrize("value, expected", [("volt", "volt"), ("V", "volt"), ("amp", "amp"), ("A", "amp")])
def test_normalize_channel_units_accepts_supported_values(value, expected):
    assert normalize_channel_units(value) == expected


@pytest.mark.parametrize("value", ["watt", "", None])
def test_normalize_channel_units_rejects_unsupported_values(value):
    with pytest.raises(ParameterValidationError):
        normalize_channel_units(value)


@pytest.mark.parametrize("value", [1.0, 10, "100"])
def test_validate_probe_ratio_accepts_positive_finite_values(value):
    assert validate_probe_ratio(value) == float(value)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan"), "abc"])
def test_validate_probe_ratio_rejects_non_positive_or_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_probe_ratio(value)


@pytest.mark.parametrize("value", [1.0, "0.001"])
def test_validate_channel_range_accepts_positive_finite_values(value):
    assert validate_channel_range(value) == float(value)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan"), "abc"])
def test_validate_channel_range_rejects_non_positive_or_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_channel_range(value)


@pytest.mark.parametrize("value", [-100e-9, 0.0, 100e-9, "1e-9"])
def test_validate_probe_skew_accepts_finite_values_in_range(value):
    assert validate_probe_skew(value) == float(value)


@pytest.mark.parametrize("value", [-101e-9, 101e-9, float("inf"), float("nan"), "abc"])
def test_validate_probe_skew_rejects_out_of_range_or_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_probe_skew(value)


def test_validate_channel_impedance_supported_rejects_2000x_fifty():
    with pytest.raises(ParameterValidationError, match="DSO-X 2000X only supports one-meg"):
        validate_channel_impedance_supported("fifty", capabilities_for_model("DSOX2004A"))

    validate_channel_impedance_supported("one_meg", capabilities_for_model("DSOX2004A"))
    validate_channel_impedance_supported("fifty", capabilities_for_model("DSOX3024A"))


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


def test_channel_controller_sets_advanced_settings_and_reads_back_values():
    backend = FakeBackend(
        responses={
            ":CHANnel1:IMPedance?": "FIFTy",
            ":CHANnel1:INVert?": "1",
            ":CHANnel1:RANGe?": "4.0",
            ":CHANnel1:UNITs?": "AMP",
            ":CHANnel1:VERNier?": "0",
            ":CHANnel1:PROBe:SKEW?": "1.0E-9",
        }
    )
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_impedance(1, "fifty")
    impedance = controller.query_impedance(1)
    controller.set_invert(1, True)
    invert = controller.query_invert(1)
    controller.set_range(1, 4.0)
    channel_range = controller.query_range(1)
    controller.set_units(1, "amp")
    units = controller.query_units(1)
    controller.set_vernier(1, False)
    vernier = controller.query_vernier(1)
    controller.set_probe_skew(1, 1e-9)
    skew = controller.query_probe_skew(1)

    assert impedance == "fifty"
    assert invert is True
    assert channel_range == 4.0
    assert units == "amp"
    assert vernier is False
    assert skew == 1e-9
    assert backend.history == [
        ":CHANnel1:IMPedance FIFTy",
        ":CHANnel1:IMPedance?",
        ":CHANnel1:INVert ON",
        ":CHANnel1:INVert?",
        ":CHANnel1:RANGe 4",
        ":CHANnel1:RANGe?",
        ":CHANnel1:UNITs AMP",
        ":CHANnel1:UNITs?",
        ":CHANnel1:VERNier OFF",
        ":CHANnel1:VERNier?",
        ":CHANnel1:PROBe:SKEW 1e-09",
        ":CHANnel1:PROBe:SKEW?",
    ]


def test_channel_controller_sets_label_and_reads_back_text():
    backend = FakeBackend(responses={":CHANnel1:LABel?": '"Input a"'})
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_label(1, "Input a")
    label = controller.query_label(1)

    assert label == "Input a"
    assert backend.history == [':CHANnel1:LABel "Input a"', ":CHANnel1:LABel?"]


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
    with pytest.raises(ParameterValidationError):
        controller.set_impedance(1, "high")
    with pytest.raises(ParameterValidationError):
        controller.set_range(1, 0)
    with pytest.raises(ParameterValidationError):
        controller.set_units(1, "watt")
    with pytest.raises(ParameterValidationError):
        controller.set_probe_skew(1, 101e-9)

    assert backend.history == []
