import pytest

from scopes_tool_cli import cli, worker
from scopes_tool_core.errors import OscilloscopeError


def _runtime(tmp_path):
    return worker.WorkerRuntime("127.0.0.1", 0, "simulate", "DSOX4024A", None, tmp_path, 1, "jsonl")


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("measure-clear", {}),
        ("measure-show", {"on": True}),
        ("measure-show", {"query": True}),
        ("measure-source", {"source_channel": 1}),
        ("measure-source", {"source_channel": 1, "source2_channel": 2}),
        ("measure-source", {"query": True}),
        ("measure-window", {"window": "main"}),
        ("measure-window", {"query": True}),
    ],
)
def test_measurement_worker_accepts_maps_and_routes_simulator(tmp_path, command, arguments):
    assert worker.validate_command_request({"command": command, "arguments": arguments})[:2] == (command, arguments)
    parsed = worker.parse_domain_command(command, arguments, _runtime(tmp_path))
    payload, exit_code = cli._execute_json_command(parsed)
    assert exit_code == 0
    assert payload["command"] == command
    assert payload["mode"] == "simulate"


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("measure-show", {"off": True}),
        ("measure-show", {"query": False}),
        ("measure-source", {}),
        ("measure-source", {"source_channel": 0}),
        ("measure-source", {"source_channel": 5}),
        ("measure-window", {}),
        ("measure-window", {"window": "screen"}),
    ],
)
def test_measurement_worker_rejects_invalid_arguments(tmp_path, command, arguments):
    with pytest.raises(OscilloscopeError):
        worker.parse_domain_command(command, arguments, _runtime(tmp_path))

