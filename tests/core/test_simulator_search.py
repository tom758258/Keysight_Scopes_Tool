import pytest

from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_search_state_mode_and_count_are_deterministic():
    backend = SimulatorBackend(model="DSOX4034A")
    scope = KeysightScope(backend)
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
    "model, command",
    [
        ("DSOX2004A", ":SEARch:MODE EDGE"),
        ("DSOX2004A", ":SEARch:MODE SERial2"),
        ("DSOX3024A", ":SEARch:MODE PEAK"),
    ],
)
def test_simulator_rejects_search_modes_outside_model_profile(model, command):
    backend = SimulatorBackend(model=model)
    with pytest.raises(SimulatorBackendError, match="not supported by simulator model"):
        backend.write(command)


def test_simulator_accepts_profile_supported_search_modes():
    SimulatorBackend(model="DSOX2004A").write(":SEARch:MODE SERial1")
    SimulatorBackend(model="DSOX3024A").write(":SEARch:MODE EDGE")
    SimulatorBackend(model="DSOX4034A").write(":SEARch:MODE PEAK")
