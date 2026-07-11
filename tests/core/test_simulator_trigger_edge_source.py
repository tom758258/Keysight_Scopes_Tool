import pytest

from keysight_scope_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_trigger_edge_source_roundtrip_and_isolation():
    backend = SimulatorBackend(model="DSOX4034A")
    initial_mode = backend.trigger_mode
    initial_level = backend.trigger_level
    initial_slope = backend.trigger_slope
    initial_coupling = backend.trigger_edge_coupling
    initial_reject = backend.trigger_edge_reject

    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    assert backend.query(":TRIGger:EDGE:SOURce?") == "CHANnel1"
    backend.write(":TRIGger:EDGE:SOURce CHANnel4")
    assert backend.query(":TRIGger:EDGE:SOURce?") == "CHANnel4"
    backend.write(":TRIGger:EDGE:SOURce EXTernal")
    assert backend.query(":TRIGger:EDGE:SOURce?") == "EXT"
    backend.write(":TRIGger:EDGE:SOURce LINE")
    assert backend.query(":TRIGger:EDGE:SOURce?") == "LINE"

    assert backend.history == [
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:SOURce CHANnel4",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:SOURce EXTernal",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:SOURce LINE",
        ":TRIGger:EDGE:SOURce?",
    ]
    assert backend.trigger_mode == initial_mode
    assert backend.trigger_level == initial_level
    assert backend.trigger_slope == initial_slope
    assert backend.trigger_edge_coupling == initial_coupling
    assert backend.trigger_edge_reject == initial_reject
    assert ":TRIGger:MODE EDGE" not in backend.history


def test_simulator_trigger_edge_source_rejects_invalid_values_and_channels():
    backend = SimulatorBackend(model="DSOX2004A")

    with pytest.raises(SimulatorBackendError):
        backend.write(":TRIGger:EDGE:SOURce WGEN1")
    with pytest.raises(SimulatorBackendError):
        backend.write(":TRIGger:EDGE:SOURce CHANnel5")
