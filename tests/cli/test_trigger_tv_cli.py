import json

import pytest

from keysight_scope_cli import cli


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_trigger_tv_query_simulate_json(capsys):
    assert cli.main(["trigger-tv", "--simulate", "--json", "--query"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "query"
    assert payload["result"]["mode"] == "edge"
    assert payload["result"]["source_channel"] == 1
    assert payload["result"]["standard"] == "ntsc"
    assert payload["result"]["tv_mode"] == "field1"
    assert payload["result"]["line"] == 1
    assert payload["result"]["polarity"] == "negative"
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE?",
        ":TRIGger:TV:SOURce?",
        ":TRIGger:TV:STANdard?",
        ":TRIGger:TV:MODE?",
        ":TRIGger:TV:LINE?",
        ":TRIGger:TV:POLarity?",
        ":SYSTem:ERRor?",
    ]


def test_trigger_tv_configure_dry_run_json(capsys):
    assert (
        cli.main(
            [
                "trigger-tv",
                "--dry-run",
                "--json",
                "--model",
                "DSOX4024A",
                "--source-channel",
                "1",
                "--standard",
                "ntsc",
                "--mode",
                "line-field1",
                "--line",
                "20",
                "--polarity",
                "negative",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["result"]["commands"] == [
        ":TRIGger:MODE TV",
        ":TRIGger:TV:SOURce CHANnel1",
        ":TRIGger:TV:STANdard NTSC",
        ":TRIGger:TV:MODE LFIeld1",
        ":TRIGger:TV:LINE 20",
        ":TRIGger:TV:POLarity NEGative",
    ]
    assert payload["scpi"]["planned"] == payload["result"]["commands"] + [
        ":SYSTem:ERRor?"
    ]


def test_trigger_tv_configure_simulate_json(capsys):
    assert (
        cli.main(
            [
                "trigger-tv",
                "--simulate",
                "--json",
                "--source-channel",
                "2",
                "--standard",
                "pal",
                "--mode",
                "line-field2",
                "--line",
                "400",
                "--polarity",
                "positive",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["result"]["source_channel"] == 2
    assert payload["result"]["standard"] == "pal"
    assert payload["result"]["tv_mode"] == "line-field2"
    assert payload["result"]["line"] == 400
    assert payload["result"]["polarity"] == "positive"
    assert payload["scpi"]["sent"] == [
        "*IDN?",
        ":TRIGger:MODE TV",
        ":TRIGger:TV:SOURce CHANnel2",
        ":TRIGger:TV:STANdard PAL",
        ":TRIGger:TV:MODE LFIeld2",
        ":TRIGger:TV:LINE 400",
        ":TRIGger:TV:POLarity POSitive",
        ":SYSTem:ERRor?",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["trigger-tv", "--dry-run", "--json"],
        [
            "trigger-tv",
            "--query",
            "--source-channel",
            "1",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-tv",
            "--source-channel",
            "1",
            "--standard",
            "ntsc",
            "--mode",
            "all-lines",
            "--line",
            "20",
            "--polarity",
            "negative",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-tv",
            "--source-channel",
            "1",
            "--standard",
            "ntsc",
            "--mode",
            "line-field1",
            "--polarity",
            "negative",
            "--dry-run",
            "--json",
        ],
    ],
)
def test_trigger_tv_rejects_invalid_arguments(argv, capsys):
    assert cli.main(argv) == 1
    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["scpi"]["sent"] == []


@pytest.mark.parametrize(
    "argv",
    [
        [
            "trigger-tv",
            "--source-channel",
            "1",
            "--standard",
            "ntsc",
            "--mode",
            "line",
            "--polarity",
            "negative",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-tv",
            "--source-channel",
            "1",
            "--standard",
            "p1080",
            "--mode",
            "field1",
            "--polarity",
            "negative",
            "--dry-run",
            "--json",
        ],
        [
            "trigger-tv",
            "--source-channel",
            "1",
            "--standard",
            "ntsc",
            "--mode",
            "all_fields",
            "--polarity",
            "negative",
            "--dry-run",
            "--json",
        ],
    ],
)
def test_trigger_tv_rejects_unsupported_enum_values(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)
