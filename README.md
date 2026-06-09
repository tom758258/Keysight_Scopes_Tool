# Keysight Scopes

Monorepo for Keysight InfiniiVision oscilloscope tooling. The repository is
split into package-owned Core, CLI, and WebUI areas while root documentation
keeps project-level orientation and shared machine contracts.

## Packages

| Package | Distribution | Import / entry point | Public docs |
| --- | --- | --- | --- |
| Core | `keysight-scope-core` | `keysight_scope_core` | `packages/core/README.md`, `packages/core/docs/integration.md` |
| CLI | `keysight-scope-cli` | `keysight-scopes`, `python -m keysight_scope_cli.cli` | `packages/cli/README.md`, `packages/cli/docs/` |
| WebUI | `keysight-scope-webui` | `keysight_scope_webui` skeleton | `packages/webui/README.md` |

Runtime APIs, console scripts, package metadata, SCPI behavior, and JSON
contracts are owned by the package docs and root contracts.

## Development

From PowerShell:

```powershell
uv venv .venv
uv pip install -e "packages/core[dev]" -e packages/cli -e packages/webui
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

The repository uses editable package installs for local development. It is not
configured as a committed `uv` workspace.

## Documentation Index

Project-level docs:

- `docs/architecture/monorepo-layout.md`
- `docs/contracts/`

Package docs:

- Core runtime, public import API, VISA/SCPI safety, hardware validation, and
  supported model status: `packages/core/README.md`
- CLI command usage, JSON mode, and automation safety:
  `packages/cli/README.md`
- WebUI package skeleton and future ownership notes:
  `packages/webui/README.md`

Shared contracts under `docs/contracts/` remain the source of truth for
cross-package machine behavior. Package docs link to those contracts instead of
duplicating them.
