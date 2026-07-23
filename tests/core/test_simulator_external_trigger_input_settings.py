import pytest

from scopes_tool_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_external_trigger_input_state_is_independent_and_aggregate_is_dynamic():
    backend = SimulatorBackend(physical_model_id="keysight-dsox4034a")
    initial_range = backend.external_trigger_range
    initial_external_level = backend.edge_external_level
    initial_analog_levels = dict(backend.trigger_levels)

    backend.write(":EXTernal:PROBe 10")
    backend.write(":EXTernal:UNITs AMPere")

    assert backend.query(":EXTernal:PROBe?") == "10"
    assert backend.query(":EXTernal:UNITs?") == "AMP"
    aggregate = backend.query(":EXTernal?")
    assert "RANG +8.00000000E+00" in aggregate
    assert "UNIT AMPere" in aggregate
    assert "PROB +1.00000000E+01" in aggregate
    assert backend.external_trigger_range == initial_range
    assert backend.edge_external_level == initial_external_level
    assert backend.trigger_levels == initial_analog_levels
    assert backend.history == [
        ":EXTernal:PROBe 10", ":EXTernal:UNITs AMPere", ":EXTernal:PROBe?", ":EXTernal:UNITs?", ":EXTernal?"
    ]


@pytest.mark.parametrize("command", [":EXTernal:PROBe 0", ":EXTernal:PROBe -1", ":EXTernal:PROBe NaN"])
def test_simulator_external_trigger_probe_rejects_nonpositive_or_nonfinite_values(command):
    with pytest.raises(SimulatorBackendError):
        SimulatorBackend(physical_model_id="keysight-dsox2004a").write(command)


def test_simulator_external_trigger_units_rejects_unsupported_values_without_changing_state():
    backend = SimulatorBackend(physical_model_id="keysight-dsox3024a")
    with pytest.raises(SimulatorBackendError):
        backend.write(":EXTernal:UNITs OHM")
    assert backend.external_trigger_units == "VOLT"


def test_simulator_external_aggregate_query_override_remains_available_for_parser_tests():
    backend = SimulatorBackend(
        physical_model_id="keysight-dsox4034a",
        query_overrides={":EXTernal?": "EXTernal:UNITs AMP;EXTernal:PROBe +10"},
    )
    assert backend.query(":EXTernal?") == "EXTernal:UNITs AMP;EXTernal:PROBe +10"
