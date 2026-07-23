import json

import pytest

from scopes_tool_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


@pytest.mark.parametrize(
    "command, query_arg, expected_query",
    [
        ("trigger-sweep", "--query", ":TRIGger:SWEep?"),
        ("trigger-noise-reject", "--query", ":TRIGger:NREJect?"),
        ("trigger-hf-reject", "--query", ":TRIGger:HFReject?"),
    ],
)
def test_trigger_common_query_dry_run_json(capsys, command, query_arg, expected_query):
    assert cli.main([command, "--dry-run", "--json", "--model", "DSOX4024A", query_arg]) == 0

    payload = _json_stdout(capsys)
    assert payload["command"] == command
    assert payload["result"] == {"operation": "query", "command": expected_query}
    assert payload["scpi"]["planned"] == [expected_query, ":SYSTem:ERRor?"]


@pytest.mark.parametrize(
    "args, expected_command, expected_result",
    [
        (
            ["trigger-sweep", "--mode", "auto"],
            ":TRIGger:SWEep AUTO",
            {"mode": "auto"},
        ),
        (
            ["trigger-sweep", "--mode", "normal"],
            ":TRIGger:SWEep NORMal",
            {"mode": "normal"},
        ),
        (
            ["trigger-noise-reject", "--enabled", "true"],
            ":TRIGger:NREJect ON",
            {"enabled": True},
        ),
        (
            ["trigger-noise-reject", "--enabled", "false"],
            ":TRIGger:NREJect OFF",
            {"enabled": False},
        ),
        (
            ["trigger-hf-reject", "--enabled", "true"],
            ":TRIGger:HFReject ON",
            {"enabled": True},
        ),
        (
            ["trigger-hf-reject", "--enabled", "false"],
            ":TRIGger:HFReject OFF",
            {"enabled": False},
        ),
    ],
)
def test_trigger_common_configure_dry_run_json(
    capsys, args, expected_command, expected_result
):
    assert cli.main([*args, "--dry-run", "--json", "--model", "DSOX4024A"]) == 0

    payload = _json_stdout(capsys)
    assert payload["result"]["operation"] == "configure"
    assert payload["result"]["command"] == expected_command
    assert payload["result"]["state_changing"] is True
    for key, value in expected_result.items():
        assert payload["result"][key] == value
    assert payload["scpi"]["planned"] == [expected_command, ":SYSTem:ERRor?"]


@pytest.mark.parametrize(
    "command, expected_result, expected_sent",
    [
        (
            "trigger-sweep",
            {"mode": "auto", "raw_value": "AUTO"},
            ["*IDN?", ":TRIGger:SWEep?", ":SYSTem:ERRor?"],
        ),
        (
            "trigger-noise-reject",
            {"enabled": False, "raw_value": "0"},
            ["*IDN?", ":TRIGger:NREJect?", ":SYSTem:ERRor?"],
        ),
        (
            "trigger-hf-reject",
            {"enabled": False, "raw_value": "0"},
            ["*IDN?", ":TRIGger:HFReject?", ":SYSTem:ERRor?"],
        ),
    ],
)
def test_trigger_common_query_simulate_json(
    capsys, command, expected_result, expected_sent
):
    assert cli.main([command, "--simulate", "--json", "--model", "DSOX4024A", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "query"
    for key, value in expected_result.items():
        assert payload["result"][key] == value
    assert payload["scpi"]["sent"] == expected_sent


@pytest.mark.parametrize(
    "args, expected_sent",
    [
        (
            ["trigger-sweep", "--mode", "normal"],
            ["*IDN?", ":TRIGger:SWEep NORMal", ":SYSTem:ERRor?"],
        ),
        (
            ["trigger-noise-reject", "--enabled", "true"],
            ["*IDN?", ":TRIGger:NREJect ON", ":SYSTem:ERRor?"],
        ),
        (
            ["trigger-noise-reject", "--enabled", "false"],
            ["*IDN?", ":TRIGger:NREJect OFF", ":SYSTem:ERRor?"],
        ),
        (
            ["trigger-hf-reject", "--enabled", "true"],
            ["*IDN?", ":TRIGger:HFReject ON", ":SYSTem:ERRor?"],
        ),
        (
            ["trigger-hf-reject", "--enabled", "false"],
            ["*IDN?", ":TRIGger:HFReject OFF", ":SYSTem:ERRor?"],
        ),
    ],
)
def test_trigger_common_configure_simulate_json(capsys, args, expected_sent):
    assert cli.main([*args, "--simulate", "--json", "--model", "DSOX4024A"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "configure"
    assert payload["scpi"]["sent"] == expected_sent


@pytest.mark.parametrize(
    "args, expected_message",
    [
        (
            ["trigger-sweep", "--query", "--mode", "auto"],
            "cannot be combined",
        ),
        (
            ["trigger-noise-reject", "--query", "--enabled", "true"],
            "cannot be combined",
        ),
        (
            ["trigger-hf-reject", "--query", "--enabled", "false"],
            "cannot be combined",
        ),
        (["trigger-sweep"], "configure requires --mode"),
        (["trigger-noise-reject"], "configure requires --enabled"),
        (["trigger-hf-reject"], "configure requires --enabled"),
    ],
)
def test_trigger_common_validation_errors_are_json(capsys, args, expected_message):
    assert cli.main([*args, "--dry-run", "--json", "--model", "DSOX4024A"]) == 1

    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert expected_message in payload["error"]["message"]


@pytest.mark.parametrize(
    "args",
    [
        ["trigger-sweep", "--mode", "single", "--dry-run", "--json"],
        ["trigger-noise-reject", "--enabled", "yes", "--dry-run", "--json"],
        ["trigger-hf-reject", "--enabled", "1", "--dry-run", "--json"],
    ],
)
def test_trigger_common_invalid_values_fail_argparse(capsys, args):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(args)

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid choice" in captured.err or "must be true or false" in captured.err
