import pytest

from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.trigger import (
    TransitionTriggerController,
    normalize_transition_qualifier,
    normalize_transition_slope,
    parse_transition_qualifier_readback,
    parse_transition_slope_readback,
    parse_transition_source,
    transition_trigger_configure_commands,
    transition_trigger_query_commands,
    trigger_mode_transition_command,
)


def test_transition_trigger_greater_than_sequence():
    commands = transition_trigger_configure_commands(
        channel=1,
        slope="positive",
        qualifier="greater-than",
        time_seconds=5e-6,
        low_level_volts=-0.5,
        high_level_volts=0.5,
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE TRANsition",
        ":TRIGger:TRANsition:SOURce CHANnel1",
        ":TRIGger:LEVel:LOW -0.5,CHANnel1",
        ":TRIGger:LEVel:HIGH 0.5,CHANnel1",
        ":TRIGger:TRANsition:SLOPe POSitive",
        ":TRIGger:TRANsition:TIME 5e-06",
        ":TRIGger:TRANsition:QUALifier GREaterthan",
    ]


def test_transition_trigger_less_than_sequence():
    commands = transition_trigger_configure_commands(
        channel=1,
        slope="negative",
        qualifier="less-than",
        time_seconds=2e-6,
        low_level_volts=-0.25,
        high_level_volts=0.75,
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE TRANsition",
        ":TRIGger:TRANsition:SOURce CHANnel1",
        ":TRIGger:LEVel:LOW -0.25,CHANnel1",
        ":TRIGger:LEVel:HIGH 0.75,CHANnel1",
        ":TRIGger:TRANsition:SLOPe NEGative",
        ":TRIGger:TRANsition:TIME 2e-06",
        ":TRIGger:TRANsition:QUALifier LESSthan",
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_seconds": 0},
        {"time_seconds": float("nan")},
        {"low_level_volts": 0.5, "high_level_volts": 0.5},
        {"low_level_volts": 0.75, "high_level_volts": 0.5},
        {"slope": "either"},
        {"qualifier": "greater_than"},
    ],
)
def test_transition_trigger_rejects_invalid_values(kwargs):
    values = {
        "channel": 1,
        "slope": "positive",
        "qualifier": "greater-than",
        "time_seconds": 5e-6,
        "low_level_volts": -0.5,
        "high_level_volts": 0.5,
        "capabilities": capabilities_for_model("DSOX4024A"),
    }
    values.update(kwargs)

    with pytest.raises(ParameterValidationError):
        transition_trigger_configure_commands(**values)


def test_transition_trigger_rejects_invalid_channel_before_scpi():
    backend = FakeBackend()
    controller = TransitionTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    with pytest.raises(ParameterValidationError):
        controller.configure(
            channel=5,
            slope="positive",
            qualifier="greater-than",
            time_seconds=5e-6,
            low_level_volts=-0.5,
            high_level_volts=0.5,
        )

    assert backend.history == []


@pytest.mark.parametrize("value", ["positive", "negative"])
def test_normalize_transition_slope_accepts_public_values(value):
    assert normalize_transition_slope(value) in {"POSitive", "NEGative"}


@pytest.mark.parametrize("value", ["greater-than", "less-than"])
def test_normalize_transition_qualifier_accepts_public_values(value):
    assert normalize_transition_qualifier(value) in {"GREaterthan", "LESSthan"}


@pytest.mark.parametrize("value", ["pos", "neg", "either", "rising", ""])
def test_normalize_transition_slope_rejects_aliases(value):
    with pytest.raises(ParameterValidationError):
        normalize_transition_slope(value)


