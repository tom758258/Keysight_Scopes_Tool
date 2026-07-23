import math

import pytest

from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError, TriggerResponseError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.trigger import (
    EdgeBurstTriggerController,
    edge_burst_trigger_configure_commands,
    edge_burst_trigger_query_commands,
    parse_edge_burst_count_readback,
    parse_edge_burst_slope_readback,
    parse_edge_burst_source,
    parse_trigger_mode,
    validate_edge_burst_count,
    validate_edge_burst_idle_time,
    validate_trigger_level,
)


def test_edge_burst_trigger_configure_sequence_without_level():
    commands = edge_burst_trigger_configure_commands(
        source_channel=1,
        slope="positive",
        count=3,
        idle_time=1e-6,
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE EBURst",
        ":TRIGger:EBURst:SOURce CHANnel1",
        ":TRIGger:EBURst:SLOPe POSitive",
        ":TRIGger:EBURst:COUNt 3",
        ":TRIGger:EBURst:IDLE 1e-06",
    ]


def test_edge_burst_trigger_configure_sequence_with_level():
    commands = edge_burst_trigger_configure_commands(
        source_channel=1,
        slope="negative",
        count=5,
        idle_time=1e-5,
        capabilities=capabilities_for_model("DSOX4024A"),
        level_volts=0.5,
    )

    assert commands == [
        ":TRIGger:MODE EBURst",
        ":TRIGger:EBURst:SOURce CHANnel1",
        ":TRIGger:EBURst:SLOPe NEGative",
        ":TRIGger:EBURst:COUNt 5",
        ":TRIGger:EBURst:IDLE 1e-05",
        ":TRIGger:EDGE:LEVel 0.5, CHANnel1",
    ]


def test_edge_burst_trigger_query_sequence_is_explicit():
    assert edge_burst_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:EBURst:SOURce?",
        ":TRIGger:EBURst:SLOPe?",
        ":TRIGger:EBURst:COUNt?",
        ":TRIGger:EBURst:IDLE?",
    ]


def test_edge_burst_trigger_controller_configures_and_queries_analog_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "EBURst",
            ":TRIGger:EBURst:SOURce?": "CHAN1",
            ":TRIGger:EBURst:SLOPe?": "POS",
            ":TRIGger:EBURst:COUNt?": "3",
            ":TRIGger:EBURst:IDLE?": "+1.00000000E-06",
            ":TRIGger:EDGE:LEVel? CHANnel1": "+5.00000000E-01",
        }
    )
    controller = EdgeBurstTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    controller.configure(
        source_channel=1,
        slope="positive",
        count=3,
        idle_time=1e-6,
        level_volts=0.5,
    )
    state = controller.query()

    assert state.to_json() == {
        "mode": "edge-burst",
        "source_channel": 1,
        "slope": "positive",
        "count": 3,
        "idle_time": 1e-6,
        "level_volts": 0.5,
        "raw_mode": "EBURst",
        "raw_source": "CHAN1",
        "raw_slope": "POS",
        "raw_count": "3",
        "raw_idle_time": "+1.00000000E-06",
        "raw_level": "+5.00000000E-01",
    }
    assert backend.history == [
        ":TRIGger:MODE EBURst",
        ":TRIGger:EBURst:SOURce CHANnel1",
        ":TRIGger:EBURst:SLOPe POSitive",
        ":TRIGger:EBURst:COUNt 3",
        ":TRIGger:EBURst:IDLE 1e-06",
        ":TRIGger:EDGE:LEVel 0.5, CHANnel1",
        *edge_burst_trigger_query_commands(),
        ":TRIGger:EDGE:LEVel? CHANnel1",
    ]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CHAN1", ("channel", 1, None)),
        ("CHANnel2", ("channel", 2, None)),
        ("CHANNEL4", ("channel", 4, None)),
        ("DIG0", ("digital", None, 0)),
        ("DIGital7", ("digital", None, 7)),
        ("NONE", ("none", None, None)),
        ("BUS1", (None, None, None)),
    ],
)
def test_parse_edge_burst_source_tolerates_raw_states(raw, expected):
    assert parse_edge_burst_source(raw) == expected


@pytest.mark.parametrize("raw", ["POS", "POSitive", "NEG", "NEGative"])
def test_parse_edge_burst_slope_readbacks(raw):
    assert parse_edge_burst_slope_readback(raw) in {"positive", "negative"}


def test_parse_edge_burst_count_readback():
    assert parse_edge_burst_count_readback("3") == 3
    with pytest.raises(TriggerResponseError):
        parse_edge_burst_count_readback("3.5")


def test_parse_trigger_mode_supports_edge_burst():
    assert parse_trigger_mode("EBUR") == "edge-burst"
    assert parse_trigger_mode("EBURst") == "edge-burst"


@pytest.mark.parametrize("source", ["DIG0", "NONE", "BUS1"])
def test_edge_burst_query_tolerates_non_analog_source_without_level_query(source):
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "EBUR",
            ":TRIGger:EBURst:SOURce?": source,
            ":TRIGger:EBURst:SLOPe?": "NEG",
            ":TRIGger:EBURst:COUNt?": "5",
            ":TRIGger:EBURst:IDLE?": "+1.00000000E-05",
        }
    )
    controller = EdgeBurstTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.source_channel is None
    assert state.level_volts is None
    assert state.raw_source == source
    assert state.raw_level is None
    assert backend.history == edge_burst_trigger_query_commands()


@pytest.mark.parametrize("channel", [0, 3, 1.5, "DIG0"])
def test_edge_burst_validation_rejects_invalid_source_channel(channel):
    with pytest.raises(ParameterValidationError):
        edge_burst_trigger_configure_commands(
            source_channel=channel,
            slope="positive",
            count=3,
            idle_time=1e-6,
            capabilities=capabilities_for_model("DSOX4022A"),
        )


@pytest.mark.parametrize("slope", ["pos", "rising", "either", ""])
def test_edge_burst_validation_rejects_invalid_slope(slope):
    with pytest.raises(ParameterValidationError):
        edge_burst_trigger_configure_commands(
            source_channel=1,
            slope=slope,
            count=3,
            idle_time=1e-6,
            capabilities=capabilities_for_model("DSOX4024A"),
        )


@pytest.mark.parametrize("count", [0, -1, 1.5, "3", True])
def test_edge_burst_count_rejects_invalid_values(count):
    with pytest.raises(ParameterValidationError):
        validate_edge_burst_count(count)


@pytest.mark.parametrize("value", [0, 9e-9, 10.000000001, math.nan, math.inf, "abc"])
def test_edge_burst_idle_time_rejects_invalid_values(value):
    with pytest.raises(ParameterValidationError):
        validate_edge_burst_idle_time(value)


@pytest.mark.parametrize("value", [1e-8, 10.0])
def test_edge_burst_idle_time_accepts_boundaries(value):
    assert validate_edge_burst_idle_time(value) == value


@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_edge_burst_level_rejects_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_trigger_level(value)
