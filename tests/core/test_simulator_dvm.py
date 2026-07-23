import pytest

from scopes_tool_core.errors import KeysightScopeError
from scopes_tool_core.scope import KeysightScope
from scopes_tool_core.simulator_backend import SimulatorBackend


def _scope():
    backend = SimulatorBackend(model="DSOX4024A")
    scope = KeysightScope(backend)
    scope.query_idn()
    return scope, backend


def test_simulator_dvm_configure_query_roundtrips_and_aggregate():
    scope, backend = _scope()
    backend.dvm_current_value = 1.234
    scope.configure_dvm_enable(True)
    scope.configure_dvm_source(2)
    scope.configure_dvm_mode("ac-rms")
    scope.configure_dvm_auto_range(False)

    assert scope.query_dvm_enable().enabled is True
    assert scope.query_dvm_source().source_channel == 2
    assert scope.query_dvm_mode().mode == "ac-rms"
    assert scope.query_dvm_auto_range().auto_range_enabled is False
    assert scope.query_dvm_current().value == pytest.approx(1.234)
    state = scope.query_dvm()
    assert state.enabled is True
    assert state.source_channel == 2
    assert state.mode == "ac-rms"
    assert state.auto_range_enabled is False
    assert state.value == pytest.approx(1.234)


@pytest.mark.parametrize("command", [":DVM:FREQuency?", ":COUNter:ENABle?", ":MEASure:COUNter?"])
def test_simulator_keeps_dvm_frequency_and_counter_queries_unsupported(command):
    backend = SimulatorBackend()
    with pytest.raises(KeysightScopeError):
        backend.query(command)


def test_simulator_keeps_dvm_frequency_mode_unsupported():
    backend = SimulatorBackend()
    with pytest.raises(KeysightScopeError):
        backend.write(":DVM:MODE FREQuency")
