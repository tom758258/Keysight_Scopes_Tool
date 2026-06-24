import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import queue
from http.server import ThreadingHTTPServer
import subprocess
import sys
import textwrap
import threading
from urllib import error as urlerror
from urllib import request as urlrequest

import pytest

from keysight_scope_cli import cli
from keysight_scope_cli import worker
from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import KeysightScopeError
from keysight_scope_core.idn import parse_idn


def _runtime(artifact_root=Path("data/worker"), queue_max=32):
    return worker.WorkerRuntime(
        host="127.0.0.1",
        port=0,
        mode="simulate",
        model="DSOX4024A",
        resource=None,
        artifact_root=Path(artifact_root),
        queue_max=queue_max,
        output_format="jsonl",
    )


def _live_runtime(artifact_root=Path("data/worker")):
    return worker.WorkerRuntime(
        host="127.0.0.1",
        port=0,
        mode="live",
        model="DSOX4024A",
        resource="USB0::FAKE::INSTR",
        artifact_root=Path(artifact_root),
        queue_max=32,
        output_format="jsonl",
    )


def test_live_worker_requires_explicit_resource():
    args = argparse.Namespace(
        simulate=False,
        host="127.0.0.1",
        port=0,
        model="DSOX4024A",
        resource=None,
        artifact_root="data/worker",
        queue_max=32,
        format="jsonl",
    )

    with pytest.raises(KeysightScopeError, match="worker --live requires --resource"):
        worker.run_worker(args)


@contextmanager
def _worker_server(runtime):
    server = ThreadingHTTPServer(("127.0.0.1", 0), worker._make_handler(runtime))
    runtime.port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield runtime
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _post_command(runtime, body, *, raw=False):
    data = body if raw else json.dumps(body).encode("utf-8")
    req = urlrequest.Request(
        f"http://127.0.0.1:{runtime.port}/command",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _wait_event_from_queue(events, event_backlog, name, *, predicate=None, timeout=1):
    import time

    deadline = time.monotonic() + timeout
    while True:
        for index, event in enumerate(event_backlog):
            if event.get("event") != name:
                continue
            if predicate is not None and not predicate(event):
                continue
            return event_backlog.pop(index)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(name)

        try:
            event = events.get(timeout=min(0.2, remaining))
        except queue.Empty:
            continue

        if event.get("event") == name and (
            predicate is None or predicate(event)
        ):
            return event

        event_backlog.append(event)


def _run_fake_worker_lifecycle(script, *, ready_timeout=1):
    events = queue.Queue()
    event_backlog = []
    stderr_lines = []
    ready = None
    summary = None
    workflow_error = None
    proc = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def read_stdout():
        assert proc.stdout is not None
        for line in proc.stdout:
            events.put(json.loads(line))

    def read_stderr():
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line.rstrip())

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        ready = _wait_event_from_queue(events, event_backlog, "ready", timeout=ready_timeout)
        assert ready["event"] == "ready"
    except Exception as exc:
        workflow_error = exc
    finally:
        if ready is not None:
            try:
                summary = _wait_event_from_queue(
                    events,
                    event_backlog,
                    "summary",
                    timeout=1,
                )
            except TimeoutError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

    workflow_failed = (
        workflow_error is not None
        or ready is None
        or summary is None
        or summary.get("event") != "summary"
        or summary.get("run_id") != ready["run_id"]
        or summary.get("ok") is not True
        or summary.get("failed") != 0
        or summary.get("cancelled") != 0
        or proc.returncode != 0
    )
    if workflow_failed:
        raise RuntimeError(
            "worker workflow failed: "
            f"error={workflow_error!r} "
            f"summary={summary} "
            f"worker.returncode={proc.returncode} "
            f"stderr_tail={stderr_lines[-20:]}"
        )
    return ready, summary, stderr_lines


def test_worker_request_rejects_unknown_top_level_field():
    with pytest.raises(KeysightScopeError, match="unknown request field"):
        worker.validate_command_request(
            {"command": "identify", "arguments": {}, "extra": True}
        )


def test_worker_request_rejects_unknown_command():
    with pytest.raises(KeysightScopeError, match="unknown command"):
        worker.validate_command_request({"command": "list-resources", "arguments": {}})


def test_worker_request_rejects_non_object_arguments():
    with pytest.raises(KeysightScopeError, match="arguments"):
        worker.validate_command_request({"command": "identify", "arguments": []})


