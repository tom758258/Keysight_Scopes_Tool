import math

import pytest

import keysight_scope_core
from keysight_scope_core.errors import ParameterValidationError, TriggerResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.trigger import (
    ExternalTriggerRangeController,
    ExternalTriggerRangeState,
    external_trigger_range_command,
    external_trigger_range_query,
)


@pytest.mark.parametrize(("value", "text"), [(1.6, "1.6"), (8.0, "8"), (12.5, "12.5")])
def test_external_trigger_range_builders_accept_any_finite_positive_range(value, text):
    assert external_trigger_range_command(value) == f":EXTernal:RANGe {text}"
    assert external_trigger_range_query() == ":EXTernal:RANGe?"


def test_external_trigger_range_controller_preserves_scientific_query_readback():
    backend = FakeBackend(responses={":EXTernal:RANGe?": " 8.00000000E+00 "})
    controller = ExternalTriggerRangeController(backend)

    controller.configure(range_volts=1.6)
    state = controller.query()

    assert backend.history == [":EXTernal:RANGe 1.6", ":EXTernal:RANGe?"]
    assert state == ExternalTriggerRangeState(8.0, "8.00000000E+00")
    assert state.to_json() == {"range_volts": 8.0, "raw_range": "8.00000000E+00"}


@pytest.mark.parametrize("value", [0, -1.0, True, False, math.nan, math.inf, -math.inf, "8"])
def test_external_trigger_range_rejects_nonpositive_or_nonreal_values(value):
    with pytest.raises(ParameterValidationError):
        external_trigger_range_command(value)


@pytest.mark.parametrize("raw", ["", "abc", "NaN", "INF", "+INF", "-INF"])
def test_external_trigger_range_rejects_invalid_instrument_readbacks(raw):
    controller = ExternalTriggerRangeController(
        FakeBackend(responses={":EXTernal:RANGe?": raw})
    )

    with pytest.raises(TriggerResponseError):
        controller.query()


def test_external_trigger_range_scope_api_and_public_exports():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX3024A,SIM000000,07.20",
            ":EXTernal:RANGe?": "1.60000000E+00",
        }
    )
    scope = KeysightScope(backend)
    scope.query_idn()

    scope.configure_external_trigger_range(1.6)
    state = scope.query_external_trigger_range()

    assert backend.history[-2:] == [":EXTernal:RANGe 1.6", ":EXTernal:RANGe?"]
    assert state.range_volts == 1.6
    assert keysight_scope_core.ExternalTriggerRangeController is ExternalTriggerRangeController
    assert keysight_scope_core.ExternalTriggerRangeState is ExternalTriggerRangeState
