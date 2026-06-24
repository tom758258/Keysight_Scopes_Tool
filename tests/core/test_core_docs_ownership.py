from __future__ import annotations

import inspect
from pathlib import Path

import keysight_scope_core as core


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = REPO_ROOT / "docs" / "core"


def read_doc(*parts: str) -> str:
    return DOC_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_core_docs_are_root_level():
    assert (DOC_ROOT / "README.md").exists()
    assert (REPO_ROOT / "CHANGELOG.md").exists()
    assert (DOC_ROOT / "integration.md").exists()
    assert (REPO_ROOT / "AGENTS.md").exists()
    assert (REPO_ROOT / "README.md").exists()
    assert (REPO_ROOT / "docs" / "architecture" / "monorepo-layout.md").exists()

    for adapter_doc in (
        REPO_ROOT / "docs" / "core" / "cli-integration.md",
        REPO_ROOT / "docs" / "core" / "Webui-README.md",
        REPO_ROOT / "docs" / "core" / "scopes-cli-jsonl-contract.md",
        REPO_ROOT / "docs" / "core" / "common-cli-jsonl-contract.md",
    ):
        assert not adapter_doc.exists()

    for contract in (
        "common-cli-jsonl-contract.md",
        "scopes-cli-jsonl-contract.md",
    ):
        assert (REPO_ROOT / "docs" / "contracts" / contract).exists()


def test_core_integration_names_public_core_api():
    text = read_doc("integration.md")

    assert "keysight_scope_core" in text
    for name in core.__all__:
        assert name in text


def test_root_readme_discovers_core_and_agent_docs():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "AGENTS.md" in text
    assert "docs/core/README.md" in text
    assert "docs/core/integration.md" in text


def test_public_core_classes_and_functions_have_docstrings():
    missing = [
        name
        for name in core.__all__
        if (inspect.isclass(getattr(core, name)) or inspect.isfunction(getattr(core, name)))
        and inspect.getdoc(getattr(core, name)) is None
    ]

    assert missing == []
