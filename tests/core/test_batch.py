import json
import logging
from datetime import datetime

import pytest

from scopes_tool_core import batch
from scopes_tool_core.errors import KeysightScopeError
from scopes_tool_core.idn import parse_idn
from scopes_tool_core.status import SystemErrorEntry


def test_prepare_default_batch_output_dir_uses_timestamp_and_collision_suffix(tmp_path):
    now = datetime(2026, 5, 16, 12, 34, 56)

    first = batch.prepare_batch_output_dir(None, now=now, base_dir=tmp_path)
    second = batch.prepare_batch_output_dir(None, now=now, base_dir=tmp_path)
    third = batch.prepare_batch_output_dir(None, now=now, base_dir=tmp_path)

    assert first == tmp_path / "2026-05-16-12-34-56"
    assert second == tmp_path / "2026-05-16-12-34-56-2"
    assert third == tmp_path / "2026-05-16-12-34-56-3"
    assert first.is_dir()
    assert second.is_dir()
    assert third.is_dir()


def test_prepare_specified_batch_output_dir_accepts_missing_directory(tmp_path):
    output_dir = tmp_path / "new-batch"

    assert batch.prepare_batch_output_dir(output_dir) == output_dir

    assert output_dir.is_dir()


def test_prepare_specified_batch_output_dir_accepts_empty_directory(tmp_path):
    output_dir = tmp_path / "empty-batch"
    output_dir.mkdir()

    assert batch.prepare_batch_output_dir(output_dir) == output_dir


def test_prepare_specified_batch_output_dir_rejects_non_empty_directory(tmp_path):
    output_dir = tmp_path / "existing-batch"
    output_dir.mkdir()
    (output_dir / "old.csv").write_text("old\n", encoding="utf-8")

    with pytest.raises(KeysightScopeError, match="must be empty"):
        batch.prepare_batch_output_dir(output_dir)


def test_batch_capture_paths_use_minimum_four_digit_width(tmp_path):
    csv_path, meta_path = batch.batch_capture_paths(tmp_path, 3, 12)

    assert csv_path == tmp_path / "waveform_0003.csv"
    assert meta_path == tmp_path / "waveform_0003_meta.json"


def test_batch_capture_paths_expand_width_for_large_count(tmp_path):
    csv_path, meta_path = batch.batch_capture_paths(tmp_path, 12345, 12345)

    assert csv_path.name == "waveform_12345.csv"
    assert meta_path.name == "waveform_12345_meta.json"


def test_write_batch_manifest_json_fields_and_capture_list(tmp_path):
    idn = parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY123,07.20")
    entry = SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')
    manifest = batch.BatchManifest(
        schema_version=batch.BATCH_SCHEMA_VERSION,
        start_time="2026-05-16T12:00:00+08:00",
        end_time="2026-05-16T12:00:01+08:00",
        status="completed",
        resource="USB0::FAKE::INSTR",
        backend="fake",
        timeout_ms=2000,
        idn=batch.idn_manifest_dict(idn),
        channels=[1, 2],
        points=1000,
        format="BYTE",
        requested_count=1,
        interval_seconds=0.0,
        captures=[
            {
                "index": 1,
                "csv": "waveform_0001.csv",
                "metadata": "waveform_0001_meta.json",
                "actual_points": {"CH1": 2, "CH2": 2},
                "system_error": batch.system_error_manifest_dict(entry),
            }
        ],
    )

    manifest_path = batch.write_batch_manifest(manifest, tmp_path / "manifest.json")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "completed"
    assert payload["idn"]["model"] == "DSOX4024A"
    assert payload["channels"] == [1, 2]
    assert payload["captures"] == [
        {
            "index": 1,
            "csv": "waveform_0001.csv",
            "metadata": "waveform_0001_meta.json",
            "actual_points": {"CH1": 2, "CH2": 2},
            "system_error": {
                "code": 0,
                "message": "No error",
                "raw": '+0,"No error"',
                "is_error": False,
            },
        }
    ]


def test_capture_batch_scpi_logging_writes_package_debug_to_file(tmp_path):
    log_path = tmp_path / "scpi.log"
    logger = logging.getLogger("scopes_tool_core.scpi")

    with batch.capture_batch_scpi_logging(log_path):
        logger.debug("SCPI >> *IDN?")
        logger.debug("SCPI << IDN")

    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "scopes_tool_core.scpi DEBUG: SCPI >> *IDN?",
        "scopes_tool_core.scpi DEBUG: SCPI << IDN",
    ]
