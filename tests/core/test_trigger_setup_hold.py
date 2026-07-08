import math

import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import ParameterValidationError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.trigger import (
    SetupHoldTriggerController,
    parse_setup_hold_slope_readback,
    parse_setup_hold_source,
    parse_trigger_mode,
    setup_hold_trigger_configure_commands,
    setup_hold_trigger_query_commands,
    validate_setup_hold_trigger_time,
)


def test_setup_hold_trigger_configure_sequence():
    commands = setup_hold_trigger_configure_commands(
        clock_channel=1,
        data_channel=2,
        slope="positive",
        setup_time_seconds=1e-9,
        hold_time_seconds=1e-9,
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE SHOLd",
        ":TRIGger:SHOLd:SOURce:CLOCk CHANnel1",
        ":TRIGger:SHOLd:SOURce:DATA CHANnel2",
        ":TRIGger:SHOLd:SLOPe POSitive",
        ":TRIGger:SHOLd:TIME:SETup 1e-09",
        ":TRIGger:SHOLd:TIME:HOLD 1e-09",
    ]


def test_setup_hold_trigger_query_sequence_is_explicit():
    assert setup_hold_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:SHOLd:SOURce:CLOCk?",
        ":TRIGger:SHOLd:SOURce:DATA?",
        ":TRIGger:SHOLd:SLOPe?",
        ":TRIGger:SHOLd:TIME:SETup?",
        ":TRIGger:SHOLd:TIME:HOLD?",
    ]


@pytest.mark.parametrize("raw", ["SHOL", "SHOLD", "SHOLd"])
def test_parse_trigger_mode_supports_setup_hold(raw):
    assert parse_trigger_mode(raw) == "setup-hold"


def test_parse_trigger_mode_preserves_other_as_unknown():
    assert parse_trigger_mode("EDGE") == "edge"
    assert parse_trigger_mode("WEIRD") is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CHAN1", ("channel", 1, None)),
        ("CHANnel2", ("channel", 2, None)),
        ("DIG0", ("digital", None, 0)),
        ("DIGital7", ("digital", None, 7)),
        ("pod", (None, None, None)),
        ("bus", (None, None, None)),
        ("unknown", (None, None, None)),
    ],
)
def test_parse_setup_hold_source_tolerates_raw_states(raw, expected):
    assert parse_setup_hold_source(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("POS", "positive"),
        ("POSitive", "positive"),
        ("NEG", "negative"),
        ("NEGative", "negative"),
    ],
)
def test_parse_setup_hold_slope_readbacks(raw, expected):
    assert parse_setup_hold_slope_readback(raw) == expected


@pytest.mark.parametrize("raw", ["+1.00000000E-09", "1e-9"])
def test_setup_hold_time_readbacks_parse_nr3(raw):
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "SHOL",
            ":TRIGger:SHOLd:SOURce:CLOCk?": "CHAN1",
            ":TRIGger:SHOLd:SOURce:DATA?": "CHAN2",
            ":TRIGger:SHOLd:SLOPe?": "POS",
            ":TRIGger:SHOLd:TIME:SETup?": raw,
            ":TRIGger:SHOLd:TIME:HOLD?": raw,
        }
    )
    controller = SetupHoldTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.setup_time_seconds == 1e-9
    assert state.hold_time_seconds == 1e-9


@pytest.mark.parametrize("model, channel", [("DSOX4022A", 2), ("DSOX4024A", 4)])
def test_setup_hold_validation_accepts_profile_channels(model, channel):
    commands = setup_hold_trigger_configure_commands(
        clock_channel=1,
        data_channel=channel,
        slope="negative",
        setup_time_seconds=2e-9,
        hold_time_seconds=3e-9,
        capabilities=capabilities_for_model(model),
    )

    assert commands[1] == ":TRIGger:SHOLd:SOURce:CLOCk CHANnel1"
    assert commands[2] == f":TRIGger:SHOLd:SOURce:DATA CHANnel{channel}"


