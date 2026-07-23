# Agent Instructions

These instructions are long-term rules for coding agents working in this
repository. Write repository documentation in English unless the user requests
another language.

## 1. Primary Project Documents

- Read the root `README.md`, root `pyproject.toml`, and the relevant area docs
  under `docs/core`, `docs/cli`, or `docs/webui` before implementing features.
- Read the root contracts in `docs/contracts/` before changing CLI, worker, or
  orchestrator behavior.
- Keep temporary planning notes, work-in-progress summaries, and validation
  records out of tracked public documentation.

## 2. Text File Hygiene Additions

- Do not use Windows PowerShell 5.1 `Set-Content -Encoding UTF8` or
  `Out-File -Encoding utf8` for final writes, because they can write a UTF-8
  BOM. If PowerShell 5.1 must write text, use
  `[System.IO.File]::WriteAllText(..., (New-Object System.Text.UTF8Encoding($false)))`.
- After rewriting files or editing non-ASCII text, verify the first three bytes
  are not `EF BB BF`, check for mojibake, and inspect `git diff` for unintended
  line-ending churn.

## 3. Project Direction

- This repository is a single-distribution project: `scopes-tool`.
- The public import packages are `scopes_tool_core`, `scopes_tool_cli`,
  and `scopes_tool_webui`.
- CLI and WebUI are parallel adapters over the shared Core runtime. Neither
  adapter owns SCPI behavior.
- Keep adapter behavior aligned with the root contracts and area docs.
- The main environment is Windows.
- Use the root editable development workflow documented in `README.md`:
  `uv pip install -e ".[all,dev]"`.
- Do not add or commit `uv.lock` unless the root project is explicitly
  converted into a uv workspace.
- Primary communication interfaces are USB and LAN through PyVISA.

## 4. Architecture Rules

- Do not scatter SCPI strings through CLI commands, examples, or test flows.
- Put SCPI behavior in Core modules and small command helpers.
- Use capability profiles and explicit feature guards for model-specific
  behavior.
- Do not assume every model in a series uses identical SCPI.
- Keep resource strings configurable. Do not hard-code real VISA addresses in
  committed code.
- Prefer fake-instrument tests for command generation and error paths before
  using hardware.
- Before WebUI UI or static work, read `docs/webui/README.md` and any
  WebUI-specific change rules if they exist.

## 5. Safety Rules

This project controls real oscilloscopes through VISA/SCPI. Real hardware
access is opt-in and requires explicit user approval.

- Prefer `scopes-tool --dry-run --json`, then `scopes-tool --simulate
  --json`, before live commands.
- For one-shot commands, an explicit `--resource ...` or
  `SCOPES_TOOL_RESOURCE` selects and opts in to that single live instrument;
  `--live` is an optional compatibility flag.
- `list-resources --live-only` is the only discovery command that may open each
  enumerated resource.
- Live workers require both `--live` and `--resource`.
- Do not use `*RST` by default.
- Validate parameters before sending SCPI commands.
- Keep normal automated tests independent of real hardware.
- Ask before changing reset behavior, VISA timeout defaults, trigger wait
  strategy, acquisition mode, waveform defaults, long-running acquisition
  behavior, return-to-local behavior, or any behavior that can leave an
  instrument stopped, locked, or with changed front-panel state.
- Do not claim hardware validation unless it was run on a real instrument.

## 6. Worker And Cleanup

- Preserve the current worker stop and cleanup semantics defined in
  `docs/contracts/scopes-worker-contract.md` and
  `docs/contracts/scopes-orchestrator-workflows.md`.
- Worker stdout is structured JSONL for lifecycle events; stderr is diagnostic
  text. Do not emit plain-text lifecycle output on stdout.
- Do not change queue admission, stop handling, cleanup ordering, artifact
  path rules, or worker lifecycle exit behavior without explicit confirmation.

## 7. Testing Rules

- Add focused tests for new behavior.
- Prefer `FakeBackend` and simulator tests for SCPI ordering, response parsing,
  worker workflows, and artifact generation.
- Run tests through `.\scripts\run-tests.ps1`; pass pytest paths or options
  after the script path for focused runs.
- For direct pytest, use `.\.venv\Scripts\python.exe -m pytest tests -q -p
  no:cacheprovider`.
- Documentation ownership tests should positively verify canonical public files
  and durable boundaries. They must not require private files to be absent or
  depend on `Local/` existing.
- If tests cannot be run, report that clearly.

## 8. Documentation Boundary

- Keep long-term agent rules in this file.
- Keep repository-wide contracts in `docs/contracts/`, area behavior in
  `docs/core`, `docs/cli`, and `docs/webui`, and repository policy in tracked
  root or `docs/` files.
- Keep `README.md` files available for engineering setup, build, validation,
  detailed reference, automation, and maintainer boundaries.
- Keep implementation progress, temporary notes, validation records, and
  hardware-specific operator context outside tracked public docs.
- Default documentation edits should update English `.md` source files only.
- Do not update Traditional Chinese or localized docs unless explicitly
  requested.
- Record reusable workflow and release information in the root README, area
  READMEs, testing guidelines, changelog, or contract documents.
- Do not commit private hardware notes, exact lab resource strings, instrument
  serial numbers, local machine details, or private lab IP addresses to public
  documentation.
- Do not duplicate large status sections here.

## 9. Repository Structure

- Root `pyproject.toml` is the only package metadata boundary. Do not recreate
  `packages/*/pyproject.toml` unless the user explicitly requests it.
- The repository is organized as a single-distribution project under the root
  `src/` directory:
  - `src/scopes_tool_core`: Core runtime layer.
  - `src/scopes_tool_cli`: Command line interface adapter.
  - `src/scopes_tool_webui`: Web interface skeleton.
- Never let `scopes_tool_core` import from `scopes_tool_cli` or
  `scopes_tool_webui`.
- CLI commands are invoked via `scopes-tool` or
  `python -m scopes_tool_cli.cli`.
