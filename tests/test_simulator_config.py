import argparse
import json

import pytest

from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.errors import KeysightScopeError
from keysight_scope.simulator_config import (
    load_scenario,
    parse_config,
    simulator_backend_kwargs,
)


CAPABILITIES = capabilities_for_model("DSOX4024A")


def _args(**overrides):
    values = {
        "model": "DSOX4024A",
        "simulate_preset": None,
        "simulate_scenario": None,
        "simulate_signals": [],
        "simulate_system_errors": [],
        "simulate_binary_transfer_failure": False,
        "simulate_invalid_measurement_channels": [],
        "simulate_display_off_channels": [],
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_parse_config_accepts_public_scenario_shape():
    parsed = parse_config(
        {
            "signals": {
                "CH1": {
                    "shape": "sine",
                    "frequency_hz": 1000,
                    "vpp_v": 1.0,
                    "offset_v": 0.0,
                    "phase_deg": 0.0,
                    "noise_rms_v": 0.02,
                }
            },
            "channels": {"CH1": {"display": True, "scale_v_per_div": 0.5, "offset_v": 0}},
            "timebase": {"scale_s_per_div": 0.001, "position_s": 0.0},
            "trigger": {"source_channel": "CH1", "level_v": 0.0, "slope": "positive"},
            "acquisition": {"type": "average", "count": 16},
            "errors": {
                "system_errors": [{"code": -113, "message": "Undefined header"}],
                "binary_transfer_failure": True,
                "invalid_measurement_channels": ["CH2"],
                "display_off_channels": ["CH1"],
            },
        },
        CAPABILITIES,
    )

    assert parsed["signals"][1].noise_rms_v == 0.02
    assert parsed["channel_display"][1] is False
    assert parsed["channel_scale"][1] == 0.5
    assert parsed["timebase_scale"] == 0.001
    assert parsed["trigger_source"] == 1
    assert parsed["trigger_slope"] == "POSitive"
    assert parsed["acquisition_type"] == "AVERage"
    assert parsed["acquisition_count"] == 16
    assert parsed["system_errors"] == ['-113,"Undefined header"']
    assert parsed["invalid_measurement_channels"] == {2}
    assert ":WAVeform:DATA?" in parsed["binary_failures"]


def test_load_scenario_rejects_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(KeysightScopeError, match="invalid --simulate-scenario JSON"):
        load_scenario(path)


def test_parse_config_rejects_unknown_keys_and_bad_channels():
    with pytest.raises(KeysightScopeError, match="unknown scenario signals CH1 key"):
        parse_config({"signals": {"CH1": {"bogus": 1}}}, CAPABILITIES)

    with pytest.raises(KeysightScopeError, match="channel 5 is not available"):
        parse_config({"errors": {"display_off_channels": ["CH5"]}}, CAPABILITIES)


def test_simulator_backend_kwargs_merges_preset_scenario_and_cli_overrides(tmp_path):
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "preset": "phase-shifted-pair",
                "signals": {"CH1": {"vpp_v": 1.5, "noise_rms_v": 0.01}},
                "errors": {"invalid_measurement_channels": ["CH2"]},
            }
        ),
        encoding="utf-8",
    )

    kwargs = simulator_backend_kwargs(
        _args(
            simulate_preset="noisy-sine",
            simulate_scenario=str(scenario_path),
            simulate_signals=["CH1:square:2000:3.0:0.25:15:0.02"],
            simulate_invalid_measurement_channels=["CH3"],
        ),
        "SIM::DSOX4024A::INSTR",
        CAPABILITIES,
    )

    assert kwargs["model"] == "DSOX4024A"
    assert kwargs["signals"][1].shape == "square"
    assert kwargs["signals"][1].frequency_hz == 2000
    assert kwargs["signals"][1].vpp_v == 3.0
    assert kwargs["signals"][2].phase_deg == 90.0
    assert kwargs["invalid_measurement_channels"] == {2, 3}


def test_simulator_backend_kwargs_rejects_bad_cli_system_error():
    with pytest.raises(KeysightScopeError, match="must be an integer"):
        simulator_backend_kwargs(
            _args(simulate_system_errors=["not-int"]),
            "SIM::DSOX4024A::INSTR",
            CAPABILITIES,
        )
