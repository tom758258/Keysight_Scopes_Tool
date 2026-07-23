import pytest

from scopes_tool_core.scope import Oscilloscope
from scopes_tool_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_search_state_mode_and_count_are_deterministic():
    backend = SimulatorBackend(physical_model_id="keysight-dsox4034a")
    scope = Oscilloscope(backend)
    scope.query_idn()

    assert scope.query_search_state().to_json() == {"enabled": False, "raw_state": "0"}
    assert scope.query_search_mode().to_json() == {
        "mode": None,
        "enabled": False,
        "raw_mode": "OFF",
    }
    assert scope.query_search_count().to_json() == {"count": 0, "raw_count": "0"}

    scope.configure_search_mode("peak")
    assert scope.query_search_state().enabled is True
    assert scope.query_search_mode().to_json() == {
        "mode": "peak",
        "enabled": True,
        "raw_mode": "PEAK",
    }

    scope.configure_search_state(False)
    assert scope.query_search_mode().mode is None


@pytest.mark.parametrize(
    "model_id, command",
    [
        ("keysight-dsox2004a", ":SEARch:MODE EDGE"),
        ("keysight-dsox2004a", ":SEARch:MODE SERial2"),
        ("keysight-dsox3024a", ":SEARch:MODE PEAK"),
    ],
)
def test_simulator_rejects_search_modes_outside_model_profile(model_id, command):
    backend = SimulatorBackend(physical_model_id=model_id)
    with pytest.raises(SimulatorBackendError, match="not supported by simulator model"):
        backend.write(command)


def test_simulator_accepts_profile_supported_search_modes():
    SimulatorBackend(physical_model_id="keysight-dsox2004a").write(":SEARch:MODE SERial1")
    SimulatorBackend(physical_model_id="keysight-dsox3024a").write(":SEARch:MODE EDGE")
    SimulatorBackend(physical_model_id="keysight-dsox4034a").write(":SEARch:MODE PEAK")
