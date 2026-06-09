# Keysight Scopes

Monorepo for Keysight InfiniiVision oscilloscope tooling. The repository is
split into package-owned Core, CLI, and WebUI areas while root documentation
keeps project-level orientation and shared machine contracts.

## License and Disclaimer

This project is licensed under the MIT License. See `LICENSE`.

This project is an independent, unofficial project and is not affiliated with,
endorsed by, or sponsored by Keysight Technologies.

Users are responsible for complying with all applicable Keysight software,
driver, instrument, and documentation license terms.

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
.\scripts\run-tests.ps1
```

The repository uses editable package installs for local development. It is not
configured as a committed `uv` workspace.

The PowerShell test script gives each pytest run an isolated temporary
directory. This avoids Windows permission conflicts when tests are run by both
the local user and a sandboxed tool. It removes the directory after a successful
run and preserves it after a failure for inspection. Additional pytest
arguments are forwarded:

```powershell
.\scripts\run-tests.ps1 packages/cli/tests/test_worker_cli.py -vv
```

Running pytest directly may fail with `PermissionError: [WinError 5]` if
`$env:TEMP\pytest-of-$env:USERNAME` was created by another Windows identity.
The test script bypasses that shared directory. To restore direct pytest usage,
remove the conflicting directory from an administrator PowerShell:

```powershell
Remove-Item -LiteralPath "$env:TEMP\pytest-of-$env:USERNAME" -Recurse -Force
```

## Documentation Index

Project-level docs:

- `docs/architecture/monorepo-layout.md`
- `docs/contracts/`
- `docs/testing-guidelines.md`

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
