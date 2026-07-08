import json

import pytest

from keysight_scope_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_trigger_edge_query_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-edge",
                "--dry-run",
                "--json",
                "--model",
                "DSOX4024A",
                "--query",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["command"] == "trigger-edge"
    assert payload["result"] == {
        "operation": "query",
        "commands": [
            ":TRIGger:EDGE:SOURce?",
            ":TRIGger:EDGE:LEVel?",
            ":TRIGger:EDGE:SLOPe?",
        ],
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_edge_configure_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-edge",
                "--dry-run",
                "--json",
                "--model",
                "DSOX4024A",
                "--source-channel",
                "1",
                "--level",
                "0.5",
                "--slope",
                "positive",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["command"] == "trigger-edge"
    assert payload["result"] == {
        "operation": "set",
        "commands": [
            ":TRIGger:MODE EDGE",
            ":TRIGger:EDGE:SOURce CHANnel1",
            ":TRIGger:EDGE:LEVel 0.5",
            ":TRIGger:EDGE:SLOPe POSitive",
        ],
        "source_channel": 1,
        "level_volts": 0.5,
        "slope": "POSitive",
    }


def test_trigger_edge_query_simulate_json(capsys):
    assert cli.main(["trigger-edge", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["command"] == "trigger-edge"
    assert payload["result"]["operation"] == "query"
    assert payload["result"]["source_channel"] == 1
    assert payload["result"]["level_volts"] == 0.0
    assert payload["result"]["slope"] == "positive"
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:SLOPe?",
        ":SYSTem:ERRor?",
    ]


def test_trigger_edge_configure_simulate_json(capsys):
    assert (
        cli.main(
            [
                "trigger-edge",
                "--simulate",
                "--json",
                "--model",
                "DSOX4024A",
                "--source-channel",
                "1",
                "--level",
                "0.5",
                "--slope",
                "positive",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["command"] == "trigger-edge"
    assert payload["result"]["source_channel"] == 1
    assert payload["result"]["level_volts"] == 0.5
    assert payload["result"]["slope"] == "POSitive"
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE EDGE",
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel 0.5",
        ":TRIGger:EDGE:SLOPe POSitive",
        ":SYSTem:ERRor?",
    ]


def test_trigger_edge_query_rejects_configure_options(capsys):
    assert (
        cli.main(
            [
                "trigger-edge",
                "--dry-run",
                "--json",
                "--query",
                "--source-channel",
                "1",
            ]
        )
        == 1
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert "cannot be combined" in payload["error"]["message"]


def test_trigger_edge_configure_rejects_missing_required_option(capsys):
    assert (
        cli.main(
            [
                "trigger-edge",
                "--dry-run",
                "--json",
                "--source-channel",
                "1",
                "--level",
                "0.5",
            ]
        )
        == 1
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert "requires --source-channel, --level, and --slope" in payload["error"]["message"]


def test_legacy_edge_trigger_command_is_not_accepted(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["edge-trigger", "--dry-run", "--json", "--query"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err
