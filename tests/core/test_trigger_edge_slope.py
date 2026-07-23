import pytest

import scopes_tool_core
from scopes_tool_core.errors import ParameterValidationError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scope import Oscilloscope
from scopes_tool_core.trigger import (
    EdgeTriggerSlopeController,
    EdgeTriggerSlopeState,
    edge_trigger_slope_command,
    edge_trigger_slope_query,
    parse_trigger_edge_slope,
)


@pytest.mark.parametrize(
    ("value", "command"),
    [
        ("positive", "POSitive"),
        ("negative", "NEGative"),
        ("either", "EITHer"),
        ("alternate", "ALTernate"),
    ],
)
def test_edge_trigger_slope_controller_configures_canonical_values(value, command):
    backend = FakeBackend()
    controller = EdgeTriggerSlopeController(backend)

    controller.configure(slope=value)

    assert backend.history == [f":TRIGger:EDGE:SLOPe {command}"]


def test_edge_trigger_slope_query_builder_and_tolerant_parser():
    assert edge_trigger_slope_query() == ":TRIGger:EDGE:SLOPe?"
    assert edge_trigger_slope_command("POSitive") == ":TRIGger:EDGE:SLOPe POSitive"

    state = parse_trigger_edge_slope("  pOsItIvE\n")
    assert state == EdgeTriggerSlopeState("positive", "pOsItIvE")
    assert state.to_json() == {"slope": "positive", "raw_slope": "pOsItIvE"}


@pytest.mark.parametrize(
    ("raw", "slope"),
    [
        ("POS", "positive"),
        ("NEGATIVE", "negative"),
        ("eith", "either"),
        ("ALTernate", "alternate"),
        ("FUTURE", None),
    ],
)
def test_edge_trigger_slope_parser_accepts_documented_readbacks_and_tolerates_unknown(raw, slope):
    state = parse_trigger_edge_slope(raw)

    assert state.slope == slope
    assert state.raw_slope == raw


@pytest.mark.parametrize("value", ["POSITIVE", "rising", "pos", "", None])
def test_edge_trigger_slope_controller_rejects_noncanonical_configure_values(value):
    with pytest.raises(ParameterValidationError):
        EdgeTriggerSlopeController(FakeBackend()).configure(slope=value)


def test_edge_trigger_slope_controller_query_and_scope_api_exports():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX3024A,SIM000000,07.20",
            ":TRIGger:EDGE:SLOPe?": "ALT",
        }
    )
    scope = Oscilloscope(backend)
    scope.query_idn()

    scope.configure_trigger_edge_slope(slope="negative")
    state = scope.query_trigger_edge_slope()

    assert backend.history[-2:] == [
        ":TRIGger:EDGE:SLOPe NEGative",
        ":TRIGger:EDGE:SLOPe?",
    ]
    assert state == EdgeTriggerSlopeState("alternate", "ALT")
    assert scopes_tool_core.EdgeTriggerSlopeController is EdgeTriggerSlopeController
    assert scopes_tool_core.EdgeTriggerSlopeState is EdgeTriggerSlopeState
