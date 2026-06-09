from __future__ import annotations

from pathlib import Path

import keysight_scope_core as core


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_core_docs_are_package_local():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()
    assert (PACKAGE_ROOT / "docs" / "integration.md").exists()

    for adapter_doc in (
        "docs/cli-integration.md",
        "docs/README_CLI_EN.md",
        "docs/agent-workflow.md",
        "docs/Webui-README.md",
        "docs/scopes-cli-jsonl-contract.md",
        "docs/common-cli-jsonl-contract.md",
    ):
        assert not (PACKAGE_ROOT / adapter_doc).exists()

    for private_doc in (
        "hardware-test-plan.md",
        "session-handoff.md",
        "validation-history.md",
        "supported-models.md",
    ):
        assert not (PACKAGE_ROOT / "docs" / private_doc).exists()

    for removed_root_doc in (
        "agent-integration-plan.md",
        "hardware-test-plan.md",
        "supported-models.md",
        "development-plan.md",
        "project-plan.md",
        "session-handoff.md",
        "validation-history.md",
    ):
        assert not (REPO_ROOT / "docs" / removed_root_doc).exists()


def test_core_integration_names_public_core_api():
    text = read_doc("docs", "integration.md")

    assert "keysight_scope_core" in text
    for name in core.__all__:
        assert name in text
