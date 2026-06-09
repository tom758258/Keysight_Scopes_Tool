import json

from keysight_scope_core.operations import (
    AcquisitionCheckRequest,
    CaptureRequest,
    MeasureLogRequest,
    MeasureRequest,
    MeasureSweepRequest,
    SmokeRequest,
    run_acquisition_check,
    run_capture,
    run_doctor,
    run_measure_log,
    run_measure,
    run_measure_sweep,
    run_smoke,
)
from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.simulator_backend import SimulatorBackend


def _scope(model="DSOX4024A", **kwargs):
    return KeysightScope(SimulatorBackend(model=model, resource_name=f"SIM::{model}::INSTR", **kwargs))


def test_run_capture_writes_files_and_checks_system_error(tmp_path):
    with _scope() as scope:
        result = run_capture(
            scope,
            "SIM::DSOX4024A::INSTR",
            CaptureRequest((1,), 1000, csv_path=tmp_path / "capture.csv"),
        )

    assert result.exit_code == 0
    assert (tmp_path / "capture.csv").exists()
    assert result.files[1]["kind"] == "metadata"
    assert scope.backend.history[-1] == ":SYSTem:ERRor?"


def test_run_doctor_returns_channel_snapshot():
    with _scope("DSOX4034A") as scope:
        result = run_doctor(scope, "SIM::DSOX4034A::INSTR")

    assert result.exit_code == 0
    assert len(result.result["channels"]) == 4
    assert result.system_error["is_error"] is False


def test_run_measure_invalid_sentinel_exits_one():
    with _scope(invalid_measurement_channels=(1,)) as scope:
        result = run_measure(
            scope,
            "SIM::DSOX4024A::INSTR",
            MeasureRequest(item="vpp", channel=1),
        )

    assert result.exit_code == 1
    assert result.result["valid"] is False


def test_run_measure_sweep_summary_counts_invalid():
    with _scope(invalid_measurement_channels=(2,)) as scope:
        result = run_measure_sweep(
            scope,
            "SIM::DSOX4024A::INSTR",
            MeasureSweepRequest(channels=(1, 2), items="vpp"),
        )

    assert result.exit_code == 1
    assert result.result["summary"] == {
        "valid_count": 1,
        "invalid_count": 1,
        "error_count": 0,
    }


def test_run_measure_log_returns_structured_result_without_console_output(tmp_path, capsys):
    with _scope() as scope:
        result = run_measure_log(
            scope,
            "SIM::DSOX4024A::INSTR",
            MeasureLogRequest(
                channels=(1,),
                items="vpp",
                pair_items="phase",
                interval_seconds=0,
                requested_count=1,
                output_dir=tmp_path / "measure-log",
            ),
        )

    assert result.exit_code == 0
    assert result.result["status"] == "completed"
    assert result.result["completed_rows"] == 1
    assert result.result["csv_path"] == str(tmp_path / "measure-log" / "measurements.csv")
    assert result.files[1]["kind"] == "manifest"
    assert result.system_error["is_error"] is False
    assert result.human_lines
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_run_measure_log_preserves_instrument_error_result(tmp_path):
    with _scope(system_errors=['-113,"Undefined header"']) as scope:
        result = run_measure_log(
            scope,
            "SIM::DSOX4024A::INSTR",
            MeasureLogRequest(
                channels=(1,),
                items="vpp",
                pair_items="phase",
                interval_seconds=0,
                requested_count=2,
                output_dir=tmp_path / "measure-log-error",
                stop_on_error=True,
            ),
        )

    assert result.exit_code == 1
    assert result.result["status"] == "instrument_error"
    assert result.result["completed_rows"] == 1
    assert result.system_error["code"] == -113


def test_run_measure_log_preserves_invalid_measurement_and_duration_limit(tmp_path):
    with _scope(invalid_measurement_channels=(1,)) as scope:
        result = run_measure_log(
            scope,
            "SIM::DSOX4024A::INSTR",
            MeasureLogRequest(
                channels=(1,),
                items="vpp",
                pair_items="phase",
                interval_seconds=0.5,
                requested_duration_seconds=0.01,
                output_dir=tmp_path / "measure-log-duration",
            ),
        )

    assert result.exit_code == 0
    assert result.result["status"] == "completed"
    assert result.result["completed_rows"] == 1
    csv_text = (tmp_path / "measure-log-duration" / "measurements.csv").read_text(
        encoding="utf-8"
    )
    assert "NaN" in csv_text


def test_run_measure_log_preserves_interrupt_result(tmp_path, monkeypatch):
    with _scope() as scope:
        monkeypatch.setattr(
            scope,
            "query_measurement",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt),
        )
        result = run_measure_log(
            scope,
            "SIM::DSOX4024A::INSTR",
            MeasureLogRequest(
                channels=(1,),
                items="vpp",
                pair_items="phase",
                interval_seconds=0,
                requested_count=1,
                output_dir=tmp_path / "measure-log-interrupt",
            ),
        )

    assert result.exit_code == 130
    assert result.result["status"] == "interrupted"
    assert result.result["error"] == "KeyboardInterrupt"
    assert result.files[0]["kind"] == "csv"
    assert result.human_lines


def test_run_smoke_writes_report(tmp_path):
    with _scope() as scope:
        result = run_smoke(
            scope,
            "SIM::DSOX4024A::INSTR",
            SmokeRequest(output_dir=tmp_path / "smoke"),
        )

    report = json.loads((tmp_path / "smoke" / "report.json").read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert report["status"] == "completed"
    assert result.files[0]["kind"] == "report"


def test_run_acquisition_check_check_only_and_restore(tmp_path):
    with _scope("DSOX4034A") as scope:
        check_only = run_acquisition_check(
            scope,
            "SIM::DSOX4034A::INSTR",
            AcquisitionCheckRequest(output_dir=tmp_path / "check", check_only=True),
        )

    assert check_only.result["termination_reason"] == "check_only"
    assert [step["name"] for step in check_only.result["steps"]] == ["initial-query"]

    with _scope("DSOX4034A") as scope:
        restored = run_acquisition_check(
            scope,
            "SIM::DSOX4034A::INSTR",
            AcquisitionCheckRequest(output_dir=tmp_path / "restore", restore_type=True),
        )

    assert restored.result["restore"]["requested"] is True
    assert restored.result["restore"]["attempted"] is True
