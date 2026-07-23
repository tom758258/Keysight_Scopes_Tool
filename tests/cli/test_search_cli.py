import json

import pytest

from scopes_tool_cli import cli


def _payload(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


@pytest.mark.parametrize(
    "args, expected",
    [
        (["search-state", "--query"], [":SEARch:STATe?"]),
        (["search-state", "--enabled", "true"], [":SEARch:STATe 1"]),
        (["search-state", "--enabled", "false"], [":SEARch:STATe 0"]),
        (["search-mode", "--query"], [":SEARch:MODE?"]),
        (["search-mode", "--mode", "serial1"], [":SEARch:STATe 1", ":SEARch:MODE SERial1"]),
        (["search-mode", "--mode", "edge"], [":SEARch:STATe 1", ":SEARch:MODE EDGE"]),
        (["search-mode", "--mode", "glitch"], [":SEARch:STATe 1", ":SEARch:MODE GLITch"]),
        (["search-mode", "--mode", "runt"], [":SEARch:STATe 1", ":SEARch:MODE RUNT"]),
        (["search-mode", "--mode", "transition"], [":SEARch:STATe 1", ":SEARch:MODE TRANsition"]),
        (["search-mode", "--mode", "peak"], [":SEARch:STATe 1", ":SEARch:MODE PEAK"]),
        (["search-count", "--query"], [":SEARch:COUNt?"]),
    ],
)
def test_search_commands_dry_run_json(capsys, args, expected):
    assert cli.main([*args, "--dry-run", "--json", "--model", "DSOX4034A"]) == 0
    payload = _payload(capsys)
    assert payload["scpi"]["planned"] == [*expected, ":SYSTem:ERRor?"]


def test_search_simulator_queries_are_deterministic_and_preserve_raw(capsys):
    assert cli.main(["search-state", "--query", "--simulate", "--json"]) == 0
    result = _payload(capsys)["result"]
    assert {key: result[key] for key in ("operation", "command", "enabled", "raw_state")} == {
        "operation": "query",
        "command": ":SEARch:STATe?",
        "enabled": False,
        "raw_state": "0",
    }

    assert cli.main(["search-mode", "--query", "--simulate", "--json"]) == 0
    result = _payload(capsys)["result"]
    assert {
        key: result[key]
        for key in ("operation", "command", "mode", "enabled", "raw_mode")
    } == {
        "operation": "query",
        "command": ":SEARch:MODE?",
        "mode": None,
        "enabled": False,
        "raw_mode": "OFF",
    }

    assert cli.main(["search-count", "--query", "--simulate", "--json"]) == 0
    result = _payload(capsys)["result"]
    assert {key: result[key] for key in ("operation", "command", "count", "raw_count")} == {
        "operation": "query",
        "command": ":SEARch:COUNt?",
        "count": 0,
        "raw_count": "0",
    }


@pytest.mark.parametrize(
    "args",
    [
        ["search-state"],
        ["search-state", "--query", "--enabled", "true"],
        ["search-mode"],
        ["search-mode", "--query", "--mode", "edge"],
    ],
)
def test_search_action_validation_fails_before_open(monkeypatch, capsys, args):
    monkeypatch.setattr(cli, "_open_scope", lambda *unused: pytest.fail("opened scope"))
    assert cli.main([*args, "--simulate", "--json", "--model", "DSOX4034A"]) == 1
    assert _payload(capsys)["ok"] is False


@pytest.mark.parametrize("mode", ["ser1", "ser2", "glit", "tran", "pwid", "pulse-width", "off", "EDGE"])
def test_search_mode_rejects_aliases(mode, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["search-mode", "--mode", mode, "--simulate", "--json"])
    assert excinfo.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "model, mode",
    [
        ("DSOX2004A", "edge"),
        ("DSOX2004A", "serial2"),
        ("DSOX3024A", "peak"),
    ],
)
def test_search_mode_profile_rejection_happens_before_open(monkeypatch, capsys, model, mode):
    monkeypatch.setattr(cli, "_open_scope", lambda *unused: pytest.fail("opened scope"))
    assert cli.main(
        ["search-mode", "--mode", mode, "--simulate", "--json", "--model", model]
    ) == 1
    payload = _payload(capsys)
    assert "not supported by the selected" in payload["error"]["message"]


def test_search_count_requires_query(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["search-count"])
    assert excinfo.value.code == 2
    assert capsys.readouterr().out == ""
