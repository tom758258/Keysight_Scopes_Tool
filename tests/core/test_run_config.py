import pytest

from keysight_scope_core.errors import KeysightScopeError
from keysight_scope_core.run_config import (
    ResolvedRunConfig,
    RunModeOptions,
    open_scope_for_run,
    resolve_resource,
    resolve_run_mode,
)
from keysight_scope_core.simulator_backend import SimulatorBackend


def test_resolve_run_mode_rejects_simulate_and_dry_run():
    with pytest.raises(KeysightScopeError, match="cannot be combined"):
        resolve_run_mode(RunModeOptions(simulate=True, dry_run=True))


def test_resolve_run_mode_defaults_to_live():
    assert resolve_run_mode(RunModeOptions()) == "live"


@pytest.mark.parametrize(
    "options",
    [
        RunModeOptions(live=True, simulate=True),
        RunModeOptions(live=True, dry_run=True),
    ],
)
def test_resolve_run_mode_rejects_live_with_non_live_mode(options):
    with pytest.raises(KeysightScopeError, match="--live cannot be combined"):
        resolve_run_mode(options)


def test_simulator_options_require_simulate():
    with pytest.raises(KeysightScopeError, match="--simulate-preset"):
        resolve_run_mode(RunModeOptions(dry_run=True, simulate_preset="noisy-sine"))


def test_resource_fallbacks():
    assert resolve_resource("simulate", None, "DSOX4024A", {}) == "SIM::DSOX4024A::INSTR"
    assert resolve_resource("dry_run", None, "DSOX4024A", {}) == "DRY::DSOX4024A::INSTR"
    assert resolve_resource("live", None, "DSOX4024A", {"KEYSIGHT_SCOPE_RESOURCE": "USB"}) == "USB"


def test_dry_run_open_scope_is_blocked():
    config = ResolvedRunConfig(
        mode="dry_run",
        model="DSOX4024A",
        capabilities=None,
        resource="DRY::DSOX4024A::INSTR",
    )
    with pytest.raises(KeysightScopeError, match="dry-run"):
        open_scope_for_run(config)


def test_simulate_open_scope_uses_simulator():
    options = RunModeOptions(simulate=True, model="DSOX4024A")
    config = ResolvedRunConfig(
        mode="simulate",
        model="DSOX4024A",
        capabilities=None,
        resource="SIM::DSOX4024A::INSTR",
        options=options,
    )

    with open_scope_for_run(config) as scope:
        assert isinstance(scope.backend, SimulatorBackend)
