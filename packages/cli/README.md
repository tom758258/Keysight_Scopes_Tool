# Keysight Scope CLI

Command-line adapter for Keysight InfiniiVision oscilloscope workflows.

Distribution: `keysight-scope-cli`

Console script: `keysight-scopes`

Module entry point: `python -m keysight_scope_cli.cli`

## Install For Development

From the repository root:

```powershell
uv pip install -e "packages/core[dev]" -e packages/cli
```

## Basic Usage

```powershell
keysight-scopes identify --simulate --json
python -m keysight_scope_cli.cli identify --simulate --json
```

Commands that accept instrument access support dry-run, simulate, and live
modes. Agents and automation should use dry-run and simulate before requesting
real hardware access. JSON payloads include `schema_version: 1` and
`timestamp_utc`.

Shared machine contracts remain at root:

- `docs/contracts/common-cli-jsonl-contract.md`
- `docs/contracts/scopes-cli-jsonl-contract.md`
- `docs/contracts/common-worker-protocol.md`
- `docs/contracts/scopes-worker-contract.md`
- `docs/contracts/common-orchestrator-workflows.md`
- `docs/contracts/scopes-orchestrator-workflows.md`

## Docs

- Command guide: `docs/README_CLI_EN.md`
- CLI integration notes: `docs/cli-integration.md`
