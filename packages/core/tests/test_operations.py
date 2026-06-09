import json

from keysight_scope_core.operations import (
    AcquisitionCheckRequest,
    CaptureRequest,
    MeasureRequest,
    MeasureSweepRequest,
    SmokeRequest,
    run_acquisition_check,
    run_capture,
    run_doctor,
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
