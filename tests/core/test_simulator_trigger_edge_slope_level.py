import copy

import pytest

from keysight_scope_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def _unrelated_trigger_state(backend):
    return {
        "mode": backend.trigger_mode,
        "source": backend.trigger_edge_source_raw,
        "levels": copy.deepcopy(backend.trigger_levels),
        "level": backend.trigger_level,
        "coupling": backend.trigger_edge_coupling,
        "reject": backend.trigger_edge_reject,
        "sweep": backend.trigger_sweep,
        "noise_reject": backend.trigger_noise_reject,
        "hf_reject": backend.trigger_hf_reject,
        "holdoff": backend.trigger_holdoff,
        "run_state": backend.run_state,
    }


@pytest.mark.parametrize(
    ("command", "readback"),
    [
        ("POSitive", "POS"),
        ("NEGative", "NEG"),
        ("EITHer", "EITH"),
        ("ALTernate", "ALT"),
    ],
)
def test_simulator_edge_slope_roundtrip_is_isolated(command, readback):
    backend = SimulatorBackend(model="DSOX4034A")
    before = _unrelated_trigger_state(backend)

    backend.write(f":TRIGger:EDGE:SLOPe {command}")
    assert backend.query(":TRIGger:EDGE:SLOPe?") == readback

    assert _unrelated_trigger_state(backend) == before
    assert backend.history == [
        f":TRIGger:EDGE:SLOPe {command}",
        ":TRIGger:EDGE:SLOPe?",
    ]
    assert ":TRIGger:MODE EDGE" not in backend.history


def test_simulator_edge_slope_rejects_invalid_values():
    with pytest.raises(SimulatorBackendError):
        SimulatorBackend().write(":TRIGger:EDGE:SLOPe RISING")


def test_simulator_edge_level_is_source_qualified_and_keeps_inactive_source_independent():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    baseline = _unrelated_trigger_state(backend)

    backend.write(":TRIGger:EDGE:LEVel -0.25,CHANnel2")
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel2") == "-0.25"
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0"

    assert backend.trigger_levels[2] == -0.25
    assert 1 not in backend.trigger_levels
    assert backend.trigger_level == baseline["level"]
    assert backend.trigger_edge_source_raw == "CHANnel1"
    after = _unrelated_trigger_state(backend)
    assert after["mode"] == baseline["mode"]
    assert after["source"] == baseline["source"]
    assert after["coupling"] == baseline["coupling"]
    assert after["reject"] == baseline["reject"]
    assert after["sweep"] == baseline["sweep"]
    assert after["noise_reject"] == baseline["noise_reject"]
    assert after["hf_reject"] == baseline["hf_reject"]
    assert after["holdoff"] == baseline["holdoff"]
    assert after["run_state"] == baseline["run_state"]
    assert backend.history == [
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel -0.25,CHANnel2",
        ":TRIGger:EDGE:LEVel? CHANnel2",
        ":TRIGger:EDGE:LEVel? CHANnel1",
    ]


def test_simulator_edge_level_updates_active_analog_level_only_for_active_channel():
    backend = SimulatorBackend(model="DSOX4034A")

    backend.write(":TRIGger:EDGE:LEVel 0.5,CHANnel1")
    backend.write(":TRIGger:EDGE:LEVel 0,CHANnel2")

    assert backend.trigger_level == 0.5
    assert backend.trigger_levels == {1: 0.5, 2: 0.0}
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0.5"
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel2") == "0"


def test_simulator_unqualified_edge_level_write_syncs_active_analog_channel():
    backend = SimulatorBackend(model="DSOX4034A")

    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    backend.write(":TRIGger:EDGE:LEVel 0.5,CHANnel1")
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0.5"

    backend.write(":TRIGger:EDGE:LEVel 0.2")

    assert backend.trigger_level == 0.2
    assert backend.trigger_levels[1] == 0.2
    assert backend.query(":TRIGger:EDGE:LEVel?") == "0.2"
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0.2"
    assert backend.trigger_edge_source_raw == "CHANnel1"
    assert backend.history == [
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel 0.5,CHANnel1",
        ":TRIGger:EDGE:LEVel? CHANnel1",
        ":TRIGger:EDGE:LEVel 0.2",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:LEVel? CHANnel1",
    ]


def test_simulator_analog_source_switch_activates_stored_channel_level():
    backend = SimulatorBackend(model="DSOX4034A")

    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    backend.write(":TRIGger:EDGE:LEVel 0.1")
    backend.write(":TRIGger:EDGE:LEVel 0.8,CHANnel2")
    assert backend.trigger_level == 0.1

    backend.write(":TRIGger:EDGE:SOURce CHANnel2")

    assert backend.trigger_edge_source_raw == "CHANnel2"
    assert backend.trigger_level == 0.8
    assert backend.query(":TRIGger:EDGE:LEVel?") == "0.8"
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0.1"
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel2") == "0.8"
    assert backend.history == [
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel 0.1",
        ":TRIGger:EDGE:LEVel 0.8,CHANnel2",
        ":TRIGger:EDGE:SOURce CHANnel2",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:LEVel? CHANnel1",
        ":TRIGger:EDGE:LEVel? CHANnel2",
    ]


def test_simulator_analog_source_switch_without_stored_level_keeps_global_fallback():
    backend = SimulatorBackend(model="DSOX4034A")

    backend.write(":TRIGger:EDGE:LEVel 0.1")
    backend.write(":TRIGger:EDGE:SOURce CHANnel2")

    assert backend.trigger_levels == {1: 0.1}
    assert backend.trigger_level == 0.1
    assert backend.query(":TRIGger:EDGE:LEVel?") == "0.1"
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel1") == "0.1"
    # A channel without storage continues to use the legacy global fallback.
    assert backend.query(":TRIGger:EDGE:LEVel? CHANnel2") == "0.1"
    assert backend.history == [
        ":TRIGger:EDGE:LEVel 0.1",
        ":TRIGger:EDGE:SOURce CHANnel2",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:LEVel? CHANnel1",
        ":TRIGger:EDGE:LEVel? CHANnel2",
    ]


def test_simulator_unqualified_level_write_with_non_analog_source_does_not_update_storage():
    backend = SimulatorBackend(model="DSOX4034A")
    backend.write(":TRIGger:EDGE:LEVel 0.5,CHANnel1")
    stored_levels = copy.deepcopy(backend.trigger_levels)

    backend.write(":TRIGger:EDGE:SOURce EXTernal")
    backend.write(":TRIGger:EDGE:LEVel 0.2")

    assert backend.trigger_level == 0.2
    assert backend.trigger_levels == stored_levels
    assert backend.trigger_edge_source_raw == "EXT"
    assert backend.history == [
        ":TRIGger:EDGE:LEVel 0.5,CHANnel1",
        ":TRIGger:EDGE:SOURce EXTernal",
        ":TRIGger:EDGE:LEVel 0.2",
    ]


def test_simulator_edge_level_rejects_invalid_channel_and_nonfinite_value():
    backend = SimulatorBackend(model="DSOX2004A")

    with pytest.raises(SimulatorBackendError):
        backend.write(":TRIGger:EDGE:LEVel 0.5,CHANnel5")
    with pytest.raises(SimulatorBackendError):
        backend.write(":TRIGger:EDGE:LEVel NaN,CHANnel1")
