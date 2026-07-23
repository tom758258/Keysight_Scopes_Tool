import json
from datetime import datetime

import pytest

from scopes_tool_core.errors import OscilloscopeError
from scopes_tool_core.output_files import (
    capture_output_paths,
    default_capture_csv_path,
    write_json_file,
)


def test_default_capture_csv_path_uses_utc8_timestamp():
    path = default_capture_csv_path(datetime(2026, 5, 31, 9, 8, 7))
    assert path.as_posix() == "data/2026-05-31-09-08-07.csv"


def test_capture_output_paths_defaults_metadata_stem():
    csv_path, meta_path, plot_path = capture_output_paths("out/capture.csv", None, None)

    assert str(csv_path) == "out\\capture.csv" or str(csv_path) == "out/capture.csv"
    assert meta_path.name == "capture_meta.json"
    assert plot_path is None


def test_write_json_file_sorts_indents_and_newline(tmp_path):
    path = tmp_path / "payload.json"

    write_json_file({"b": 1, "a": 2}, path, file_kind="test JSON")

    assert path.read_text(encoding="utf-8") == '{\n  "a": 2,\n  "b": 1\n}\n'
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2, "b": 1}


def test_write_json_file_wraps_oserror(monkeypatch, tmp_path):
    path = tmp_path / "payload.json"

    def fail_open(*args, **kwargs):
        del args, kwargs
        raise PermissionError("locked")

    monkeypatch.setattr(type(path), "open", fail_open)
    with pytest.raises(OscilloscopeError, match="could not write test JSON file"):
        write_json_file({"a": 1}, path, file_kind="test JSON")