def test_command_acceptance_returns_common_envelope_and_artifact(tmp_path):
    runtime = _runtime(tmp_path)
    with _worker_server(runtime):
        status, payload = _post_command(
            runtime,
            {"command": "identify", "arguments": {}, "job_id": "job-1"},
        )

    assert status == 202
    assert payload["status"] == "accepted"
    assert payload["command"] == "identify"
    assert payload["job_id"] == "job-1"
    assert payload["worker_job_id"]
    request_path = Path(payload["artifact_path"]) / "request.json"
    assert json.loads(request_path.read_text(encoding="utf-8")) == {
        "command": "identify",
        "arguments": {},
        "job_id": "job-1",
    }


def test_worker_correlation_flows_through_events_and_artifacts(tmp_path):
    runtime = _runtime(tmp_path)
    client_job_id = "client-job-1"
    with _worker_server(runtime):
        status, accepted = _post_command(
            runtime,
            {"command": "identify", "arguments": {}, "job_id": client_job_id},
        )

    worker_job_id = accepted["worker_job_id"]
    assert status == 202
    assert accepted["status"] == "accepted"
    assert accepted["command"] == "identify"
    assert accepted["job_id"] == client_job_id
    assert accepted["artifact_path"]
    assert worker_job_id
    assert worker_job_id != client_job_id
    assert runtime.run_id != worker_job_id

    job = runtime.jobs[worker_job_id]
    job.state = "succeeded"
    job.started_time = "started"
    job.finished_time = "finished"
    job.exit_code = 0
    job.result = {"ok": True, "result": {"idn": {}}, "files": []}
    started = worker._event_payload(
        runtime, "job_started", worker_job_id=worker_job_id, command="identify"
    )
    worker._write_result(runtime, job)
    finished = worker._event_payload(
        runtime,
        "job_finished",
        worker_job_id=worker_job_id,
        job_id=client_job_id,
        command="identify",
        state="succeeded",
        ok=True,
        exit_code=0,
        artifact_path=accepted["artifact_path"],
        result_path=str(Path(accepted["artifact_path"]) / "result.json"),
        error=None,
    )

    request_payload = json.loads(
        (Path(accepted["artifact_path"]) / "request.json").read_text(encoding="utf-8")
    )
    result_payload = json.loads(
        (Path(accepted["artifact_path"]) / "result.json").read_text(encoding="utf-8")
    )

    assert started["job_id"] == client_job_id
    assert started["worker_job_id"] == worker_job_id
    assert started["command"] == "identify"
    assert finished["job_id"] == client_job_id
    assert finished["worker_job_id"] == worker_job_id
    assert finished["command"] == "identify"
    assert request_payload["job_id"] == client_job_id
    assert request_payload["command"] == "identify"
    assert result_payload["run_id"] == runtime.run_id
    assert result_payload["worker_job_id"] == worker_job_id
    assert result_payload["job_id"] == client_job_id
    assert result_payload["command"] == "identify"
    assert result_payload["state"] == "succeeded"
    assert result_payload["ok"] is True
    assert result_payload["exit_code"] == 0


@pytest.mark.parametrize(
    ("body", "expected_command", "expected_job_id"),
    (
        (b"{", None, None),
        ([], None, None),
        ({"command": "identify", "arguments": {}, "extra": True}, "identify", None),
        ({"command": "list-resources", "arguments": {}, "job_id": "job-2"}, "list-resources", "job-2"),
        ({"command": "identify", "arguments": {}, "job_id": 7}, "identify", None),
    ),
)
def test_command_validation_errors_use_common_echo_rules(
    tmp_path, body, expected_command, expected_job_id
):
    runtime = _runtime(tmp_path)
    with _worker_server(runtime):
        status, payload = _post_command(runtime, body, raw=isinstance(body, bytes))

    assert status == 400
    assert payload["status"] == "error"
    assert payload["command"] == expected_command
    assert payload["job_id"] == expected_job_id
    assert payload["error"] == "validation_error"
    assert not any(tmp_path.iterdir())


def test_queue_full_rejection_uses_rejected_reason(tmp_path):
    runtime = _runtime(tmp_path, queue_max=1)
    runtime.queue.put_nowait(
        worker.WorkerJob(
            command="identify",
            arguments={},
            job_id=None,
            worker_job_id="queued",
            artifact_path=tmp_path / "queued",
            request_time="now",
        )
    )

    with _worker_server(runtime):
        status, payload = _post_command(
            runtime,
            {"command": "identify", "arguments": {}, "job_id": "job-3"},
        )

    assert status == 429
    assert payload == {
        "status": "rejected",
        "command": "identify",
        "job_id": "job-3",
        "reason": "queue_full",
    }