@pytest.mark.parametrize("channel", [0, 3, 1.5, "D0", "DIG0", "digital0", "pod", "bus"])
def test_setup_hold_validation_rejects_invalid_channels(channel):
    with pytest.raises(ParameterValidationError):
        setup_hold_trigger_configure_commands(
            clock_channel=channel,
            data_channel=1,
            slope="positive",
            setup_time_seconds=1e-9,
            hold_time_seconds=1e-9,
            capabilities=capabilities_for_model("DSOX4022A"),
        )


def test_setup_hold_validation_rejects_invalid_slope():
    with pytest.raises(ParameterValidationError):
        setup_hold_trigger_configure_commands(
            clock_channel=1,
            data_channel=2,
            slope="rising",
            setup_time_seconds=1e-9,
            hold_time_seconds=1e-9,
            capabilities=capabilities_for_model("DSOX4024A"),
        )


@pytest.mark.parametrize("value", [0, -1e-9, math.nan, math.inf, "abc"])
def test_setup_hold_validation_rejects_invalid_times(value):
    with pytest.raises(ParameterValidationError):
        validate_setup_hold_trigger_time(value, "setup")


def test_setup_hold_controller_configures_and_queries_analog_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "SHOL",
            ":TRIGger:SHOLd:SOURce:CLOCk?": "CHAN1",
            ":TRIGger:SHOLd:SOURce:DATA?": "CHAN2",
            ":TRIGger:SHOLd:SLOPe?": "NEG",
            ":TRIGger:SHOLd:TIME:SETup?": "+1.00000000E-09",
            ":TRIGger:SHOLd:TIME:HOLD?": "+2.00000000E-09",
        }
    )
    controller = SetupHoldTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    controller.configure(
        clock_channel=1,
        data_channel=2,
        slope="negative",
        setup_time_seconds=1e-9,
        hold_time_seconds=2e-9,
    )
    state = controller.query()

    assert state.to_json() == {
        "mode": "setup-hold",
        "raw_mode": "SHOL",
        "clock_source": "CHAN1",
        "clock_source_kind": "channel",
        "clock_channel": 1,
        "clock_digital": None,
        "data_source": "CHAN2",
        "data_source_kind": "channel",
        "data_channel": 2,
        "data_digital": None,
        "slope": "negative",
        "setup_time_seconds": 1e-9,
        "hold_time_seconds": 2e-9,
        "raw": state.raw,
    }
    assert backend.history == [
        ":TRIGger:MODE SHOLd",
        ":TRIGger:SHOLd:SOURce:CLOCk CHANnel1",
        ":TRIGger:SHOLd:SOURce:DATA CHANnel2",
        ":TRIGger:SHOLd:SLOPe NEGative",
        ":TRIGger:SHOLd:TIME:SETup 1e-09",
        ":TRIGger:SHOLd:TIME:HOLD 2e-09",
        *setup_hold_trigger_query_commands(),
    ]


def test_setup_hold_query_tolerates_digital_and_unknown_sources():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "EDGE",
            ":TRIGger:SHOLd:SOURce:CLOCk?": "DIGital0",
            ":TRIGger:SHOLd:SOURce:DATA?": "BUS1",
            ":TRIGger:SHOLd:SLOPe?": "POS",
            ":TRIGger:SHOLd:TIME:SETup?": "+1.00000000E-09",
            ":TRIGger:SHOLd:TIME:HOLD?": "+1.00000000E-09",
        }
    )
    controller = SetupHoldTriggerController(
        SCPIClient(backend),
        capabilities_for_model("DSOX4024A"),
    )

    state = controller.query()

    assert state.mode == "edge"
    assert state.clock_source_kind == "digital"
    assert state.clock_channel is None
    assert state.clock_digital == 0
    assert state.data_source_kind is None
    assert state.data_channel is None
    assert state.data_digital is None
    assert backend.history == setup_hold_trigger_query_commands()
