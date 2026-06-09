from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def read_contract(*parts: str) -> str:
    return REPO_ROOT.joinpath("docs", "contracts", *parts).read_text(
        encoding="utf-8"
    )


def test_cli_docs_are_package_local_and_contracts_are_root_level():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()

    for path in (
        "docs/cli-integration.md",
        "docs/README_CLI_EN.md",
    ):
        assert (PACKAGE_ROOT / path).exists()

    for contract in (
        "common-worker-protocol.md",
        "common-cli-jsonl-contract.md",
        "scopes-cli-jsonl-contract.md",
        "common-orchestrator-workflows.md",
        "scopes-orchestrator-workflows.md",
        "scopes-worker-contract.md",
    ):
        assert (REPO_ROOT / "docs" / "contracts" / contract).exists()
        assert not (PACKAGE_ROOT / "docs" / contract).exists()

    assert not (PACKAGE_ROOT / "docs" / "hardware-test-plan.md").exists()
    assert not (PACKAGE_ROOT / "docs" / "supported-models.md").exists()
    assert not (PACKAGE_ROOT / "docs" / "Webui-README.md").exists()
    assert not (PACKAGE_ROOT / "docs" / "agent-workflow.md").exists()
    assert not (PACKAGE_ROOT / "docs" / "session-handoff.md").exists()
    assert not (PACKAGE_ROOT / "docs" / "validation-history.md").exists()


def test_cli_integration_keeps_cli_fields_out_of_core_schema():
    text = read_doc("docs", "cli-integration.md")

    assert "measurement_cli_name" in text
    assert "adapter behavior, not Core schema" in text
    assert "argparse.Namespace" in text
    assert "keysight-scopes = keysight_scope_cli.cli:main" in text


def test_cli_command_guide_links_root_contracts_and_safe_modes():
    text = read_doc("docs", "README_CLI_EN.md")

    assert "--dry-run --json" in text
    assert "--simulate --json" in text
    assert "--live --resource" in text
    assert "scopes-cli-jsonl-contract.md" in text
    assert "common-cli-jsonl-contract.md" in text


def test_common_contracts_stay_instrument_neutral():
    text = "\n".join(
        read_contract(path)
        for path in (
            "common-worker-protocol.md",
            "common-cli-jsonl-contract.md",
            "common-orchestrator-workflows.md",
        )
    )

    for forbidden in ("Scopes", "Keysight", "DSOX", "VISA", "SCPI", "oscilloscope"):
        assert forbidden not in text


def test_common_contracts_are_copied_from_meters_common_sources():
    for name in (
        "common-worker-protocol.md",
        "common-cli-jsonl-contract.md",
        "common-orchestrator-workflows.md",
    ):
        assert (REPO_ROOT / "docs" / "contracts" / name).read_bytes() == (
            REPO_ROOT / "Meters" / name
        ).read_bytes()


def test_scopes_contracts_link_common_contracts():
    cli_contract = read_contract("scopes-cli-jsonl-contract.md")
    workflow_contract = read_contract("scopes-orchestrator-workflows.md")
    worker_contract = read_contract("scopes-worker-contract.md")

    assert "common-cli-jsonl-contract.md" in cli_contract
    assert "common-orchestrator-workflows.md" in workflow_contract
    assert "common-worker-protocol.md" in worker_contract
    assert "Scopes-specific" in cli_contract
    assert "Scopes worker contract only" in worker_contract
    assert "Every `/command` response contains the Common fields" in worker_contract
    assert "command: null" in worker_contract


def test_scopes_orchestrator_example_documents_correlation_and_backlog():
    workflow_contract = read_contract("scopes-orchestrator-workflows.md")
    worker_contract = read_contract("scopes-worker-contract.md")

    assert 'client_job_id = "client-job-1"' in workflow_contract
    assert '"--job-id",' in workflow_contract
    assert 'assert accepted["job_id"] == client_job_id' in workflow_contract
    assert 'assert started["job_id"] == client_job_id' in workflow_contract
    assert 'assert finished["job_id"] == client_job_id' in workflow_contract
    assert 'assert request_payload["job_id"] == client_job_id' in workflow_contract
    assert 'assert result_payload["job_id"] == client_job_id' in workflow_contract
    assert "event_backlog = []" in workflow_contract
    assert "predicate=lambda event: event.get(\"worker_job_id\") == worker_job_id" in workflow_contract
    assert "predicate=lambda event: event.get(\"run_id\") == ready[\"run_id\"]" in workflow_contract
    assert 'assert ready["command_url"].endswith("/command")' in workflow_contract
    assert 'assert wait_payload["urls"]["command_url"] == ready["command_url"]' in workflow_contract
    assert '"csv": "capture.csv"' in worker_contract
    assert '"csv": "data/capture.csv"' not in worker_contract


def test_scopes_orchestrator_example_documents_worker_cleanup_reliability():
    workflow_contract = read_contract("scopes-orchestrator-workflows.md")

    assert "ready = None" in workflow_contract
    assert "summary = None" in workflow_contract
    assert "workflow_error = None" in workflow_contract
    assert "stderr_lines = []" in workflow_contract
    assert "def read_stderr():" in workflow_contract
    assert "threading.Thread(target=read_stderr, daemon=True).start()" in workflow_contract
    assert "stderr_tail={stderr_lines[-20:]}" in workflow_contract
    assert 'assert wait_payload["service"] == "keysight-scopes"' in workflow_contract
    assert 'assert wait_payload["urls"]["command_url"] == ready["command_url"]' in workflow_contract
    assert 'assert wait_payload["urls"]["status_url"] == ready["status_url"]' in workflow_contract
    assert 'assert wait_payload["urls"]["stop_url"] == ready["stop_url"]' in workflow_contract
    assert 'assert "command_url" not in wait_payload' in workflow_contract
    assert 'assert "trigger_url" not in wait_payload["urls"]' in workflow_contract
    assert "except Exception as exc:" in workflow_contract
    assert "workflow_error = exc" in workflow_contract
    assert "workflow_error is not None" in workflow_contract
    assert "error={workflow_error!r}" in workflow_contract
    assert 'summary.get("event") != "summary"' in workflow_contract
    assert 'summary.get("run_id") != ready["run_id"]' in workflow_contract
    assert 'summary.get("ok") is not True' in workflow_contract
    assert 'summary.get("failed") != 0' in workflow_contract
    assert 'summary.get("cancelled") != 0' in workflow_contract
    assert "worker.returncode != 0" in workflow_contract


def test_scopes_cli_contract_documents_nested_status_urls_only():
    cli_contract = read_contract("scopes-cli-jsonl-contract.md")

    assert "`status` and `wait-ready` use the same status payload schema" in cli_contract
    assert 'service: "keysight-scopes"' in cli_contract
    assert "`run_id` must match the `ready` event" in cli_contract
    assert "only in the nested `urls`" in cli_contract
    assert "`command_url`, `status_url`, and `stop_url`" in cli_contract
    assert "Top-level `command_url`, `status_url`, and `stop_url` fields are" in cli_contract
    assert "not supported in `status` or `wait-ready` JSON" in cli_contract
    assert "The `urls` object must not" in cli_contract
    assert "include `trigger_url`" in cli_contract
