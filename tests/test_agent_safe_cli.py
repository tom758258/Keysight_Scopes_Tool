import json

from keysight_scope import cli
from keysight_scope.errors import KeysightScopeError
from keysight_scope.simulator_backend import SimulatorBackend


def _json_stdout(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_verify_simulate_json_uses_simulator_without_resource(capsys):
    assert cli.main(["verify", "--simulate", "--json"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["command"] == "verify"
    assert payload["mode"] == "simulate"
    assert payload["resource"] == "SIM::DSOX4024A::INSTR"
    assert payload["backend"] == "Keysight simulator"
    assert payload["idn"]["model"] == "DSOX4024A"
    assert payload["capabilities"]["analog_channels"] == 4
    assert payload["scpi"]["sent"] == ["*IDN?"]


def test_verify_dry_run_json_does_not_open_scope(monkeypatch, capsys):
    def fail_open(resource, visa_library=None):
        del resource, visa_library
        raise AssertionError("dry-run must not open a VISA scope")

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fail_open))

    assert cli.main(["verify", "--dry-run", "--json", "--model", "DSOX4024A"]) == 0

    payload = _json_stdout(capsys)
    assert payload["ok"] is True
    assert payload["mode"] == "dry_run"
    assert payload["scpi"]["planned"] == ["*IDN?"]
    assert payload["scpi"]["sent"] == []


def test_capture_dry_run_json_reports_files_without_writing(monkeypatch, capsys, tmp_path):
    def fail_open(resource, visa_library=None):
        del resource, visa_library
        raise AssertionError("dry-run must not open a VISA scope")

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fail_open))
    csv_path = tmp_path / "capture.csv"

    assert (
        cli.main(
            [
                "capture",
                "--dry-run",
                "--json",
                "--channel",
                "1",
                "--csv",
                str(csv_path),
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    assert payload["mode"] == "dry_run"
    assert payload["files"] == [
        {"kind": "csv", "path": str(csv_path)},
        {"kind": "metadata", "path": str(csv_path.with_name("capture_meta.json"))},
    ]
    assert not csv_path.exists()
    assert payload["scpi"]["planned"][-1] == ":SYSTem:ERRor?"


def test_simulate_json_error_is_single_json_object(capsys):
    assert (
        cli.main(
            [
                "measure",
                "--simulate",
                "--json",
                "--model",
                "DSOX4022A",
                "--channel",
                "3",
                "--item",
                "vpp",
            ]
        )
        == 1
    )

    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["mode"] == "simulate"
    assert "channel 3 is not available" in payload["error"]["message"]


def test_simulate_json_backend_error_keeps_single_json_object(monkeypatch, capsys):
    backend = SimulatorBackend(
        query_failures={
            ":MEASure:VPP? CHANnel1": KeysightScopeError("configured measurement failure")
        }
    )
    monkeypatch.setattr(cli, "SimulatorBackend", lambda **kwargs: backend)

    assert cli.main(["measure", "--simulate", "--json", "--channel", "1", "--item", "vpp"]) == 1

    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["mode"] == "simulate"
    assert payload["error"]["message"] == "configured measurement failure"
    assert payload["scpi"]["sent"] == ["*IDN?", ":MEASure:VPP? CHANnel1"]


def test_check_error_simulate_json_can_report_injected_error_queue(monkeypatch, capsys):
    backend = SimulatorBackend(system_errors=['-113,"Undefined header"'])
    monkeypatch.setattr(cli, "SimulatorBackend", lambda **kwargs: backend)

    assert cli.main(["check-error", "--simulate", "--json", "--all", "--max-reads", "3"]) == 1

    payload = _json_stdout(capsys)
    assert payload["ok"] is False
    assert payload["mode"] == "simulate"
    assert payload["result"]["entries"] == [
        {
            "code": -113,
            "is_error": True,
            "message": "Undefined header",
            "raw": '-113,"Undefined header"',
        },
        {
            "code": 0,
            "is_error": False,
            "message": "No error",
            "raw": '+0,"No error"',
        },
    ]
    assert payload["system_error"]["code"] == 0
    assert payload["scpi"]["sent"] == [":SYSTem:ERRor?", ":SYSTem:ERRor?"]



def test_control_simulate_json_reports_action_and_system_error(capsys):
    assert cli.main(["run", "--simulate", "--json"]) == 0

    payload = _json_stdout(capsys)
    assert payload["result"]["action"] == "run"
    assert payload["result"]["command"] == ":RUN"
    assert payload["system_error"]["code"] == 0
    assert payload["result"]["human_output"]


def test_channel_timebase_trigger_json_results(capsys):
    assert cli.main(["channel-scale", "--simulate", "--json", "--channel", "1", "--volts-per-division", "0.5"]) == 0
    channel_payload = _json_stdout(capsys)
    assert channel_payload["result"]["operation"] == "set"
    assert channel_payload["result"]["channel"] == 1
    assert channel_payload["result"]["volts_per_division"] == 0.5

    assert cli.main(["timebase-position", "--simulate", "--json", "--seconds", "0.001"]) == 0
    timebase_payload = _json_stdout(capsys)
    assert timebase_payload["result"]["operation"] == "set"
    assert timebase_payload["result"]["position_seconds"] == 0.001

    assert cli.main(["edge-trigger", "--simulate", "--json", "--source-channel", "1", "--level", "0.2", "--slope", "positive"]) == 0
    trigger_payload = _json_stdout(capsys)
    assert trigger_payload["result"]["source_channel"] == 1
    assert trigger_payload["result"]["level_volts"] == 0.2
    assert trigger_payload["result"]["slope"] == "POSitive"


def test_measure_simulate_json_reports_measurement_fields(capsys):
    assert cli.main(["measure", "--simulate", "--json", "--channel", "1", "--item", "vpp"]) == 0

    payload = _json_stdout(capsys)
    result = payload["result"]
    assert result["item"] == "vpp"
    assert result["channel"] == 1
    assert result["valid"] is True
    assert result["value"] == 0.5
    assert result["unit"] == "V"
    assert result["raw_value"] == "5.000000E-01"
    assert result["parameters"] == {}
    assert payload["system_error"]["is_error"] is False


def test_measure_pair_phase_simulate_json_uses_signal_model(capsys):
    assert (
        cli.main(
            [
                "measure",
                "--simulate",
                "--json",
                "--source-channel",
                "1",
                "--reference-channel",
                "2",
                "--item",
                "phase",
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    result = payload["result"]
    assert result["item"] == "phase"
    assert result["channel"] == 1
    assert result["reference_channel"] == 2
    assert result["valid"] is True
    assert result["value"] == 45.0
    assert result["unit"] == "deg"


def test_measure_simulate_json_reports_invalid_sentinel(monkeypatch, capsys):
    backend = SimulatorBackend(invalid_measurement_channels={1})
    monkeypatch.setattr(cli, "SimulatorBackend", lambda **kwargs: backend)

    assert cli.main(["measure", "--simulate", "--json", "--channel", "1", "--item", "vpp"]) == 1

    payload = _json_stdout(capsys)
    result = payload["result"]
    assert payload["ok"] is False
    assert result["valid"] is False
    assert result["value"] is None
    assert result["raw_value"] == "9.9E+37"
    assert result["reason"] == "invalid measurement sentinel"


def test_capture_simulate_json_reports_files_and_summaries(capsys, tmp_path):
    csv_path = tmp_path / "capture.csv"

    assert (
        cli.main(
            [
                "capture",
                "--simulate",
                "--json",
                "--channel",
                "1",
                "--points",
                "5000",
                "--csv",
                str(csv_path),
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    result = payload["result"]
    assert payload["files"] == [
        {"kind": "csv", "path": str(csv_path)},
        {"kind": "metadata", "path": str(csv_path.with_name("capture_meta.json"))},
    ]
    assert result["requested_points"] == 5000
    assert result["actual_points"] == 5000
    assert result["captures"][0]["channel"] == 1
    assert "raw_samples" not in result["captures"][0]
    assert result["captures"][0]["preamble"]["points"] == 5000


def test_screenshot_simulate_json_reports_png_metadata(capsys, tmp_path):
    png_path = tmp_path / "screen.png"

    assert cli.main(["screenshot", "--simulate", "--json", "--output", str(png_path)]) == 0

    payload = _json_stdout(capsys)
    result = payload["result"]
    assert payload["files"] == [{"kind": "png", "path": str(png_path)}]
    assert result["format"] == "PNG"
    assert result["background"] == "black"
    assert result["byte_count"] > 0
    assert result["png_path"] == str(png_path)


def test_capture_batch_simulate_json_reports_manifest_and_entries(capsys, tmp_path):
    output_dir = tmp_path / "batch"

    assert (
        cli.main(
            [
                "capture-batch",
                "--simulate",
                "--json",
                "--channel",
                "1",
                "--count",
                "2",
                "--points",
                "10000",
                "--format",
                "word",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    payload = _json_stdout(capsys)
    result = payload["result"]
    assert result["status"] == "completed"
    assert result["requested_count"] == 2
    assert result["completed_count"] == 2
    assert result["manifest_path"] == str(output_dir / "manifest.json")
    assert result["scpi_log_path"] == str(output_dir / "scpi.log")
    assert len(result["captures"]) == 2
    assert result["captures"][0]["actual_points"] == {"CH1": 10000}
    assert {item["kind"] for item in payload["files"]} >= {"manifest", "scpi_log", "csv", "metadata"}


def test_acquisition_dry_run_json_reports_structured_plan(capsys):
    assert cli.main(["acquisition", "--dry-run", "--json", "--type", "average", "--count", "16"]) == 0

    payload = _json_stdout(capsys)
    assert payload["result"]["operation"] == "set"
    assert payload["result"]["scpi_type"] == "AVERage"
    assert payload["result"]["count"] == 16
    assert payload["scpi"]["planned"] == [":ACQuire:TYPE AVERage", ":ACQuire:COUNt 16", ":SYSTem:ERRor?"]
