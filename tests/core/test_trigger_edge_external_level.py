import math

import pytest

import keysight_scope_core
from keysight_scope_core.errors import ParameterValidationError, TriggerResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.trigger import (
    EdgeTriggerExternalLevelController,
    EdgeTriggerExternalLevelState,
    edge_trigger_external_level_command,
    edge_trigger_external_level_query,
)


@pytest.mark.parametrize(("value", "text"), [(0.5, "0.5"), (-0.25, "-0.25"), (0.0, "0")])
def test_external_edge_level_builders_always_use_external_qualified_scpi(value, text):
    assert edge_trigger_external_level_command(value) == f":TRIGger:EDGE:LEVel {text},EXTernal"
    assert edge_trigger_external_level_query() == ":TRIGger:EDGE:LEVel? EXTernal"


def test_external_edge_level_controller_preserves_scientific_query_readback():
    backend = FakeBackend(responses={":TRIGger:EDGE:LEVel? EXTernal": " -5.00000000E-01 "})
    controller = EdgeTriggerExternalLevelController(backend)

    controller.configure(level_volts=0.5)
    state = controller.query()

    assert backend.history == [
        ":TRIGger:EDGE:LEVel 0.5,EXTernal",
        ":TRIGger:EDGE:LEVel? EXTernal",
    ]
    assert state == EdgeTriggerExternalLevelState(-0.5, "-5.00000000E-01")
    assert state.to_json() == {"level_volts": -0.5, "raw_level": "-5.00000000E-01"}


@pytest.mark.parametrize(
    "value", [True, False, math.nan, math.inf, -math.inf, "0.5", 10**309, -(10**309)]
)
def test_external_edge_level_rejects_nonfinite_or_nonreal_values(value):
    with pytest.raises(ParameterValidationError):
        edge_trigger_external_level_command(value)


@pytest.mark.parametrize("raw", ["", "abc", "NaN", "INF", "+INF", "-INF"])
def test_external_edge_level_rejects_invalid_instrument_readbacks(raw):
    controller = EdgeTriggerExternalLevelController(
        FakeBackend(responses={":TRIGger:EDGE:LEVel? EXTernal": raw})
    )

    with pytest.raises(TriggerResponseError):
        controller.query()


def test_external_edge_level_scope_api_and_public_exports():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4034A,SIM000000,07.20",
            ":TRIGger:EDGE:LEVel? EXTernal": "+5.00000000E-01",
        }
    )
    scope = KeysightScope(backend)
    scope.query_idn()

    scope.configure_trigger_edge_external_level(level_volts=-0.25)
    state = scope.query_trigger_edge_external_level()

    assert backend.history[-2:] == [
        ":TRIGger:EDGE:LEVel -0.25,EXTernal",
        ":TRIGger:EDGE:LEVel? EXTernal",
    ]
    assert state.level_volts == 0.5
    assert keysight_scope_core.EdgeTriggerExternalLevelController is EdgeTriggerExternalLevelController
    assert keysight_scope_core.EdgeTriggerExternalLevelState is EdgeTriggerExternalLevelState
