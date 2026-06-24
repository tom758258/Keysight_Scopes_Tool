# Monorepo Layout

Last updated: 2026-06-10

```text
.
|-- AGENTS.md
|-- CHANGELOG.md
|-- docs/
|   |-- architecture/
|   |-- cli/
|   |-- contracts/
|   |-- core/
|   |-- webui/
|-- pyproject.toml
|-- scripts/
|-- src/
|   |-- keysight_scope_cli/
|   |-- keysight_scope_core/
|   |-- keysight_scope_webui/
|-- tests/
|   |-- cli/
|   |-- core/
|   |-- webui/
```

Root-level documents are for repository orientation, architecture, and shared
contracts. Area-specific documents under `docs/core/`, `docs/cli/`, and
`docs/webui/` are the canonical place for public import package behavior and
adapter guidance. The root `pyproject.toml` is the only package metadata file.

## Documentation Publication Boundary

Only Git-tracked documents are canonical and available in a public clone.
Repository-wide policy and shared contracts belong in tracked root documents
or `docs/`; package-specific behavior belongs in the owning package README or
docs directory.

`Local/` is an ignored, local-only workspace. Its `publication-hold/`
directory may contain private historical snapshots, but those files are not
current instructions or public documentation. Documentation ownership tests
must not depend on `Local/` existing or require historical/private filenames
to be absent. Do not move a document into an ignored path to satisfy a test.
