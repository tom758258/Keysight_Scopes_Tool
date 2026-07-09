import json

import pytest

from keysight_scope_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_trigger_delay_query_dry_run_text_does_not_open_visa(capsys):
    assert (
        cli.main(
            [
                "trigger-delay",
                "--dry-run",
                "--model",
                "DSOX4034A",
                "--query",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Resource: DRY::DSOX4034A::INSTR" in captured.out
    assert "Command: :TRIGger:MODE?" in captured.out
    assert "Command: :TRIGger:DELay:ARM:SOURce?" in captured.out
    assert "Failed to open VISA resource" not in captured.out
    assert "VI_ERROR_INV_RSRC_NAME" not in captured.out


def test_trigger_delay_query_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-delay",
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
    assert payload["result"] == {
        "operation": "query",
        "commands": [
            ":TRIGger:MODE?",
            ":TRIGger:DELay:ARM:SOURce?",
            ":TRIGger:DELay:ARM:SLOPe?",
            ":TRIGger:DELay:TDELay:TIME?",
            ":TRIGger:DELay:TRIGger:COUNt?",
            ":TRIGger:DELay:TRIGger:SOURce?",
            ":TRIGger:DELay:TRIGger:SLOPe?",
        ],
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_delay_configure_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-delay",
                "--dry-run",
                "--json",
                "--model",
                "DSOX4024A",
                "--arm-channel",
                "1",
                "--arm-slope",
                "positive",
                "--trigger-channel",
                "2",
                "--trigger-slope",
                "negative",
                "--time-seconds",
                "1e-6",
                "--count",
                "2",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["result"] == {
        "operation": "set",
        "commands": [
            ":TRIGger:MODE DELay",
            ":TRIGger:DELay:ARM:SOURce CHANnel1",
            ":TRIGger:DELay:ARM:SLOPe POSitive",
            ":TRIGger:DELay:TDELay:TIME 1e-06",
            ":TRIGger:DELay:TRIGger:COUNt 2",
            ":TRIGger:DELay:TRIGger:SOURce CHANnel2",
            ":TRIGger:DELay:TRIGger:SLOPe NEGative",
        ],
        "arm_channel": 1,
        "arm_source": "CHANnel1",
        "arm_slope": "positive",
        "trigger_channel": 2,
        "trigger_source": "CHANnel2",
        "trigger_slope": "negative",
        "time_seconds": 1e-6,
        "count": 2,
        "state_changing": True,
    }


def test_trigger_delay_query_simulate_json(capsys):
    assert cli.main(["trigger-delay", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["mode"] == "edge"
    assert payload["result"]["arm_source"] == "CHAN1"
    assert payload["result"]["arm_channel"] == 1
    assert payload["result"]["arm_slope"] == "positive"
    assert payload["result"]["trigger_source"] == "CHAN1"
    assert payload["result"]["trigger_channel"] == 1
    assert payload["result"]["trigger_slope"] == "positive"
    assert payload["result"]["time_seconds"] == 1e-6
    assert payload["result"]["count"] == 2
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE?",
        ":TRIGger:DELay:ARM:SOURce?",
        ":TRIGger:DELay:ARM:SLOPe?",
        ":TRIGger:DELay:TDELay:TIME?",
        ":TRIGger:DELay:TRIGger:COUNt?",
        ":TRIGger:DELay:TRIGger:SOURce?",
        ":TRIGger:DELay:TRIGger:SLOPe?",
        ":SYSTem:ERRor?",
    ]


def test_trigger_delay_configure_simulate_json(capsys):
    assert (
        cli.main(
            [
                "trigger-delay",
                "--simulate",
                "--json",
                "--arm-channel",
                "1",
                "--arm-slope",
                "positive",
                "--trigger-channel",
                "2",
                "--trigger-slope",
                "negative",
                "--time-seconds",
                "1e-6",
                "--count",
                "2",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["result"]["state_changing"] is True
    assert payload["result"]["commands"] == [
        ":TRIGger:MODE DELay",
        ":TRIGger:DELay:ARM:SOURce CHANnel1",
        ":TRIGger:DELay:ARM:SLOPe POSitive",
        ":TRIGger:DELay:TDELay:TIME 1e-06",
        ":TRIGger:DELay:TRIGger:COUNt 2",
        ":TRIGger:DELay:TRIGger:SOURce CHANnel2",
        ":TRIGger:DELay:TRIGger:SLOPe NEGative",
    ]
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        *payload["result"]["commands"],
        ":SYSTem:ERRor?",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["trigger-delay", "--dry-run", "--json"],
        [
            "trigger-delay",
            "--query",
            "--arm-channel",
            "1",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-delay",
            "--arm-channel",
            "1",
            "--arm-slope",
            "positive",
            "--trigger-channel",
            "2",
            "--trigger-slope",
            "negative",
            "--time-seconds",
            "3e-9",
            "--count",
            "2",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-delay",
            "--arm-channel",
            "1",
            "--arm-slope",
            "positive",
            "--trigger-channel",
            "2",
            "--trigger-slope",
            "negative",
            "--dry-run",
            "--json",
        ],
    ],
)
def test_trigger_delay_rejects_invalid_arguments(argv, capsys):
    assert cli.main(argv) == 1
    payload = _json_stdout(capsys)
    assert payload["ok"] is False


def test_trigger_delay_rejects_invalid_two_channel_source_before_access(capsys):
    assert (
        cli.main(
            [
                "trigger-delay",
                "--model",
                "DSOX4022A",
                "--arm-channel",
                "1",
                "--arm-slope",
                "positive",
                "--trigger-channel",
                "3",
                "--trigger-slope",
                "negative",
                "--time-seconds",
                "1e-6",
                "--count",
                "2",
                "--dry-run",
                "--json",
            ]
        )
        == 1
    )
    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["scpi"]["sent"] == []


def test_trigger_delay_argparse_rejects_invalid_count():
    with pytest.raises(SystemExit):
        cli.main(
            [
                "trigger-delay",
                "--arm-channel",
                "1",
                "--arm-slope",
                "positive",
                "--trigger-channel",
                "2",
                "--trigger-slope",
                "negative",
                "--time-seconds",
                "1e-6",
                "--count",
                "0",
                "--dry-run",
                "--json",
            ]
        )


def test_trigger_delay_rejects_invalid_slope_choice():
    with pytest.raises(SystemExit):
        cli.main(
            [
                "trigger-delay",
                "--arm-channel",
                "1",
                "--arm-slope",
                "rising",
                "--trigger-channel",
                "2",
                "--trigger-slope",
                "negative",
                "--time-seconds",
                "1e-6",
                "--count",
                "2",
                "--dry-run",
                "--json",
            ]
        )


def test_trigger_delay_log_scpi_keeps_json_on_stdout(capsys):
    assert (
        cli.main(["trigger-delay", "--simulate", "--json", "--log-scpi", "--query"])
        == 0
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["result"]["human_output"]
    assert ":TRIGger:DELay:ARM:SOURce?" in payload["scpi"]["sent"]
