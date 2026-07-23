import math

import pytest

import scopes_tool_core
from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError, TriggerResponseError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scope import Oscilloscope
from scopes_tool_core.trigger import (
    EdgeTriggerLevelController,
    EdgeTriggerLevelState,
    edge_trigger_level_channel_command,
    edge_trigger_level_channel_query,
)


@pytest.mark.parametrize(
    ("value", "text"),
    [(0.5, "0.5"), (-0.25, "-0.25"), (0.0, "0")],
)
def test_edge_trigger_level_channel_builders_use_source_qualified_syntax(value, text):
    assert (
        edge_trigger_level_channel_command(4, value)
        == f":TRIGger:EDGE:LEVel {text},CHANnel4"
    )
    assert edge_trigger_level_channel_query(4) == ":TRIGger:EDGE:LEVel? CHANnel4"


def test_edge_trigger_level_controller_configures_and_queries_raw_numeric_level():
    backend = FakeBackend(responses={":TRIGger:EDGE:LEVel? CHANnel2": "+5.00000000E-01"})
    controller = EdgeTriggerLevelController(backend, capabilities_for_model("DSOX4034A"))

    controller.configure(source_channel=2, level_volts=-0.25)
    state = controller.query(source_channel=2)

    assert backend.history == [
        ":TRIGger:EDGE:LEVel -0.25,CHANnel2",
        ":TRIGger:EDGE:LEVel? CHANnel2",
    ]
    assert state == EdgeTriggerLevelState(2, 0.5, "+5.00000000E-01")
    assert state.to_json() == {
        "source_channel": 2,
        "level_volts": 0.5,
        "raw_level": "+5.00000000E-01",
    }


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, False, "0.5"])
def test_edge_trigger_level_controller_rejects_nonfinite_or_nonreal_values(value):
    controller = EdgeTriggerLevelController(FakeBackend(), capabilities_for_model("DSOX4034A"))

    with pytest.raises(ParameterValidationError):
        controller.configure(source_channel=1, level_volts=value)


@pytest.mark.parametrize("channel", [0, 5, True])
def test_edge_trigger_level_controller_validates_model_channels(channel):
    controller = EdgeTriggerLevelController(FakeBackend(), capabilities_for_model("DSOX2004A"))

    with pytest.raises(ParameterValidationError):
        controller.configure(source_channel=channel, level_volts=0.5)


@pytest.mark.parametrize("raw", ["NONE", "NaN", "INF", "not-a-number"])
def test_edge_trigger_level_controller_rejects_invalid_instrument_readbacks(raw):
    controller = EdgeTriggerLevelController(
        FakeBackend(responses={":TRIGger:EDGE:LEVel? CHANnel1": raw}),
        capabilities_for_model("DSOX2004A"),
    )

    with pytest.raises(TriggerResponseError):
        controller.query(source_channel=1)


def test_edge_trigger_level_scope_api_and_public_exports():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX3024A,SIM000000,07.20",
            ":TRIGger:EDGE:LEVel? CHANnel4": "-2.50000000E-01",
        }
    )
    scope = Oscilloscope(backend)
    scope.query_idn()

    scope.configure_trigger_edge_level(source_channel=4, level_volts=0.5)
    state = scope.query_trigger_edge_level(source_channel=4)

    assert backend.history[-2:] == [
        ":TRIGger:EDGE:LEVel 0.5,CHANnel4",
        ":TRIGger:EDGE:LEVel? CHANnel4",
    ]
    assert state.level_volts == -0.25
    assert scopes_tool_core.EdgeTriggerLevelController is EdgeTriggerLevelController
    assert scopes_tool_core.EdgeTriggerLevelState is EdgeTriggerLevelState
