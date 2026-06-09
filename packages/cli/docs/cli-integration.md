# CLI Integration

The CLI package adapts `argparse.Namespace` inputs into Core run-mode,
planning, and operation calls. Keep parser-only naming and compatibility fields
in this package.

CLI-only fields include:

- `measurement_cli_name`
- command names such as `measure-log`, `capture-batch`, and `hardware-report`
- process return-code behavior
- stderr SCPI diagnostic handling
- parser validation messages

These fields are adapter behavior, not Core schema. Core receives normalized
requests and returns runtime data; the CLI decides how to render human text,
JSON stdout, stderr logs, and exit codes.

The installed console script remains:

```text
keysight-scopes = keysight_scope_cli.cli:main
```

The module form remains:

```powershell
python -m keysight_scope_cli.cli
```

CLI JSON behavior is documented by the root Scopes contract:
`docs/contracts/scopes-cli-jsonl-contract.md`. One-shot and lifecycle JSON
payloads include `schema_version: 1` and `timestamp_utc`.
