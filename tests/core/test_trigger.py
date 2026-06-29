import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import ParameterValidationError, TriggerResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.trigger import (
    EdgeTriggerController,
    edge_trigger_level_command,
    edge_trigger_level_query,
    edge_trigger_slope_command,
    edge_trigger_slope_query,
    edge_trigger_source_command,
    force_trigger_command,
    edge_trigger_source_query,
    normalize_edge_slope,
    parse_edge_slope,
    parse_edge_trigger_source,
    parse_trigger_float,
    trigger_mode_edge_command,
    validate_trigger_level,
)

def test_edge_trigger_commands_use_keysight_syntax():
    assert trigger_mode_edge_command() == ":TRIGger:MODE EDGE"
    assert edge_trigger_source_command(1) == ":TRIGger:EDGE:SOURce CHANnel1"
    assert edge_trigger_source_query() == ":TRIGger:EDGE:SOURce?"
    assert edge_trigger_level_command(0.25) == ":TRIGger:EDGE:LEVel 0.25"
    assert edge_trigger_level_query() == ":TRIGger:EDGE:LEVel?"
    assert edge_trigger_slope_command("POSitive") == ":TRIGger:EDGE:SLOPe POSitive"
    assert edge_trigger_slope_query() == ":TRIGger:EDGE:SLOPe?"

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CHAN1", 1),
        ("CHANnel2", 2),
        (" channel4 ", 4),
    ],
)


def test_parse_edge_trigger_source(raw, expected):
    assert parse_edge_trigger_source(raw) == expected

@pytest.mark.parametrize("raw", ["NONE", "EXT", "CHANX", "CHAN0"])


def test_parse_edge_trigger_source_rejects_non_analog_channel(raw):
    with pytest.raises(TriggerResponseError):
        parse_edge_trigger_source(raw)

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("POS", "positive"),
        ("POSitive", "positive"),
        ("NEG", "negative"),
        ("EITH", "either"),
        ("ALT", "alternate"),
    ],
)


def test_parse_edge_slope(raw, expected):
    assert parse_edge_slope(raw) == expected

def test_parse_edge_slope_rejects_unexpected_response():
    with pytest.raises(TriggerResponseError):
        parse_edge_slope("MAYBE")

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("positive", "POSitive"),
        ("rising", "POSitive"),
        ("negative", "NEGative"),
        ("falling", "NEGative"),
        ("either", "EITHer"),
        ("alternate", "ALTernate"),
    ],
)


def test_normalize_edge_slope(raw, expected):
    assert normalize_edge_slope(raw) == expected

def test_normalize_edge_slope_rejects_unknown_slope():
    with pytest.raises(ParameterValidationError):
        normalize_edge_slope("sideways")

@pytest.mark.parametrize("raw, expected", [("2.5E-1", 0.25), (" -1.0 ", -1.0)])


def test_parse_trigger_float(raw, expected):
    assert parse_trigger_float(raw, "level") == expected

@pytest.mark.parametrize("raw", ["MAYBE", "NaN", "INF"])


def test_parse_trigger_float_rejects_unexpected_response(raw):
    with pytest.raises(TriggerResponseError):
        parse_trigger_float(raw, "level")

@pytest.mark.parametrize("value", [0.0, -1.0, "0.25"])


def test_validate_trigger_level_accepts_finite_values(value):
    assert validate_trigger_level(value) == float(value)

@pytest.mark.parametrize("value", [float("inf"), float("nan"), "abc"])


def test_validate_trigger_level_rejects_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_trigger_level(value)

def test_edge_trigger_controller_configures_and_reads_back_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:EDGE:SOURce?": "CHAN1",
            ":TRIGger:EDGE:LEVel?": "2.5E-1",
            ":TRIGger:EDGE:SLOPe?": "POS",
        }
    )
    controller = EdgeTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.configure(source_channel=1, level_volts=0.25, slope="positive")
    state = controller.query()

    assert state.source_channel == 1
    assert state.level_volts == 0.25
    assert state.slope == "positive"
    assert backend.history == [
        ":TRIGger:MODE EDGE",
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel 0.25",
        ":TRIGger:EDGE:SLOPe POSitive",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:SLOPe?",
    ]

def test_edge_trigger_controller_rejects_invalid_channel_before_scpi():
    backend = FakeBackend()
    controller = EdgeTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.configure(source_channel=3, level_volts=0.0, slope="positive")

    assert backend.history == []


def test_force_trigger_command_returns_expected_scpi():
    assert force_trigger_command() == ":TRIGger:FORCe"


def test_force_trigger_command_writes_only_force_trigger_scpi():
    backend = FakeBackend()
    client = SCPIClient(backend)

    client.write(force_trigger_command())

    assert backend.history == [":TRIGger:FORCe"]
