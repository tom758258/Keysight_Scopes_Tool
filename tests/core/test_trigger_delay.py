import math

import pytest

from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError, TriggerResponseError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.trigger import (
    DelayTriggerController,
    delay_trigger_configure_commands,
    delay_trigger_query_commands,
    normalize_delay_slope,
    parse_delay_count_readback,
    parse_delay_slope_readback,
    parse_delay_source,
    parse_trigger_mode,
    validate_delay_trigger_count,
    validate_delay_trigger_time,
)


def test_delay_trigger_configure_sequence():
    commands = delay_trigger_configure_commands(
        arm_channel=1,
        arm_slope="positive",
        trigger_channel=2,
        trigger_slope="negative",
        time_seconds=1e-6,
        count=2,
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE DELay",
        ":TRIGger:DELay:ARM:SOURce CHANnel1",
        ":TRIGger:DELay:ARM:SLOPe POSitive",
        ":TRIGger:DELay:TDELay:TIME 1e-06",
        ":TRIGger:DELay:TRIGger:COUNt 2",
        ":TRIGger:DELay:TRIGger:SOURce CHANnel2",
        ":TRIGger:DELay:TRIGger:SLOPe NEGative",
    ]


def test_delay_trigger_query_sequence_is_explicit():
    assert delay_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:DELay:ARM:SOURce?",
        ":TRIGger:DELay:ARM:SLOPe?",
        ":TRIGger:DELay:TDELay:TIME?",
        ":TRIGger:DELay:TRIGger:COUNt?",
        ":TRIGger:DELay:TRIGger:SOURce?",
        ":TRIGger:DELay:TRIGger:SLOPe?",
    ]


@pytest.mark.parametrize("value", [0, 3e-9, 10.000000001, math.nan, math.inf])
def test_delay_trigger_time_rejects_invalid_values(value):
    with pytest.raises(ParameterValidationError):
        validate_delay_trigger_time(value)


@pytest.mark.parametrize("value", [4e-9, 10.0])
def test_delay_trigger_time_accepts_boundaries(value):
    assert validate_delay_trigger_time(value) == value


@pytest.mark.parametrize("value", [0, -1, 1.5, "2", True])
def test_delay_trigger_count_rejects_invalid_values(value):
    with pytest.raises(ParameterValidationError):
        validate_delay_trigger_count(value)


def test_delay_trigger_count_accepts_one():
    assert validate_delay_trigger_count(1) == 1


def test_delay_trigger_rejects_invalid_channel_before_scpi():
    backend = FakeBackend()
    controller = DelayTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4022A"),
    )

    with pytest.raises(ParameterValidationError):
        controller.configure(
            arm_channel=1,
            arm_slope="positive",
            trigger_channel=3,
            trigger_slope="negative",
            time_seconds=1e-6,
            count=2,
        )

    assert backend.history == []


@pytest.mark.parametrize("value", ["positive", "negative"])
def test_normalize_delay_slope_accepts_public_values(value):
    assert normalize_delay_slope(value) in {"POSitive", "NEGative"}


@pytest.mark.parametrize(
    "value",
    ["pos", "neg", "rising", "falling", "either", "alternate", ""],
)
def test_normalize_delay_slope_rejects_aliases(value):
    with pytest.raises(ParameterValidationError):
        normalize_delay_slope(value)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CHAN1", ("channel", 1, None)),
        ("CHANnel2", ("channel", 2, None)),
        ("CHANNEL4", ("channel", 4, None)),
        ("DIG0", ("digital", None, 0)),
        ("DIGital7", ("digital", None, 7)),
        ("EXTernal", (None, None, None)),
        ("NONE", (None, None, None)),
        ("", (None, None, None)),
    ],
)
def test_parse_delay_source_tolerates_raw_states(raw, expected):
    assert parse_delay_source(raw) == expected


@pytest.mark.parametrize("raw", ["POS", "POSitive", "NEG", "NEGative"])
def test_parse_delay_slope_readbacks(raw):
    assert parse_delay_slope_readback(raw) in {"positive", "negative"}


def test_parse_delay_count_readback():
    assert parse_delay_count_readback("2") == 2
    assert parse_delay_count_readback("") is None
    with pytest.raises(TriggerResponseError):
        parse_delay_count_readback("2.5")


def test_parse_trigger_mode_supports_delay():
    assert parse_trigger_mode("DEL") == "delay"
    assert parse_trigger_mode("DELay") == "delay"


def test_delay_trigger_controller_configures_and_queries_analog_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "DEL",
            ":TRIGger:DELay:ARM:SOURce?": "CHAN1",
            ":TRIGger:DELay:ARM:SLOPe?": "POS",
            ":TRIGger:DELay:TDELay:TIME?": "+1.00000000E-06",
            ":TRIGger:DELay:TRIGger:COUNt?": "2",
            ":TRIGger:DELay:TRIGger:SOURce?": "CHAN2",
            ":TRIGger:DELay:TRIGger:SLOPe?": "NEG",
        }
    )
    controller = DelayTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    controller.configure(
        arm_channel=1,
        arm_slope="positive",
        trigger_channel=2,
        trigger_slope="negative",
        time_seconds=1e-6,
        count=2,
    )
    state = controller.query()

    assert state.to_json() == {
        "mode": "delay",
        "arm_source": "CHAN1",
        "arm_source_kind": "channel",
        "arm_channel": 1,
        "arm_digital": None,
        "arm_slope": "positive",
        "trigger_source": "CHAN2",
        "trigger_source_kind": "channel",
        "trigger_channel": 2,
        "trigger_digital": None,
        "trigger_slope": "negative",
        "time_seconds": 1e-6,
        "count": 2,
        "raw": state.raw,
    }
    assert backend.history == [
        ":TRIGger:MODE DELay",
        ":TRIGger:DELay:ARM:SOURce CHANnel1",
        ":TRIGger:DELay:ARM:SLOPe POSitive",
        ":TRIGger:DELay:TDELay:TIME 1e-06",
        ":TRIGger:DELay:TRIGger:COUNt 2",
        ":TRIGger:DELay:TRIGger:SOURce CHANnel2",
        ":TRIGger:DELay:TRIGger:SLOPe NEGative",
        *delay_trigger_query_commands(),
    ]


def test_delay_trigger_query_tolerates_digital_and_raw_sources():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "DELay",
            ":TRIGger:DELay:ARM:SOURce?": "DIGital7",
            ":TRIGger:DELay:ARM:SLOPe?": "POS",
            ":TRIGger:DELay:TDELay:TIME?": "+4.00000000E-09",
            ":TRIGger:DELay:TRIGger:COUNt?": "1",
            ":TRIGger:DELay:TRIGger:SOURce?": "EXTernal",
            ":TRIGger:DELay:TRIGger:SLOPe?": "NEG",
        }
    )
    controller = DelayTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.arm_source == "DIGital7"
    assert state.arm_source_kind == "digital"
    assert state.arm_channel is None
    assert state.arm_digital == 7
    assert state.trigger_source == "EXTernal"
    assert state.trigger_source_kind is None
    assert state.trigger_channel is None
    assert state.trigger_digital is None
    assert backend.history == delay_trigger_query_commands()
