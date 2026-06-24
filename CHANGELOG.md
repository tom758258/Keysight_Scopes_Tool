# Keysight Scopes Changelog

## 0.1.0

- Publishes one `keysight-scopes` distribution containing the
  `keysight_scope_core`, `keysight_scope_cli`, and `keysight_scope_webui`
  import packages.
- Maintains the current Core runtime for Keysight InfiniiVision oscilloscope
  automation.
- Adds the `keysight-scopes` console script and
  `python -m keysight_scope_cli.cli` module entry point.
- Maintains the current WebUI package skeleton without adding a WebUI runtime
  dependency or console command.
- Public documentation covers the Core API surface, CLI command usage,
  integration notes, JSON behavior, automation safety, and WebUI ownership.
