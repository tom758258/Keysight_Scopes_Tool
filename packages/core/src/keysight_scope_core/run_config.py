"""Run-mode resolution and backend opening helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Literal, Mapping, Sequence

from .capabilities import ScopeCapabilities, capabilities_for_model
from .errors import KeysightScopeError
from .scope import KeysightScope
from .simulator_backend import SimulatorBackend
from .simulator_config import simulator_backend_kwargs, validate_simulator_args

RunMode = Literal["dry_run", "simulate", "live"]


@dataclass(frozen=True)
class RunModeOptions:
    simulate: bool = False
    dry_run: bool = False
    live: bool = False
    model: str = "DSOX4024A"
    simulate_signals: Sequence[str] = field(default_factory=tuple)
    simulate_preset: str | None = None
    simulate_scenario: str | None = None
    simulate_system_errors: Sequence[str] = field(default_factory=tuple)
    simulate_binary_transfer_failure: bool = False
    simulate_invalid_measurement_channels: Sequence[str] = field(default_factory=tuple)
    simulate_display_off_channels: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResolvedRunConfig:
    mode: RunMode
    model: str
    capabilities: ScopeCapabilities | None
    resource: str | None
    visa_library: str | None = None
    options: RunModeOptions = field(default_factory=RunModeOptions)


def resolve_run_mode(options: RunModeOptions) -> RunMode:
    if options.simulate and options.dry_run:
        raise KeysightScopeError("--simulate cannot be combined with --dry-run")
    if options.simulate_signals and not options.simulate:
        raise KeysightScopeError("--simulate-signal can only be used with --simulate")
    for value, option in (
        (options.simulate_preset, "--simulate-preset"),
        (options.simulate_scenario, "--simulate-scenario"),
        (options.simulate_system_errors, "--simulate-system-error"),
        (
            options.simulate_binary_transfer_failure,
            "--simulate-binary-transfer-failure",
        ),
        (options.simulate_invalid_measurement_channels, "--simulate-invalid-measurement"),
        (options.simulate_display_off_channels, "--simulate-display-off"),
    ):
        if value and not options.simulate:
            raise KeysightScopeError(f"{option} can only be used with --simulate")
    if options.simulate:
        capabilities = capabilities_for_model(options.model)
        validate_simulator_args(options, capabilities)
        return "simulate"
    if options.dry_run:
        capabilities_for_model(options.model)
        return "dry_run"
    return "live"


def resolve_resource(
    mode: RunMode,
    explicit_resource: str | None,
    model: str,
    environ: Mapping[str, str] = os.environ,
) -> str | None:
    if mode == "simulate":
        return explicit_resource or f"SIM::{model}::INSTR"
    if mode == "dry_run":
        return explicit_resource or f"DRY::{model}::INSTR"
    return explicit_resource or environ.get("KEYSIGHT_SCOPE_RESOURCE")


def require_resource(
    mode: RunMode,
    explicit_resource: str | None,
    model: str,
    environ: Mapping[str, str] = os.environ,
) -> str:
    resource = resolve_resource(mode, explicit_resource, model, environ)
    if resource is None:
        raise KeysightScopeError("--resource is required unless KEYSIGHT_SCOPE_RESOURCE is set")
    return resource


def make_simulator_backend(options: RunModeOptions, resource: str) -> SimulatorBackend:
    kwargs = simulator_backend_kwargs(
        options,
        resource,
        capabilities_for_model(options.model),
    )
    return SimulatorBackend(**kwargs)


def open_scope_for_run(config: ResolvedRunConfig) -> KeysightScope:
    if config.mode == "dry_run":
        raise KeysightScopeError("dry-run does not open a backend")
    if config.resource is None:
        raise KeysightScopeError("--resource is required unless KEYSIGHT_SCOPE_RESOURCE is set")
    if config.mode == "simulate":
        return KeysightScope(make_simulator_backend(config.options, config.resource))
    return KeysightScope.open(config.resource, visa_library=config.visa_library)
