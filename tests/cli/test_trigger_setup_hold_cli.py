import json

import pytest

from scopes_tool_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_trigger_setup_hold_query_dry_run_text_does_not_open_visa(capsys):
    assert (
        cli.main(
            [
                "trigger-setup-hold",
                "--dry-run",
                "--model",
                "keysight-dsox4034a",
                "--query",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Resource: DRY::keysight-dsox4034a::INSTR" in captured.out
    assert "Command: :TRIGger:MODE?" in captured.out
    assert "Command: :TRIGger:SHOLd:SOURce:CLOCk?" in captured.out
    assert "Failed to open VISA resource" not in captured.out
    assert "VI_ERROR_INV_RSRC_NAME" not in captured.out


def test_trigger_setup_hold_query_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-setup-hold",
                "--dry-run",
                "--json",
                "--model",
                "keysight-dsox4024a",
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
            ":TRIGger:SHOLd:SOURce:CLOCk?",
            ":TRIGger:SHOLd:SOURce:DATA?",
            ":TRIGger:SHOLd:SLOPe?",
            ":TRIGger:SHOLd:TIME:SETup?",
            ":TRIGger:SHOLd:TIME:HOLD?",
        ],
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_setup_hold_configure_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-setup-hold",
                "--dry-run",
                "--json",
                "--model",
                "keysight-dsox4024a",
                "--clock-channel",
                "1",
                "--data-channel",
                "2",
                "--slope",
                "positive",
                "--setup-time",
                "1e-9",
                "--hold-time",
                "1e-9",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["result"] == {
        "operation": "configure",
        "mode": "setup-hold",
        "commands": [
            ":TRIGger:MODE SHOLd",
            ":TRIGger:SHOLd:SOURce:CLOCk CHANnel1",
            ":TRIGger:SHOLd:SOURce:DATA CHANnel2",
            ":TRIGger:SHOLd:SLOPe POSitive",
            ":TRIGger:SHOLd:TIME:SETup 1e-09",
            ":TRIGger:SHOLd:TIME:HOLD 1e-09",
        ],
        "clock_source": "CHANnel1",
        "clock_channel": 1,
        "clock_source_kind": "channel",
        "data_source": "CHANnel2",
        "data_channel": 2,
        "data_source_kind": "channel",
        "slope": "positive",
        "setup_time_seconds": 1e-9,
        "hold_time_seconds": 1e-9,
        "state_changing": True,
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_setup_hold_configure_simulate_json(capsys):
    assert (
        cli.main(
            [
                "trigger-setup-hold",
                "--simulate",
                "--json",
                "--clock-channel",
                "1",
                "--data-channel",
                "2",
                "--slope",
                "negative",
                "--setup-time",
                "1e-9",
                "--hold-time",
                "2e-9",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["state_changing"] is True
    assert payload["result"]["commands"] == [
        ":TRIGger:MODE SHOLd",
        ":TRIGger:SHOLd:SOURce:CLOCk CHANnel1",
        ":TRIGger:SHOLd:SOURce:DATA CHANnel2",
        ":TRIGger:SHOLd:SLOPe NEGative",
        ":TRIGger:SHOLd:TIME:SETup 1e-09",
        ":TRIGger:SHOLd:TIME:HOLD 2e-09",
    ]
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        *payload["result"]["commands"],
        ":SYSTem:ERRor?",
    ]


def test_trigger_setup_hold_configure_then_query_simulate_json(capsys):
    assert (
        cli.main(
            [
                "trigger-setup-hold",
                "--simulate",
                "--json",
                "--clock-channel",
                "1",
                "--data-channel",
                "2",
                "--slope",
                "positive",
                "--setup-time",
                "1e-9",
                "--hold-time",
                "1e-9",
            ]
        )
        == 0
    )
    _json_stdout(capsys)

    assert cli.main(["trigger-setup-hold", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["mode"] == "edge"
    assert payload["result"]["clock_source"] == "CHAN1"
    assert payload["result"]["clock_channel"] == 1
    assert payload["result"]["data_source"] == "CHAN2"
    assert payload["result"]["data_channel"] == 2
    assert payload["result"]["slope"] == "positive"
    assert payload["result"]["setup_time_seconds"] == 1e-9
    assert payload["result"]["hold_time_seconds"] == 1e-9
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE?",
        ":TRIGger:SHOLd:SOURce:CLOCk?",
        ":TRIGger:SHOLd:SOURce:DATA?",
        ":TRIGger:SHOLd:SLOPe?",
        ":TRIGger:SHOLd:TIME:SETup?",
        ":TRIGger:SHOLd:TIME:HOLD?",
        ":SYSTem:ERRor?",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["trigger-setup-hold", "--dry-run", "--json"],
        [
            "trigger-setup-hold",
            "--query",
            "--clock-channel",
            "1",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-setup-hold",
            "--clock-channel",
            "1",
            "--data-channel",
            "2",
            "--slope",
            "positive",
            "--setup-time",
            "1e-9",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-setup-hold",
            "--model",
            "keysight-dsox4024a",
            "--clock-channel",
            "1",
            "--data-channel",
            "5",
            "--slope",
            "positive",
            "--setup-time",
            "1e-9",
            "--hold-time",
            "1e-9",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-setup-hold",
            "--clock-channel",
            "1",
            "--data-channel",
            "2",
            "--slope",
            "positive",
            "--setup-time",
            "0",
            "--hold-time",
            "1e-9",
            "--dry-run",
            "--json",
        ],
    ],
)
def test_trigger_setup_hold_rejects_invalid_arguments(argv, capsys):
    assert cli.main(argv) == 1
    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["scpi"]["sent"] == []


@pytest.mark.parametrize("channel", ["D0", "DIG0", "digital0", "pod", "bus", "1.5"])
def test_trigger_setup_hold_argparse_rejects_source_aliases(channel):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "trigger-setup-hold",
                "--clock-channel",
                channel,
                "--data-channel",
                "2",
                "--slope",
                "positive",
                "--setup-time",
                "1e-9",
                "--hold-time",
                "1e-9",
                "--dry-run",
                "--json",
            ]
        )


def test_trigger_setup_hold_rejects_invalid_slope_before_access(capsys):
    assert (
        cli.main(
            [
                "trigger-setup-hold",
                "--clock-channel",
                "1",
                "--data-channel",
                "2",
                "--slope",
                "rising",
                "--setup-time",
                "1e-9",
                "--hold-time",
                "1e-9",
                "--dry-run",
                "--json",
            ]
        )
        == 1
    )
    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["scpi"]["sent"] == []


def test_trigger_setup_hold_log_scpi_keeps_json_on_stdout(capsys):
    assert (
        cli.main(["trigger-setup-hold", "--simulate", "--json", "--log-scpi", "--query"])
        == 0
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["result"]["human_output"]
    assert ":TRIGger:SHOLd:SOURce:CLOCk?" in payload["scpi"]["sent"]
