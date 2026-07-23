import pytest
from scopes_tool_core.simulator_backend import SimulatorBackend, SimulatorBackendError

def test_simulator_trigger_edge_coupling_roundtrip():
    backend = SimulatorBackend()

    backend.write(":TRIGger:EDGE:COUPling AC")
    assert backend.query(":TRIGger:EDGE:COUPling?") == "AC"

    backend.write(":TRIGger:EDGE:COUPling DC")
    assert backend.query(":TRIGger:EDGE:COUPling?") == "DC"

    backend.write(":TRIGger:EDGE:COUPling LFReject")
    assert backend.query(":TRIGger:EDGE:COUPling?") == "LFReject"

    with pytest.raises(SimulatorBackendError) as exc:
        backend.write(":TRIGger:EDGE:COUPling INVALID")
    assert "Unsupported simulator write" in str(exc.value)


def test_simulator_trigger_edge_reject_roundtrip():
    backend = SimulatorBackend()

    backend.write(":TRIGger:EDGE:REJect OFF")
    assert backend.query(":TRIGger:EDGE:REJect?") == "OFF"

    backend.write(":TRIGger:EDGE:REJect LFReject")
    assert backend.query(":TRIGger:EDGE:REJect?") == "LFReject"

    backend.write(":TRIGger:EDGE:REJect HFReject")
    assert backend.query(":TRIGger:EDGE:REJect?") == "HFReject"

    with pytest.raises(SimulatorBackendError) as exc:
        backend.write(":TRIGger:EDGE:REJect INVALID")
    assert "Unsupported simulator write" in str(exc.value)


def test_simulator_trigger_edge_history_and_isolation():
    backend = SimulatorBackend()
    initial_history_len = len(backend.history)

    backend.write(":TRIGger:EDGE:COUPling AC")
    assert backend.query(":TRIGger:EDGE:COUPling?") == "AC"
    backend.write(":TRIGger:EDGE:REJect OFF")
    assert backend.query(":TRIGger:EDGE:REJect?") == "OFF"

    added_history = backend.history[initial_history_len:]
    assert added_history == [
        ":TRIGger:EDGE:COUPling AC",
        ":TRIGger:EDGE:COUPling?",
        ":TRIGger:EDGE:REJect OFF",
        ":TRIGger:EDGE:REJect?",
    ]
