import pytest

from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.trigger import (
    OrTriggerController,
    or_trigger_configure_commands,
    or_trigger_query_commands,
    parse_or_trigger_pattern_response,
    trigger_mode_or_command,
    validate_or_trigger_pattern,
)


def test_or_trigger_configure_sequence():
    commands = or_trigger_configure_commands(
        pattern="xxxr",
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE OR",
        ':TRIGger:OR "XXXR"',
    ]


@pytest.mark.parametrize(
    "pattern",
    ["", "XX,R", 'XX"R', "XXX1", "XXX0", "0x01", "XXYR", "XX R", "XXX10"],
)
def test_or_trigger_rejects_invalid_patterns_before_backend_access(pattern):
    backend = FakeBackend()
    controller = OrTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    with pytest.raises(ParameterValidationError):
        controller.configure(pattern)

    assert backend.history == []


def test_or_trigger_accepts_lowercase_for_registered_model():
    assert (
        validate_or_trigger_pattern("xxxr", capabilities_for_model("DSOX4024A"))
        == "XXXR"
    )


def test_or_trigger_four_channel_profile_rejects_two_char_pattern():
    with pytest.raises(ParameterValidationError):
        validate_or_trigger_pattern("XR", capabilities_for_model("DSOX4024A"))


def test_or_trigger_four_channel_profile_rejects_five_char_pattern():
    with pytest.raises(ParameterValidationError):
        validate_or_trigger_pattern("XXXXR", capabilities_for_model("DSOX4024A"))


def test_or_trigger_query_sequence_is_explicit_and_non_acquisition():
    assert trigger_mode_or_command() == ":TRIGger:MODE OR"
    assert or_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:OR?",
    ]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"XXXR"', "XXXR"),
        ("XXXR", "XXXR"),
        ('"xxfr"', "XXFR"),
        ("BAD1", None),
    ],
)
def test_parse_or_trigger_pattern_response(raw, expected):
    assert parse_or_trigger_pattern_response(raw) == expected


def test_or_trigger_controller_configures_and_queries_raw_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "OR",
            ":TRIGger:OR?": '"XXXR"',
        }
    )
    controller = OrTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    configured = controller.configure("xxxr")
    queried = controller.query()

    assert configured.pattern == "XXXR"
    assert queried.to_json() == {
        "mode": "or",
        "raw_mode": "OR",
        "pattern": "XXXR",
        "raw_pattern": '"XXXR"',
        "raw": queried.raw,
    }
    assert backend.history == [
        ":TRIGger:MODE OR",
        ':TRIGger:OR "XXXR"',
        ":TRIGger:MODE?",
        ":TRIGger:OR?",
    ]


def test_or_trigger_query_preserves_unexpected_readbacks():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "EDGE",
            ":TRIGger:OR?": '"BAD1"',
        }
    )
    controller = OrTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.mode == "edge"
    assert state.raw_mode == "EDGE"
    assert state.pattern is None
    assert state.raw_pattern == '"BAD1"'