def test_worker_parses_domain_arguments_without_opening_backend():
    parsed = worker.parse_domain_command(
        "channel-scale",
        {"channel": 1, "volts_per_division": 0.5},
        _runtime(),
    )

    assert parsed.command == "channel-scale"
    assert parsed.channel == 1
    assert parsed.scale_value == 0.5
    assert parsed.simulate is True
    assert parsed.json_output is True


def test_worker_parse_rejects_invalid_domain_arguments():
    with pytest.raises(KeysightScopeError):
        worker.parse_domain_command(
            "channel-scale",
            {"channel": 9, "volts_per_division": 0.5},
            _runtime(),
        )


def test_send_command_dry_run_does_not_contact_http(capsys):
    args = argparse.Namespace(
        command="send-command",
        host="127.0.0.1",
        port=9,
        worker_command="identify",
        arguments_json="{}",
        job_id="job-1",
        timeout_ms=1,
        format="json",
        client_json=True,
        dry_run=True,
    )

    assert worker.client_send_command(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert payload["schema_version"] == 1
    assert "timestamp_utc" in payload
    assert payload["command"] == "identify"
    assert payload["request"] == {
        "command": "identify",
        "arguments": {},
        "job_id": "job-1",
    }


def test_stop_is_lifecycle_command_and_stop_acquisition_is_domain(capsys):
    assert cli.main(["stop", "--port", "9", "--timeout-ms", "1", "--json"]) == 3
    assert cli.main(["stop-acquisition", "--simulate", "--json"]) == 0


def test_direct_json_envelope_has_schema_and_timestamp(capsys):
    assert cli.main(["identify", "--simulate", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == 1
    assert "timestamp_utc" in payload
    assert payload["ok"] is True


def test_worker_event_payloads_have_required_fields(tmp_path):
    runtime = _runtime(tmp_path)
    job = worker.WorkerJob(
        command="identify",
        arguments={},
        job_id="client-job",
        worker_job_id="worker-job",
        artifact_path=tmp_path / "worker-job",
        request_time="now",
    )
    runtime.jobs[job.worker_job_id] = job

    ready = worker._event_payload(runtime, "ready", trigger_url="forbidden")
    started = worker._event_payload(
        runtime, "job_started", worker_job_id=job.worker_job_id, command=job.command
    )
    finished = worker._event_payload(
        runtime,
        "job_finished",
        worker_job_id=job.worker_job_id,
        job_id=job.job_id,
        command=job.command,
        state="failed",
        ok=False,
        artifact_path=str(job.artifact_path),
        result_path=str(job.artifact_path / "result.json"),
        error={"type": "x", "message": "y"},
    )
    summary = worker._event_payload(runtime, "summary", ok=True, fatal_error=None)

    for payload in (ready, started, finished, summary):
        assert payload["schema_version"] == 1
        assert payload["run_id"] == runtime.run_id
        assert "timestamp_utc" in payload
    assert ready["event"] == "ready"
    assert ready["service"] == "keysight-scopes"
    assert ready["host"] == "127.0.0.1"
    assert ready["port"] == 0
    assert ready["mode"] == "simulate"
    assert ready["model"] == "DSOX4024A"
    assert ready["resource"] is None
    assert "trigger_url" not in ready
    assert started["job_id"] == "client-job"
    assert started["artifact_path"] == str(job.artifact_path)
    assert finished["state"] == "failed"
    assert finished["ok"] is False
    assert summary["accepted"] == 0


def _assert_status_payload_matches_ready(payload, ready):
    assert payload["service"] == "keysight-scopes"
    assert payload["run_id"] == ready["run_id"]
    assert payload["mode"] == ready["mode"]
    assert payload["model"] == ready["model"]
    assert payload["resource"] == ready["resource"]
    assert payload["urls"]["command_url"] == ready["command_url"]
    assert payload["urls"]["status_url"] == ready["status_url"]
    assert payload["urls"]["stop_url"] == ready["stop_url"]
    assert "command_url" not in payload
    assert "status_url" not in payload
    assert "stop_url" not in payload
    assert "trigger_url" not in payload
    assert "trigger_url" not in payload["urls"]


def test_status_and_wait_ready_match_ready_session_and_status_urls(tmp_path, capsys):
    runtime = _runtime(tmp_path)
    with _worker_server(runtime):
        ready = worker._event_payload(
            runtime,
            "ready",
            status_url=f"{runtime.base_url()}/status",
            command_url=f"{runtime.base_url()}/command",
            stop_url=f"{runtime.base_url()}/stop",
            trigger_url="forbidden",
        )
        args = argparse.Namespace(
            command="wait-ready",
            host="127.0.0.1",
            port=runtime.port,
            timeout_ms=1000,
            format="json",
            client_json=True,
        )
        assert worker.client_wait_ready(args) == 0
        status_args = argparse.Namespace(
            command="status",
            host="127.0.0.1",
            port=runtime.port,
            timeout_ms=1000,
            format="json",
            client_json=True,
        )
        assert worker.client_get(status_args, "/status") == 0

    output_lines = capsys.readouterr().out.strip().splitlines()
    wait_payload = json.loads(output_lines[0])
    status_payload = json.loads(output_lines[1])
    assert ready["event"] == "ready"
    assert ready["schema_version"] == 1
    assert ready["service"] == "keysight-scopes"
    assert ready["run_id"]
    assert ready["host"] == "127.0.0.1"
    assert ready["port"] == runtime.port
    assert ready["mode"] == "simulate"
    assert ready["model"] == "DSOX4024A"
    assert ready["resource"] is None
    assert ready["command_url"].endswith("/command")
    assert ready["status_url"].endswith("/status")
    assert ready["stop_url"].endswith("/stop")
    assert "trigger_url" not in ready
    _assert_status_payload_matches_ready(wait_payload, ready)
    _assert_status_payload_matches_ready(status_payload, ready)


def test_worker_lifecycle_failure_before_ready_keeps_stderr_diagnostics():
    script = """
        import sys

        print("startup failed: missing dependency", file=sys.stderr, flush=True)
        raise SystemExit(7)
    """

    with pytest.raises(RuntimeError) as exc_info:
        _run_fake_worker_lifecycle(script, ready_timeout=0.2)

    message = str(exc_info.value)
    assert "UnboundLocalError" not in message
    assert "startup failed: missing dependency" in message
    assert "summary=None" in message
    assert "worker.returncode=7" in message


def test_worker_lifecycle_drains_stderr_without_mixing_stdout_jsonl():
    script = """
        import json
        import sys

        ready = {"event": "ready", "run_id": "run-1"}
        print(json.dumps(ready), flush=True)
        for index in range(2000):
            print(f"diagnostic-{index}", file=sys.stderr, flush=True)
        summary = {
            "event": "summary",
            "run_id": "run-1",
            "ok": False,
            "failed": 1,
            "cancelled": 0,
        }
        print(json.dumps(summary), flush=True)
    """

    with pytest.raises(RuntimeError) as exc_info:
        _run_fake_worker_lifecycle(script)

    message = str(exc_info.value)
    assert "diagnostic-1999" in message
    assert "diagnostic-0" not in message
    assert message.count("diagnostic-") <= 20
    assert "summary={'event': 'summary'" in message


@pytest.mark.parametrize(
    ("summary", "return_code", "should_pass", "match"),
    (
        ({"event": "summary", "run_id": "run-1", "ok": True, "failed": 0, "cancelled": 0}, 0, True, None),
        (None, 0, False, "summary=None"),
        ({"event": "summary", "run_id": "run-1", "ok": False, "failed": 0, "cancelled": 0}, 0, False, "'ok': False"),
        ({"event": "summary", "run_id": "other", "ok": True, "failed": 0, "cancelled": 0}, 0, False, "'run_id': 'other'"),
        ({"event": "summary", "run_id": "run-1", "ok": True, "failed": 0, "cancelled": 0}, 9, False, "worker.returncode=9"),
    ),
)
def test_worker_lifecycle_validates_final_summary(summary, return_code, should_pass, match):
    lines = [
        "import json",
        "import sys",
        'print(json.dumps({"event": "ready", "run_id": "run-1"}), flush=True)',
        'print("final diagnostic", file=sys.stderr, flush=True)',
    ]
    if summary is not None:
        lines.append(f"print(json.dumps({summary!r}), flush=True)")
    lines.append(f"raise SystemExit({return_code})")
    script = "\n".join(lines)

    if should_pass:
        ready, final_summary, stderr_lines = _run_fake_worker_lifecycle(script)
        assert ready["run_id"] == "run-1"
        assert final_summary == summary
        assert stderr_lines == ["final diagnostic"]
    else:
        with pytest.raises(RuntimeError, match=match) as exc_info:
            _run_fake_worker_lifecycle(script)
        assert "final diagnostic" in str(exc_info.value)


def test_event_backlog_preserves_non_target_events_and_predicate_selects_job():
    events = queue.Queue()
    event_backlog = []
    events.put({"event": "message", "text": "kept"})
    events.put({"event": "job_started", "worker_job_id": "other"})
    events.put({"event": "summary", "run_id": "run-1"})
    events.put({"event": "job_started", "worker_job_id": "target"})
    events.put({"event": "job_finished", "worker_job_id": "target"})

    started = _wait_event_from_queue(
        events,
        event_backlog,
        "job_started",
        predicate=lambda event: event.get("worker_job_id") == "target",
    )
    summary = _wait_event_from_queue(
        events,
        event_backlog,
        "summary",
        predicate=lambda event: event.get("run_id") == "run-1",
    )
    other_started = _wait_event_from_queue(
        events,
        event_backlog,
        "job_started",
        predicate=lambda event: event.get("worker_job_id") == "other",
    )
    message = _wait_event_from_queue(events, event_backlog, "message")

    assert started["worker_job_id"] == "target"
    assert summary["run_id"] == "run-1"
    assert other_started["worker_job_id"] == "other"
    assert message["text"] == "kept"


def test_worker_job_paths_default_under_job_dir(tmp_path):
    job_dir = tmp_path / "run" / "job"
    parsed = worker.parse_domain_command(
        "capture",
        {"channel": [1], "points": 1000, "plot": "plot.png"},
        _runtime(tmp_path),
        job_dir,
    )

    assert Path(parsed.csv_path) == job_dir / "capture.csv"
    assert Path(parsed.meta_path) == job_dir / "capture_meta.json"
    assert Path(parsed.plot_path) == job_dir / "plot.png"


def test_worker_no_overwrite_guard_rejects_existing_artifact(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "capture.csv").write_text("existing", encoding="utf-8")
    parsed = worker.parse_domain_command(
        "capture",
        {"channel": [1]},
        _runtime(tmp_path),
        job_dir,
    )

    with pytest.raises(KeysightScopeError, match="already exists"):
        worker._guard_no_overwrite(parsed, job_dir)


def test_stop_cancels_queued_job_with_terminal_result(tmp_path):
    runtime = _runtime(tmp_path)
    job_dir = tmp_path / "run" / "queued"
    job_dir.mkdir(parents=True)
    (job_dir / "request.json").write_text("{}", encoding="utf-8")
    job = worker.WorkerJob(
        command="identify",
        arguments={},
        job_id="client-job",
        worker_job_id="queued",
        artifact_path=job_dir,
        request_time="now",
    )
    runtime.jobs[job.worker_job_id] = job

    worker._finish_cancelled_job(runtime, job, started=False)
    result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))

    assert result["state"] == "cancelled"
    assert result["ok"] is False
    assert result["exit_code"] == 3
    assert runtime.cancelled == 1


class _FakeBackend:
    backend = "fake VISA"

    def __init__(self, idn: str):
        self.idn = idn
        self.history = []
        self.timeout = None

    def query(self, command: str) -> str:
        self.history.append(command)
        if command == "*IDN?":
            return self.idn
        return "+0,\"No error\""

    def write(self, command: str) -> None:
        self.history.append(command)

    def set_timeout(self, timeout_ms: int | None) -> None:
        self.timeout = timeout_ms


class _FakeScope:
    def __init__(self, idn: str):
        self.backend = _FakeBackend(idn)
        self.scpi = self.backend
        self.capabilities = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def query_idn(self):
        idn = parse_idn(self.backend.query("*IDN?"))
        self.capabilities = capabilities_for_model(idn.model)
        return idn


def test_live_worker_identity_mismatch_fails_before_domain_scpi(monkeypatch, tmp_path):
    fake_scope = _FakeScope("KEYSIGHT,DSOX3024A,MY0000,1.0")
    monkeypatch.setattr(cli.KeysightScope, "open", lambda *args, **kwargs: fake_scope)
    parsed = worker.parse_domain_command(
        "capture",
        {"channel": [1]},
        _live_runtime(tmp_path),
        tmp_path / "job",
    )

    payload, exit_code = cli._execute_json_command(parsed)

    assert exit_code == 3
    assert payload["ok"] is False
    assert payload["error"]["type"] == "identity_mismatch"
    assert payload["error"]["expected_model"] == "DSOX4024A"
    assert payload["error"]["actual_idn"] == "KEYSIGHT,DSOX3024A,MY0000,1.0"
    assert fake_scope.backend.history == ["*IDN?"]
    assert fake_scope.backend.timeout == cli.WORKER_IDN_TIMEOUT_MS
