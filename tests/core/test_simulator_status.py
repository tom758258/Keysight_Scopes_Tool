from scopes_tool_core.scope import KeysightScope
from scopes_tool_core.simulator_backend import SimulatorBackend


def test_simulator_system_status_queries_are_deterministic():
    backend = SimulatorBackend()
    scope = KeysightScope(backend)

    assert scope.query_operation_complete().to_json() == {"complete": True, "raw": "1"}
    assert scope.query_status_byte().to_json() == {
        "value": 0,
        "raw": "0",
        "set_bits": (),
    }
    assert scope.query_standard_event_status().value == 0
    assert scope.query_operation_status().value == 0
    assert scope.query_system_options().to_json() == {"raw": "0", "options": ("0",)}


def test_simulator_standard_event_query_is_destructive():
    backend = SimulatorBackend(standard_event_status=5)
    scope = KeysightScope(backend)

    assert scope.query_standard_event_status().value == 5
    assert scope.query_standard_event_status().value == 0


def test_simulator_clear_status_clears_error_and_event_state():
    backend = SimulatorBackend(
        system_errors=['-113,"Undefined header"'],
        status_byte=4,
        standard_event_status=8,
    )
    scope = KeysightScope(backend)

    scope.clear_status()

    assert backend.history == ["*CLS"]
    assert scope.query_status_byte().value == 0
    assert scope.query_standard_event_status().value == 0
    assert scope.query_system_error().code == 0