@pytest.mark.parametrize("value", ["greater_than", "less_than", "none", ""])
def test_normalize_transition_qualifier_rejects_aliases(value):
    with pytest.raises(ParameterValidationError):
        normalize_transition_qualifier(value)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CHAN1", ("channel", 1)),
        ("CHANnel2", ("channel", 2)),
        ("CHANNEL4", ("channel", 4)),
        ("DIGital7", (None, None)),
        ("EXTernal", (None, None)),
        ("", (None, None)),
    ],
)
def test_parse_transition_source_preserves_only_safe_analog_channels(raw, expected):
    assert parse_transition_source(raw) == expected


@pytest.mark.parametrize("raw", ["POS", "POSitive", "NEG", "NEGative"])
def test_parse_transition_slope_readbacks(raw):
    assert parse_transition_slope_readback(raw) in {"positive", "negative"}


@pytest.mark.parametrize("raw", ["GRE", "GREaterthan", "LESS", "LESSthan"])
def test_parse_transition_qualifier_readbacks(raw):
    assert parse_transition_qualifier_readback(raw) in {"greater-than", "less-than"}


def test_transition_trigger_query_sequence_is_explicit_and_non_acquisition():
    assert trigger_mode_transition_command() == ":TRIGger:MODE TRANsition"
    assert transition_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:TRANsition:SOURce?",
        ":TRIGger:TRANsition:SLOPe?",
        ":TRIGger:TRANsition:QUALifier?",
        ":TRIGger:TRANsition:TIME?",
    ]


def test_transition_trigger_controller_configures_and_queries_analog_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "TRAN",
            ":TRIGger:TRANsition:SOURce?": "CHAN1",
            ":TRIGger:TRANsition:SLOPe?": "POS",
            ":TRIGger:TRANsition:QUALifier?": "GRE",
            ":TRIGger:TRANsition:TIME?": "+5.00000000E-06",
            ":TRIGger:LEVel:LOW? CHANnel1": "-5.00000000E-01",
            ":TRIGger:LEVel:HIGH? CHANnel1": "+5.00000000E-01",
        }
    )
    controller = TransitionTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    controller.configure(
        channel=1,
        slope="positive",
        qualifier="greater-than",
        time_seconds=5e-6,
        low_level_volts=-0.5,
        high_level_volts=0.5,
    )
    state = controller.query()

    assert state.to_json() == {
        "mode": "transition",
        "source": "CHAN1",
        "source_kind": "channel",
        "channel": 1,
        "slope": "positive",
        "qualifier": "greater-than",
        "time_seconds": 5e-6,
        "low_level_volts": -0.5,
        "high_level_volts": 0.5,
        "raw": state.raw,
    }
    assert backend.history == [
        ":TRIGger:MODE TRANsition",
        ":TRIGger:TRANsition:SOURce CHANnel1",
        ":TRIGger:LEVel:LOW -0.5,CHANnel1",
        ":TRIGger:LEVel:HIGH 0.5,CHANnel1",
        ":TRIGger:TRANsition:SLOPe POSitive",
        ":TRIGger:TRANsition:TIME 5e-06",
        ":TRIGger:TRANsition:QUALifier GREaterthan",
        ":TRIGger:MODE?",
        ":TRIGger:TRANsition:SOURce?",
        ":TRIGger:TRANsition:SLOPe?",
        ":TRIGger:TRANsition:QUALifier?",
        ":TRIGger:TRANsition:TIME?",
        ":TRIGger:LEVel:LOW? CHANnel1",
        ":TRIGger:LEVel:HIGH? CHANnel1",
    ]


def test_transition_trigger_query_skips_levels_for_unsafe_source():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "TRAN",
            ":TRIGger:TRANsition:SOURce?": "DIGital7",
            ":TRIGger:TRANsition:SLOPe?": "NEG",
            ":TRIGger:TRANsition:QUALifier?": "LESS",
            ":TRIGger:TRANsition:TIME?": "+2.00000000E-06",
        }
    )
    controller = TransitionTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.source == "DIGital7"
    assert state.source_kind is None
    assert state.channel is None
    assert state.low_level_volts is None
    assert state.high_level_volts is None
    assert backend.history == transition_trigger_query_commands()
