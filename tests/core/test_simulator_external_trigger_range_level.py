import copy

import pytest

from keysight_scope_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def _trigger_state(backend):
    return {
        "mode": backend.trigger_mode,
        "source": backend.trigger_edge_source_raw,
        "level": backend.trigger_level,
        "levels": copy.deepcopy(backend.trigger_levels),
        "external_range": backend.external_trigger_range,
        "external_level": backend.edge_external_level,
        "slope": backend.trigger_slope,
        "coupling": backend.trigger_edge_coupling,
        "reject": backend.trigger_edge_reject,
        "sweep": backend.trigger_sweep,
        "noise_reject": backend.trigger_noise_reject,
        "hf_reject": backend.trigger_hf_reject,
        "holdoff": backend.trigger_holdoff,
        "run_state": backend.run_state,
    }


def test_simulator_external_range_default_and_roundtrip_are_isolated():
    backend = SimulatorBackend(model="DSOX4034A")
    before = _trigger_state(backend)

    assert backend.query(":EXTernal:RANGe?") == "8"
    backend.write(":EXTernal:RANGe 1.6")
    assert backend.query(":EXTernal:RANGe?") == "1.6"

    after = _trigger_state(backend)
    assert after["external_range"] == 1.6
    for key in set(before) - {"external_range"}:
        assert after[key] == before[key]
    assert backend.history == [
        ":EXTernal:RANGe?",
        ":EXTernal:RANGe 1.6",
        ":EXTernal:RANGe?",
    ]


@pytest.mark.parametrize("command", [":EXTernal:RANGe 0", ":EXTernal:RANGe -1", ":EXTernal:RANGe NaN"])
def test_simulator_external_range_rejects_nonpositive_or_nonfinite_values(command):
    with pytest.raises(SimulatorBackendError):
        SimulatorBackend().write(command)


def test_simulator_external_level_is_independent_while_external_is_inactive():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:LEVel 0.1,CHANnel1")

    backend.write(":TRIGger:EDGE:LEVel 0.5,EXTernal")

    assert backend.trigger_edge_source_raw == "CHANnel1"
    assert backend.trigger_level == 0.1
    assert backend.trigger_levels == {1: 0.1}
    assert backend.edge_external_level == 0.5
    assert backend.query(":TRIGger:EDGE:LEVel? EXTernal") == "0.5"


def test_simulator_external_level_updates_global_only_when_external_is_active():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:SOURce EXTernal")
    backend.write(":TRIGger:EDGE:LEVel -0.5,EXTernal")

    assert backend.trigger_edge_source_raw == "EXT"
    assert backend.trigger_level == -0.5
    assert backend.edge_external_level == -0.5
    assert backend.trigger_levels == {}

    backend.write(":TRIGger:EDGE:LEVel 0.25")
    assert backend.trigger_level == 0.25
    assert backend.edge_external_level == 0.25
    assert backend.trigger_levels == {}


def test_simulator_legacy_level_does_not_update_external_storage_for_analog_or_line():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:LEVel 0.7,EXTernal")

    backend.write(":TRIGger:EDGE:LEVel 0.1")
    assert backend.trigger_levels == {1: 0.1}
    assert backend.edge_external_level == 0.7

    backend.write(":TRIGger:EDGE:SOURce LINE")
    backend.write(":TRIGger:EDGE:LEVel 0.2")
    assert backend.trigger_level == 0.2
    assert backend.trigger_levels == {1: 0.1}
    assert backend.edge_external_level == 0.7


def test_simulator_source_switch_loads_external_and_restores_analog_stored_levels():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:LEVel 0.1")
    backend.write(":TRIGger:EDGE:LEVel 0.8,EXTernal")

    backend.write(":TRIGger:EDGE:SOURce EXTernal")
    assert backend.trigger_level == 0.8
    assert backend.query(":TRIGger:EDGE:LEVel?") == "0.8"

    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    assert backend.trigger_level == 0.1
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0.1"
    assert backend.query(":TRIGger:EDGE:LEVel? EXTernal") == "0.8"
    assert backend.history == [
        ":TRIGger:EDGE:LEVel 0.1",
        ":TRIGger:EDGE:LEVel 0.8,EXTernal",
        ":TRIGger:EDGE:SOURce EXTernal",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel? CHANnel1",
        ":TRIGger:EDGE:LEVel? EXTernal",
    ]


def test_simulator_source_without_stored_level_preserves_global_fallback():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:LEVel 0.1")

    backend.write(":TRIGger:EDGE:SOURce CHANnel2")

    assert backend.trigger_levels == {1: 0.1}
    assert backend.trigger_level == 0.1
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel2") == "0.1"


def test_simulator_range_change_does_not_clamp_or_rewrite_external_level():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:LEVel 4,EXTernal")

    backend.write(":EXTernal:RANGe 1.6")

    assert backend.external_trigger_range == 1.6
    assert backend.edge_external_level == 4.0
    assert backend.query(":TRIGger:EDGE:LEVel? EXTernal") == "4"
