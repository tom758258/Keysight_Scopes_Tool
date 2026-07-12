from dataclasses import replace
import math

import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.demo import (
    DemoController,
    demo_function_command,
    demo_function_query,
    demo_output_command,
    demo_output_query,
    demo_phase_command,
    demo_phase_query,
    demo_query_commands,
    parse_demo_bool,
    parse_demo_function,
    parse_demo_phase,
)
from keysight_scope_core.errors import DemoResponseError, ParameterValidationError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient


def test_demo_scpi_builders():
    capabilities = capabilities_for_model("DSOX3024A")
    assert demo_output_command(True) == ":DEMO:OUTPut ON"
    assert demo_output_command(False) == ":DEMO:OUTPut OFF"
    assert demo_output_query() == ":DEMO:OUTPut?"
    assert demo_function_command("runt", capabilities=capabilities) == ":DEMO:FUNCtion RUNT"
    assert demo_function_query() == ":DEMO:FUNCtion?"
    assert demo_phase_command(90.0) == ":DEMO:FUNCtion:PHASe:PHASe 90"
    assert demo_phase_query() == ":DEMO:FUNCtion:PHASe:PHASe?"
    assert demo_query_commands() == [
        ":DEMO:FUNCtion?",
        ":DEMO:OUTPut?",
        ":DEMO:FUNCtion:PHASe:PHASe?",
    ]


@pytest.mark.parametrize("raw, expected", [("1", True), ("0", False), ("ON", True), ("OFF", False)])
def test_parse_demo_bool(raw, expected):
    assert parse_demo_bool(raw) is expected


@pytest.mark.parametrize("raw, expected", [("0", 0.0), ("90.5", 90.5), ("3.6E+2", 360.0)])
def test_parse_demo_phase(raw, expected):
    assert parse_demo_phase(raw) == expected


@pytest.mark.parametrize("raw", ["bad", "NaN", "Infinity"])
def test_parse_demo_phase_rejects_malformed_values(raw):
    with pytest.raises(DemoResponseError):
        parse_demo_phase(raw)


def test_demo_function_readback_normalization_and_unknown_preservation():
    assert parse_demo_function("RUNT") == ("runt", "RUNT")
    assert parse_demo_function(" glit ") == ("glitch", "GLIT")
    assert parse_demo_function("FUTURE") == (None, None)


def test_demo_aggregate_query_preserves_unknown_function_raw():
    backend = FakeBackend(
        responses={
            ":DEMO:FUNCtion?": "FUTURE",
            ":DEMO:OUTPut?": "1",
            ":DEMO:FUNCtion:PHASe:PHASe?": "90.0",
        }
    )
    state = DemoController(
        SCPIClient(backend), capabilities_for_model("DSOX4024A")
    ).query()
    assert state.function is None
    assert state.function_scpi is None
    assert state.function_raw == "FUTURE"
    assert state.enabled is True
    assert state.phase_degrees == 90.0
    assert backend.history == demo_query_commands()


def test_demo_controller_rejects_profile_without_demo_support():
    capabilities = replace(
        capabilities_for_model("DSOX4024A"), supports_demo=False
    )
    with pytest.raises(ParameterValidationError):
        DemoController(SCPIClient(FakeBackend()), capabilities)


@pytest.mark.parametrize(
    "function",
    ["sine", "clock", "runt", "transition", "setup-hold", "glitch", "edge-then-edge", "i2c", "uart", "spi", "can", "lin"],
)
def test_2000x_accepts_common_demo_functions(function):
    assert demo_function_command(
        function, capabilities=capabilities_for_model("DSOX2004A")
    ).startswith(":DEMO:FUNCtion ")


@pytest.mark.parametrize("function", ["i2s", "flexray", "arinc", "mil", "mil2"])
def test_2000x_rejects_3000x_demo_extensions(function):
    with pytest.raises(ParameterValidationError):
        demo_function_command(function, capabilities=capabilities_for_model("DSOX2004A"))


@pytest.mark.parametrize("model", ["DSOX3024A", "DSOX4024A"])
@pytest.mark.parametrize("function", ["i2s", "can-lin", "flexray", "arinc", "mil", "mil2"])
def test_3000x_and_4000x_accept_configured_demo_extensions(model, function):
    assert demo_function_command(
        function, capabilities=capabilities_for_model(model)
    ).startswith(":DEMO:FUNCtion ")


@pytest.mark.parametrize("degrees", [-0.1, 360.1, math.nan, math.inf, -math.inf, True])
def test_demo_phase_builder_rejects_invalid_values(degrees):
    with pytest.raises(ParameterValidationError):
        demo_phase_command(degrees)
