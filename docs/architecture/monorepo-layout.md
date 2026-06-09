# Monorepo Layout

Last updated: 2026-06-04

```text
.
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
