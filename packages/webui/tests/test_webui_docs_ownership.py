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


def test_webui_readme_uses_skeleton_language_not_cli_workflow():
    text = read_doc("README.md")

    assert "keysight_scope_webui" in text
    assert "skeleton" in text.lower()
    assert "No user-facing WebUI runtime is implemented" in text
    assert "scope-tool" not in text
    assert "python -m keysight_scope_cli.cli" not in text


def test_webui_docs_do_not_claim_runtime_ui_exists():
    text = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
        )
    )

    for forbidden in (
        "FastAPI",
        "uvicorn",
        "static UI",
        "implemented browser app",
        "implemented user-facing WebUI runtime to validate.",
    ):
        assert forbidden not in text
