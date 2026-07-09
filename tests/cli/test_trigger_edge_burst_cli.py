import json

import pytest

from keysight_scope_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def _text_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def test_trigger_edge_burst_query_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
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
            ":TRIGger:EBURst:SOURce?",
            ":TRIGger:EBURst:SLOPe?",
            ":TRIGger:EBURst:COUNt?",
            ":TRIGger:EBURst:IDLE?",
            ":TRIGger:EDGE:LEVel? CHANnel1",
        ],
    }
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_edge_burst_query_dry_run_text(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--model",
                "DSOX4034A",
                "--query",
                "--dry-run",
            ]
        )
        == 0
    )

    output = _text_stdout(capsys)
    assert "Resource: DRY::DSOX4034A::INSTR" in output
    assert "Model: DSOX4034A" in output
    assert "Series: 4000X" in output
    assert "Planned query: Nth Edge Burst trigger state" in output
    assert "Command: :TRIGger:MODE?" in output
    assert "Command: :TRIGger:EBURst:SOURce?" in output
    assert "Command: :TRIGger:EBURst:SLOPe?" in output
    assert "Command: :TRIGger:EBURst:COUNt?" in output
    assert "Command: :TRIGger:EBURst:IDLE?" in output
    assert "Command: :TRIGger:EDGE:LEVel? CHANnel1" in output
    assert "Failed to open VISA resource" not in output
    assert "VI_ERROR_INV_RSRC_NAME" not in output
    assert "Mode:" not in output
    assert "Source:" not in output
    assert "Count:" not in output
    assert "Level V:" not in output
    assert ":SYSTem:ERRor?" not in output


def test_trigger_edge_burst_configure_dry_run_json_without_level(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--dry-run",
                "--json",
                "--model",
                "DSOX4024A",
                "--source-channel",
                "1",
                "--slope",
                "positive",
                "--count",
                "3",
                "--idle-time",
                "1e-6",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["result"] == {
        "operation": "configure",
        "mode": "edge-burst",
        "commands": [
            ":TRIGger:MODE EBURst",
            ":TRIGger:EBURst:SOURce CHANnel1",
            ":TRIGger:EBURst:SLOPe POSitive",
            ":TRIGger:EBURst:COUNt 3",
            ":TRIGger:EBURst:IDLE 1e-06",
        ],
        "source_channel": 1,
        "source": "CHANnel1",
        "slope": "positive",
        "count": 3,
        "idle_time": 1e-6,
        "state_changing": True,
    }


def test_trigger_edge_burst_configure_dry_run_text_without_level(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--model",
                "DSOX4034A",
                "--source-channel",
                "2",
                "--slope",
                "negative",
                "--count",
                "5",
                "--idle-time",
                "1e-5",
                "--dry-run",
            ]
        )
        == 0
    )

    output = _text_stdout(capsys)
    assert "Planned change: Nth Edge Burst trigger CH2, negative, count 5" in output
    assert "Command: :TRIGger:MODE EBURst" in output
    assert "Command: :TRIGger:EBURst:SOURce CHANnel2" in output
    assert "Command: :TRIGger:EBURst:SLOPe NEGative" in output
    assert "Command: :TRIGger:EBURst:COUNt 5" in output
    assert "Command: :TRIGger:EBURst:IDLE 1e-05" in output
    assert ":TRIGger:EDGE:LEVel" not in output
    assert "Failed to open VISA resource" not in output
    assert "VI_ERROR_INV_RSRC_NAME" not in output
    assert ":SYSTem:ERRor?" not in output


