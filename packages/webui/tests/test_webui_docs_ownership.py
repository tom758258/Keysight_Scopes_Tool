from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_webui_docs_are_package_local():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()

    for non_webui_doc in (
        "docs/cli-integration.md",
        "docs/README_CLI_EN.md",
        "docs/agent-workflow.md",
        "docs/scopes-cli-jsonl-contract.md",
        "docs/common-cli-jsonl-contract.md",
        "docs/hardware-test-plan.md",
        "docs/supported-models.md",
        "docs/project-plan.md",
        "docs/session-handoff.md",
        "docs/validation-history.md",
    ):
        assert not (PACKAGE_ROOT / non_webui_doc).exists()


def test_webui_readme_names_public_package_identity():
    text = read_doc("README.md")

    assert "keysight_scope_webui" in text
