import pytest

from keysight_scope_cli import cli, worker
from keysight_scope_core.errors import KeysightScopeError


def _runtime(tmp_path):
    return worker.WorkerRuntime("127.0.0.1", 0, "simulate", "DSOX4024A", None, tmp_path, 1, "jsonl")


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("reference-save", {"slot": 1, "source_channel": 1}),
        ("reference-display", {"slot": 1, "state": "on"}),
        ("reference-display", {"slot": 1, "query": True}),
        ("reference-label", {"slot": 1, "text": "BASELINE"}),
        ("reference-label", {"slot": 1, "query": True}),
        ("reference-clear", {"slot": 1}),
        ("reference-query", {"slot": 1}),
    ],
)
def test_reference_worker_accepts_maps_and_routes_simulator(tmp_path, command, arguments):
    assert worker.validate_command_request({"command": command, "arguments": arguments})[:2] == (command, arguments)
    parsed = worker.parse_domain_command(command, arguments, _runtime(tmp_path))
    payload, exit_code = cli._execute_json_command(parsed)
    assert exit_code == 0
    assert payload["command"] == command
    assert payload["mode"] == "simulate"


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("reference-save", {"slot": 0, "source_channel": 1}),
        ("reference-save", {"slot": 3, "source_channel": 1}),
        ("reference-save", {"slot": 1, "source_channel": 5}),
        ("reference-display", {"slot": 1}),
        ("reference-display", {"slot": 1, "query": False}),
        ("reference-label", {"slot": 1}),
        ("reference-label", {"slot": 1, "text": "TOO-LONG-11"}),
    ],
)
def test_reference_worker_rejects_invalid_arguments(tmp_path, command, arguments):
    with pytest.raises(KeysightScopeError):
        worker.parse_domain_command(command, arguments, _runtime(tmp_path))
