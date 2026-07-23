import pytest

from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.trigger import (
    PatternTriggerController,
    parse_pattern_format_readback,
    parse_pattern_qualifier_readback,
    parse_pattern_trigger_response,
    pattern_trigger_configure_commands,
    pattern_trigger_query_commands,
    trigger_mode_pattern_command,
    validate_pattern_trigger_pattern,
)


def test_pattern_trigger_configure_sequence():
    commands = pattern_trigger_configure_commands(
        pattern="xxx1",
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE PATTern",
        ":TRIGger:PATTern:FORMat ASCii",
        ':TRIGger:PATTern "XXX1"',
        ":TRIGger:PATTern:QUALifier ENTered",
    ]


@pytest.mark.parametrize(
    "pattern",
    ["", "XX,X", 'XX"X', "XXXR", "XXXF", "0x01", "XXY1", "XX 1", "XXX10"],
)
def test_pattern_trigger_rejects_invalid_patterns(pattern):
    with pytest.raises(ParameterValidationError):
        pattern_trigger_configure_commands(
            pattern=pattern,
            capabilities=capabilities_for_model("DSOX4024A"),
        )


def test_pattern_trigger_accepts_lowercase_for_registered_model():
    assert (
        validate_pattern_trigger_pattern("xxx1", capabilities_for_model("DSOX4024A"))
        == "XXX1"
    )


def test_pattern_trigger_rejects_wrong_length_for_model():
    with pytest.raises(ParameterValidationError):
        validate_pattern_trigger_pattern("XXXX1", capabilities_for_model("DSOX4024A"))


def test_pattern_trigger_query_sequence_is_explicit_and_non_acquisition():
    assert trigger_mode_pattern_command() == ":TRIGger:MODE PATTern"
    assert pattern_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:PATTern:FORMat?",
        ":TRIGger:PATTern?",
        ":TRIGger:PATTern:QUALifier?",
    ]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"XXX1",NONE,POS', ("XXX1", "NONE", "POS")),
        ("XXX1,NONE,POS", ("XXX1", "NONE", "POS")),
        ('"XX,X",CHANnel1,NEG', ("XX,X", "CHANnel1", "NEG")),
        ("XXX1", ("XXX1", None, None)),
    ],
)
def test_parse_pattern_trigger_response(raw, expected):
    assert parse_pattern_trigger_response(raw) == expected


@pytest.mark.parametrize("raw", ["ASC", "ASCii"])
def test_parse_pattern_format_ascii_readbacks(raw):
    assert parse_pattern_format_readback(raw) == "ascii"


def test_parse_pattern_format_hex_readback_is_preserved():
    assert parse_pattern_format_readback("HEX") == "hex"


@pytest.mark.parametrize("raw", ["ENT", "ENTered"])
def test_parse_pattern_qualifier_entered_readbacks(raw):
    assert parse_pattern_qualifier_readback(raw) == "entered"


def test_pattern_trigger_controller_configures_and_queries_raw_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "PATT",
            ":TRIGger:PATTern:FORMat?": "ASC",
            ":TRIGger:PATTern?": '"XXX1",NONE,POS',
            ":TRIGger:PATTern:QUALifier?": "ENT",
        }
    )
    controller = PatternTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    configured = controller.configure("xxx1")
    queried = controller.query()

    assert configured.pattern == "XXX1"
    assert queried.to_json() == {
        "mode": "pattern",
        "format": "ascii",
        "pattern": "XXX1",
        "qualifier": "entered",
        "edge_source_raw": "NONE",
        "edge_raw": "POS",
        "raw_pattern_response": '"XXX1",NONE,POS',
        "raw": queried.raw,
    }
    assert backend.history == [
        ":TRIGger:MODE PATTern",
        ":TRIGger:PATTern:FORMat ASCii",
        ':TRIGger:PATTern "XXX1"',
        ":TRIGger:PATTern:QUALifier ENTered",
        ":TRIGger:MODE?",
        ":TRIGger:PATTern:FORMat?",
        ":TRIGger:PATTern?",
        ":TRIGger:PATTern:QUALifier?",
    ]


def test_pattern_trigger_query_preserves_unexpected_readbacks():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "ODD",
            ":TRIGger:PATTern:FORMat?": "BINARY",
            ":TRIGger:PATTern?": '"1010",CHANnel1,WEIRD',
            ":TRIGger:PATTern:QUALifier?": "OTHER",
        }
    )
    controller = PatternTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.mode is None
    assert state.format is None
    assert state.pattern == "1010"
    assert state.qualifier is None
    assert state.edge_source_raw == "CHANnel1"
    assert state.edge_raw == "WEIRD"
    assert state.raw == {
        "mode": "ODD",
        "format": "BINARY",
        "pattern": '"1010",CHANnel1,WEIRD',
        "qualifier": "OTHER",
    }
