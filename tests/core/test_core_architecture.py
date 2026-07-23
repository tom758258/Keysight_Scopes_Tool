from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = REPO_ROOT / "src" / "scopes_tool_core"
CLI_SRC = REPO_ROOT / "src" / "scopes_tool_cli"
WEBUI_SRC = REPO_ROOT / "src" / "scopes_tool_webui"


def _python_texts(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))


def test_core_source_does_not_print_directly():
    offenders = []
    for path in CORE_SRC.glob("*.py"):
        if "print(" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == []


def test_operations_do_not_depend_on_cli_process_state():
    text = (CORE_SRC / "operations.py").read_text(encoding="utf-8")

    assert "argparse" not in text
    assert "sys.argv" not in text


def test_import_packages_keep_dependency_boundaries():
    core_text = _python_texts(CORE_SRC)
    cli_text = _python_texts(CLI_SRC)
    webui_text = _python_texts(WEBUI_SRC)

    assert "scopes_tool_cli" not in core_text
    assert "scopes_tool_webui" not in core_text
    assert "scopes_tool_webui" not in cli_text
    assert "scopes_tool_cli" not in webui_text