def test_trigger_edge_burst_configure_dry_run_json_with_level(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--dry-run",
                "--json",
                "--model",
                "DSOX4024A",
                "--source-channel",
                "1",
                "--slope",
                "negative",
                "--count",
                "5",
                "--idle-time",
                "1e-5",
                "--level-volts",
                "0.5",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["result"]["commands"] == [
        ":TRIGger:MODE EBURst",
        ":TRIGger:EBURst:SOURce CHANnel1",
        ":TRIGger:EBURst:SLOPe NEGative",
        ":TRIGger:EBURst:COUNt 5",
        ":TRIGger:EBURst:IDLE 1e-05",
        ":TRIGger:EDGE:LEVel 0.5, CHANnel1",
    ]
    assert payload["result"]["slope"] == "negative"
    assert payload["result"]["level_volts"] == 0.5


def test_trigger_edge_burst_configure_dry_run_text_with_level(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--model",
                "DSOX4034A",
                "--source-channel",
                "1",
                "--slope",
                "positive",
                "--count",
                "3",
                "--idle-time",
                "1e-6",
                "--level-volts",
                "0.5",
                "--dry-run",
            ]
        )
        == 0
    )

    output = _text_stdout(capsys)
    assert "Resource: DRY::DSOX4034A::INSTR" in output
    assert "Model: DSOX4034A" in output
    assert "Series: 4000X" in output
    assert "Planned change: Nth Edge Burst trigger CH1, positive, count 3" in output
    assert "Command: :TRIGger:MODE EBURst" in output
    assert "Command: :TRIGger:EBURst:SOURce CHANnel1" in output
    assert "Command: :TRIGger:EBURst:SLOPe POSitive" in output
    assert "Command: :TRIGger:EBURst:COUNt 3" in output
    assert "Command: :TRIGger:EBURst:IDLE 1e-06" in output
    assert "Command: :TRIGger:EDGE:LEVel 0.5, CHANnel1" in output
    assert "Failed to open VISA resource" not in output
    assert "VI_ERROR_INV_RSRC_NAME" not in output
    assert ":SYSTem:ERRor?" not in output


def test_trigger_edge_burst_query_simulate_json(capsys):
    assert cli.main(["trigger-edge-burst", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["mode"] == "edge"
    assert payload["result"]["source_channel"] == 1
    assert payload["result"]["slope"] == "positive"
    assert payload["result"]["count"] == 3
    assert payload["result"]["idle_time"] == 1e-6
    assert payload["result"]["level_volts"] == 0.0
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE?",
        ":TRIGger:EBURst:SOURce?",
        ":TRIGger:EBURst:SLOPe?",
        ":TRIGger:EBURst:COUNt?",
        ":TRIGger:EBURst:IDLE?",
        ":TRIGger:EDGE:LEVel? CHANnel1",
        ":SYSTem:ERRor?",
    ]


def test_trigger_edge_burst_configure_simulate_json_with_level(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--simulate",
                "--json",
                "--source-channel",
                "1",
                "--slope",
                "positive",
                "--count",
                "3",
                "--idle-time",
                "1e-6",
                "--level-volts",
                "0.5",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["state_changing"] is True
    assert payload["result"]["commands"] == [
        ":TRIGger:MODE EBURst",
        ":TRIGger:EBURst:SOURce CHANnel1",
        ":TRIGger:EBURst:SLOPe POSitive",
        ":TRIGger:EBURst:COUNt 3",
        ":TRIGger:EBURst:IDLE 1e-06",
        ":TRIGger:EDGE:LEVel 0.5, CHANnel1",
    ]
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        *payload["result"]["commands"],
        ":SYSTem:ERRor?",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["trigger-edge-burst", "--dry-run", "--json"],
        [
            "trigger-edge-burst",
            "--query",
            "--source-channel",
            "1",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-edge-burst",
            "--source-channel",
            "1",
            "--slope",
            "positive",
            "--count",
            "3",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-edge-burst",
            "--source-channel",
            "1",
            "--slope",
            "positive",
            "--count",
            "3",
            "--idle-time",
            "9e-9",
            "--dry-run",
            "--json",
        ],
    ],
)
def test_trigger_edge_burst_rejects_invalid_arguments(argv, capsys):
    assert cli.main(argv) == 1
    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["scpi"]["sent"] == []


def test_trigger_edge_burst_text_dry_run_rejects_invalid_channel_before_open(capsys):
    assert (
        cli.main(
            [
                "trigger-edge-burst",
                "--model",
                "DSOX4022A",
                "--source-channel",
                "3",
                "--slope",
                "positive",
                "--count",
                "3",
                "--idle-time",
                "1e-6",
                "--dry-run",
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Failed to open VISA resource" not in captured.err
    assert "VI_ERROR_INV_RSRC_NAME" not in captured.err


@pytest.mark.parametrize(
    "option",
    [
        "--channel",
        "--source",
        "--edge-count",
        "--idle-time-seconds",
        "--time-seconds",
        "--trigger-level",
        "--level",
    ],
)
def test_trigger_edge_burst_rejects_alias_options(option):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "trigger-edge-burst",
                "--source-channel",
                "1",
                "--slope",
                "positive",
                "--count",
                "3",
                "--idle-time",
                "1e-6",
                option,
                "1",
                "--dry-run",
                "--json",
            ]
        )
