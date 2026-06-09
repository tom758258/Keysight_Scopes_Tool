# Monorepo Layout

Last updated: 2026-06-10

```text
.
|-- AGENTS.md
|-- docs/
|   |-- architecture/
|   |-- contracts/
|-- packages/
|   |-- core/
|   |   |-- README.md
|   |   |-- CHANGELOG.md
|   |   |-- docs/
|   |   |-- src/keysight_scope_core/
|   |   |-- tests/
|   |-- cli/
|   |   |-- README.md
|   |   |-- CHANGELOG.md
|   |   |-- docs/
|   |   |-- src/keysight_scope_cli/
|   |   |-- tests/
|   |-- webui/
|       |-- README.md
|       |-- CHANGELOG.md
|       |-- src/keysight_scope_webui/
|       |-- tests/
|-- scripts/
```

Root-level documents are for repository orientation, architecture, and shared
contracts. Package-local documents are the canonical place for public package
behavior and adapter guidance.

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
