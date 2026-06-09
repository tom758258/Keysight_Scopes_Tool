from __future__ import annotations

import inspect
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
    assert (REPO_ROOT / "AGENTS.md").exists()
    assert (REPO_ROOT / "README.md").exists()
    assert (REPO_ROOT / "docs" / "architecture" / "monorepo-layout.md").exists()

    for adapter_doc in (
        "docs/cli-integration.md",
        "docs/Webui-README.md",
        "docs/scopes-cli-jsonl-contract.md",
        "docs/common-cli-jsonl-contract.md",
    ):
        assert not (PACKAGE_ROOT / adapter_doc).exists()

    for contract in (
        "common-cli-jsonl-contract.md",
        "scopes-cli-jsonl-contract.md",
    ):
        assert (REPO_ROOT / "docs" / "contracts" / contract).exists()


def test_core_integration_names_public_core_api():
    text = read_doc("docs", "integration.md")

    assert "keysight_scope_core" in text
    for name in core.__all__:
        assert name in text


def test_root_readme_discovers_core_and_agent_docs():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "AGENTS.md" in text
    assert "packages/core/README.md" in text
    assert "packages/core/docs/integration.md" in text


def test_public_core_classes_and_functions_have_docstrings():
    missing = [
        name
        for name in core.__all__
        if (inspect.isclass(getattr(core, name)) or inspect.isfunction(getattr(core, name)))
        and inspect.getdoc(getattr(core, name)) is None
    ]

    assert missing == []
