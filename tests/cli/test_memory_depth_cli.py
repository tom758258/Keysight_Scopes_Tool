"""Tests for the memory-depth CLI command."""

import json

import pytest

from keysight_scope_cli import cli
from keysight_scope_core.acquisition import memory_depth_query, parse_memory_depth
from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.idn import parse_idn
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.status import SystemErrorEntry


class _MemoryDepthBackend:
    backend = "fake"
    timeout = 2000


class _MemoryDepthDummyScope:
    backend = _MemoryDepthBackend()

    def __init__(self):
        self.capabilities = None
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback

    def query_idn(self):
        self.calls.append("query_idn")
        self.capabilities = capabilities_for_model("DSOX4024A")
        return parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY123,07.20")

    def query_system_error(self):
        self.calls.append("query_system_error")
        return SystemErrorEntry(code=0, message="No error", raw=chr(43) + chr(48) + chr(44) + chr(34) + "No error" + chr(34))

    def query(self, command):
        self.calls.append(("query", command))
        if command == memory_depth_query():
            return "1000000"
        raise AssertionError("unexpected SCPI command: " + command)


def _install_memory_depth_scope(monkeypatch):
    scope = _MemoryDepthDummyScope()
    monkeypatch.setattr(
        cli.KeysightScope,
        "open",
        staticmethod(lambda resource, visa_library=None: scope),
    )
    return scope


def test_memory_depth_cli_requires_query_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["memory-depth", "--resource", "USB0::FAKE::INSTR"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "the following arguments are required: --query" in captured.err


def test_memory_depth_cli_rejects_set_or_points_arguments(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main([
            "memory-depth",
            "--query",
            "--resource",
            "USB0::FAKE::INSTR",
            "--value",
            "1000",
        ])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "unrecognized arguments: --value" in captured.err


def test_memory_depth_cli_dry_run_includes_planned_scpi_without_visa(monkeypatch, capsys):
    _install_memory_depth_scope(monkeypatch)

    def fail_open(resource, visa_library=None):
        raise AssertionError("dry-run must not open VISA")

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fail_open))

    assert cli.main([
        "memory-depth",
        "--query",
        "--dry-run",
        "--json",
    ]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["command"] == "memory-depth"
    assert payload["mode"] == "dry_run"
    assert payload["result"]["operation"] == "query"
    assert payload["result"]["scpi_command"] == memory_depth_query()
    assert payload["result"]["planned_scpi"] == [
        "*IDN?",
        memory_depth_query(),
        ":SYSTem:ERRor?",
    ]
    assert payload["scpi"]["planned"] == payload["result"]["planned_scpi"]
    assert payload["result"]["unit"] == "points"
    assert "memory_depth_points" not in payload["result"]
    assert payload["scpi"]["sent"] == []
    assert payload["files"] == []


def test_memory_depth_cli_simulate_returns_memory_depth_in_points(monkeypatch, capsys):
    _install_memory_depth_scope(monkeypatch)

    assert cli.main([
        "memory-depth",
        "--query",
        "--simulate",
        "--json",
    ]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["mode"] == "simulate"
    assert payload["result"]["operation"] == "query"
    assert payload["result"]["unit"] == "points"
    assert payload["result"]["scpi_command"] == memory_depth_query()
    assert payload["result"]["memory_depth_points"] == 1000000
    assert isinstance(payload["result"]["memory_depth_points"], int)
    assert payload["result"]["raw_value"] == "1000000"
    sent = payload["scpi"]["sent"]
    assert "*IDN?" in sent
    assert memory_depth_query() in sent
    assert ":SYSTem:ERRor?" in sent


def test_memory_depth_cli_simulate_scpi_order(monkeypatch, capsys):
    _install_memory_depth_scope(monkeypatch)

    assert cli.main([
        "memory-depth",
        "--query",
        "--simulate",
        "--json",
    ]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        memory_depth_query(),
        ":SYSTem:ERRor?",
    ]


def test_memory_depth_cli_command_order_with_fake_backend():
    backend = FakeBackend(responses={":ACQuire:POINts?": "1000000"})
    client = SCPIClient(backend)

    raw = client.query(memory_depth_query())
    value = parse_memory_depth(raw)

    assert value == 1000000
    assert backend.history == [memory_depth_query()]


def test_memory_depth_cli_simulate_uses_simulator_backend(monkeypatch, capsys):
    assert cli.main([
        "memory-depth",
        "--query",
        "--simulate",
        "--json",
        "--model",
        "DSOX4024A",
    ]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "simulate"
    assert payload["result"]["memory_depth_points"] == 1000000
    assert payload["result"]["scpi_command"] == memory_depth_query()


def test_memory_depth_cli_scpi_log_does_not_break_json_stdout(monkeypatch, capsys):
    _install_memory_depth_scope(monkeypatch)

    assert cli.main([
        "memory-depth",
        "--query",
        "--simulate",
        "--json",
        "--log-scpi",
    ]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["result"]["memory_depth_points"] == 1000000
