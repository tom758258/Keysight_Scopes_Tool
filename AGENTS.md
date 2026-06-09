# Agent Instructions

These instructions are long-term rules for coding agents working in this
repository. Write repository documentation in English unless the user requests
another language.

## Canonical Files and Publication Boundary

- Only Git-tracked files are canonical project documentation.
- `Local/` is an ignored, local-only workspace. In particular,
  `Local/publication-hold/` contains private historical snapshots, not current
  instructions or public documentation.
- Do not move documents into `Local/` or another ignored path to satisfy
  ownership tests. Fix the public documentation boundary or the test instead.
- Keep repository-wide contracts in `docs/contracts/`, package behavior in the
  owning package README or docs directory, and repository policy in tracked
  root or `docs/` files.

## Development

- Keep changes scoped to the requested task and follow existing package
  patterns.
- Prefer clear modules and simple public APIs over speculative abstractions.
- Use type hints and concise docstrings for public Python APIs.
- Use Python logging for internal command logs; reserve direct output for CLI
  rendering.
- Use the editable development setup documented in `README.md`:
  `uv pip install -e "packages/core[dev]" -e packages/cli -e packages/webui`.
- Do not add or commit `uv.lock` unless the root project is explicitly
  converted into a uv workspace.

## Instrument Safety

This project controls real oscilloscopes through VISA/SCPI. Real hardware access
is opt-in and requires explicit user approval.

- Prefer `keysight-scopes --dry-run --json`, then
  `keysight-scopes --simulate --json`, before live commands.
- For one-shot commands, an explicit `--resource ...` or
  `KEYSIGHT_SCOPE_RESOURCE` selects and opts in to that single live instrument;
  `--live` is an optional compatibility flag.
- `list-resources --live-only` is the only discovery command that may open
  each enumerated resource.
- Live workers require both `--live` and `--resource`.
- Agents must still obtain explicit user approval before accessing real
  hardware.
- Do not use `*RST` by default.
- Validate parameters before sending SCPI commands.
- Keep normal automated tests independent of real hardware.
- Ask before changing reset behavior, VISA timeout defaults, trigger wait
  strategy, acquisition mode, waveform defaults, long-running acquisition,
  return-to-local behavior, or behavior that can leave an instrument stopped,
  locked, or with changed front-panel state.
- Do not claim hardware validation unless it was run on a real instrument.

For CLI and worker automation behavior, use the tracked contracts in
`docs/contracts/` as the source of truth. Parse JSON output from stdout; SCPI
diagnostics belong on stderr.

## Testing

- Add focused tests for new behavior.
- Prefer `FakeBackend` and simulator tests for SCPI ordering, response parsing,
  and workflows.
- Run tests through `.\scripts\run-tests.ps1`; pass pytest paths or options
  after the script path for focused runs.
- Documentation ownership tests should positively verify canonical public
  files and durable boundaries. They must not require private files to be
  absent or depend on `Local/` existing.
- If tests cannot be run, report that clearly.

## Core and CLI Boundary

- Keep `packages/cli/src/keysight_scope_cli/cli.py` as the adapter for argparse
  parsing, stdout/stderr rendering, process exit codes, and JSON envelopes.
- Put dry-run SCPI and artifact planning in
  `packages/core/src/keysight_scope_core/planning.py`.
- Put mode resolution and backend opening rules in
  `packages/core/src/keysight_scope_core/run_config.py`.
- Put reusable workflows in
  `packages/core/src/keysight_scope_core/operations.py`. Core operations must
  not import `argparse`, read `sys.argv`, or print directly.
- Put shared output path and write wrappers in
  `packages/core/src/keysight_scope_core/output_files.py`.
- Keep model-specific behavior in capability profiles and explicit feature
  guards rather than scattering model conditionals through feature modules.
