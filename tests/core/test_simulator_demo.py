import pytest

from scopes_tool_core.scope import KeysightScope
from scopes_tool_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_demo_defaults_and_roundtrip():
    backend = SimulatorBackend(model="DSOX4024A")
    scope = KeysightScope(backend)
    scope.query_idn()

    initial = scope.query_demo()
    assert initial.function == "sine"
    assert initial.function_scpi == "SIN"
    assert initial.enabled is False
    assert initial.phase_degrees == 0.0

    scope.configure_demo_output(True)
    scope.configure_demo_function("glitch")
    scope.configure_demo_phase(90)
    assert scope.query_demo_output().enabled is True
    assert scope.query_demo_function().function == "glitch"
    assert scope.query_demo_phase().phase_degrees == 90.0


def test_simulator_rejects_unsupported_demo_token_and_phase():
    backend = SimulatorBackend(model="DSOX2004A")
    with pytest.raises(SimulatorBackendError):
        backend.write(":DEMO:FUNCtion I2S")
    with pytest.raises(SimulatorBackendError):
        backend.write(":DEMO:FUNCtion USB")
    with pytest.raises(SimulatorBackendError):
        backend.write(":DEMO:FUNCtion:PHASe:PHASe 361")


@pytest.mark.parametrize("value, expected", [("ON", "1"), ("OFF", "0"), ("1", "1"), ("0", "0")])
def test_simulator_demo_output_accepts_common_boolean_tokens(value, expected):
    backend = SimulatorBackend()
    backend.write(f":DEMO:OUTPut {value}")
    assert backend.query(":DEMO:OUTPut?") == expected
