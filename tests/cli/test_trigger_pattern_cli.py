import json

import pytest

from scopes_tool_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_trigger_pattern_configure_dry_run_json(capsys):
    assert (
        cli.main(["trigger-pattern", "--dry-run", "--json", "--pattern", "xxx1"])
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"] == {
        "operation": "set",
        "commands": [
            ":TRIGger:MODE PATTern",
            ":TRIGger:PATTern:FORMat ASCii",
            ':TRIGger:PATTern "XXX1"',
            ":TRIGger:PATTern:QUALifier ENTered",
        ],
        "mode": "pattern",
        "format": "ascii",
        "pattern": "XXX1",
        "qualifier": "entered",
        "state_changing": True,
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_pattern_query_dry_run_json(capsys):
    assert cli.main(["trigger-pattern", "--dry-run", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"] == {
        "operation": "query",
        "commands": [
            ":TRIGger:MODE?",
            ":TRIGger:PATTern:FORMat?",
            ":TRIGger:PATTern?",
            ":TRIGger:PATTern:QUALifier?",
        ],
    }


def test_trigger_pattern_configure_simulate_json(capsys):
    assert (
        cli.main(["trigger-pattern", "--simulate", "--json", "--pattern", "XXX1"])
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "set"
    assert payload["result"]["mode"] == "pattern"
    assert payload["result"]["format"] == "ascii"
    assert payload["result"]["pattern"] == "XXX1"
    assert payload["result"]["qualifier"] == "entered"
    assert payload["files"] == []
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE PATTern",
        ":TRIGger:PATTern:FORMat ASCii",
        ':TRIGger:PATTern "XXX1"',
        ":TRIGger:PATTern:QUALifier ENTered",
        ":SYSTem:ERRor?",
    ]


def test_trigger_pattern_query_simulate_json(capsys):
    assert cli.main(["trigger-pattern", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "query"
    assert payload["result"]["mode"] == "edge"
    assert payload["result"]["format"] == "ascii"
    assert payload["result"]["pattern"] == "XXXX"
    assert payload["result"]["qualifier"] == "entered"
    assert payload["result"]["edge_source_raw"] == "NONE"
    assert payload["result"]["edge_raw"] == "POS"
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE?",
        ":TRIGger:PATTern:FORMat?",
        ":TRIGger:PATTern?",
        ":TRIGger:PATTern:QUALifier?",
        ":SYSTem:ERRor?",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["trigger-pattern", "--query", "--pattern", "XXX1", "--dry-run", "--json"],
        ["trigger-pattern", "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", "", "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", "XX,X", "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", 'XX"X', "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", "XXXR", "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", "XXXF", "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", "0x01", "--dry-run", "--json"],
        ["trigger-pattern", "--pattern", "XXY1", "--dry-run", "--json"],
    ],
)
def test_trigger_pattern_rejects_invalid_arguments(argv, capsys):
    assert cli.main(argv) == 1
    payload = _json_stdout(capsys)
    assert payload["ok"] is False


def test_trigger_pattern_rejects_unsupported_options():
    with pytest.raises(SystemExit):
        cli.main(["trigger-pattern", "--source", "CHANnel1", "--dry-run", "--json"])


def test_trigger_pattern_does_not_emit_acquisition_or_capture_scpi(capsys):
    assert (
        cli.main(["trigger-pattern", "--pattern", "XXX1", "--dry-run", "--json"])
        == 0
    )

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
