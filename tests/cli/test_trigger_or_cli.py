import json

import pytest

from scopes_tool_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_trigger_or_configure_dry_run_json(capsys):
    assert cli.main(["trigger-or", "--dry-run", "--json", "--pattern", "xxxr"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["command"] == "trigger-or"
    assert payload["result"] == {
        "operation": "set",
        "commands": [
            ":TRIGger:MODE OR",
            ':TRIGger:OR "XXXR"',
        ],
        "mode": "or",
        "pattern": "XXXR",
        "raw_pattern": "XXXR",
        "state_changing": True,
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_or_query_dry_run_json(capsys):
    assert cli.main(["trigger-or", "--dry-run", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"] == {
        "operation": "query",
        "commands": [
            ":TRIGger:MODE?",
            ":TRIGger:OR?",
        ],
    }


def test_trigger_or_configure_simulate_json(capsys):
    assert cli.main(["trigger-or", "--simulate", "--json", "--pattern", "XXXR"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "set"
    assert payload["result"]["mode"] == "or"
    assert payload["result"]["pattern"] == "XXXR"
    assert payload["result"]["raw_pattern"] == "XXXR"
    assert payload["files"] == []
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE OR",
        ':TRIGger:OR "XXXR"',
        ":SYSTem:ERRor?",
    ]


def test_trigger_or_query_simulate_json(capsys):
    assert cli.main(["trigger-or", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "query"
    assert payload["result"]["mode"] == "edge"
    assert payload["result"]["raw_mode"] == "EDGE"
    assert payload["result"]["pattern"] == "XXXX"
    assert payload["result"]["raw_pattern"] == '"XXXX"'
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE?",
        ":TRIGger:OR?",
        ":SYSTem:ERRor?",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["trigger-or", "--query", "--pattern", "XXXR", "--dry-run", "--json"],
        ["trigger-or", "--dry-run", "--json"],
        ["trigger-or", "--pattern", "", "--dry-run", "--json"],
        ["trigger-or", "--pattern", "XX,R", "--dry-run", "--json"],
        ["trigger-or", "--pattern", 'XX"R', "--dry-run", "--json"],
        ["trigger-or", "--pattern", "XXX0", "--dry-run", "--json"],
        ["trigger-or", "--pattern", "XXX1", "--dry-run", "--json"],
        ["trigger-or", "--pattern", "0x01", "--dry-run", "--json"],
        ["trigger-or", "--pattern", "XXYR", "--dry-run", "--json"],
    ],
)
def test_trigger_or_rejects_invalid_arguments(argv, capsys):
    assert cli.main(argv) == 1
    payload = _json_stdout(capsys)
    assert payload["ok"] is False


def test_trigger_or_rejects_unsupported_options():
    with pytest.raises(SystemExit):
        cli.main(["trigger-or", "--mask", "XXXR", "--dry-run", "--json"])


def test_trigger_or_does_not_emit_acquisition_or_capture_scpi(capsys):
    assert cli.main(["trigger-or", "--pattern", "XXXR", "--dry-run", "--json"]) == 0

    payload = _json_stdout(capsys)
    planned = payload["scpi"]["planned"]
    forbidden = [
        ":RUN",
        ":STOP",
        ":SINGle",
        ":TRIGger:FORCe",
        ":DIGitize",
        ":WAVeform:DATA?",
        ":ACQuire",
        ":CAPTure",
    ]
    for command in forbidden:
        assert all(item != command and not item.startswith(f"{command} ") for item in planned)
