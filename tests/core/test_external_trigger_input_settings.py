import math

import pytest

import keysight_scope_core
from keysight_scope_core.errors import ParameterValidationError, TriggerResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.trigger import (
    ExternalTriggerProbeController,
    ExternalTriggerProbeState,
    ExternalTriggerSettingsController,
    ExternalTriggerSettingsState,
    ExternalTriggerUnitsController,
    ExternalTriggerUnitsState,
    external_trigger_probe_command,
    external_trigger_probe_query,
    external_trigger_settings_query,
    external_trigger_units_command,
    external_trigger_units_query,
    parse_external_trigger_settings,
)


@pytest.mark.parametrize(("value", "text"), [(1, "1"), (0.001, "0.001"), (12.5, "12.5")])
def test_external_trigger_probe_builders_accept_any_finite_positive_attenuation(value, text):
    assert external_trigger_probe_command(value) == f":EXTernal:PROBe {text}"
    assert external_trigger_probe_query() == ":EXTernal:PROBe?"


@pytest.mark.parametrize(
    "value", [True, False, None, "10", 0, -1, math.nan, math.inf, -math.inf, pytest.param(10**10000, id="huge-integer")]
)
def test_external_trigger_probe_rejects_nonpositive_or_nonfinite_values(value):
    with pytest.raises(ParameterValidationError):
        external_trigger_probe_command(value)


def test_external_trigger_probe_controller_parses_scientific_readback_and_preserves_raw_value():
    backend = FakeBackend(responses={":EXTernal:PROBe?": " +1.00000000E+01 "})
    controller = ExternalTriggerProbeController(backend)

    controller.configure(attenuation=10)
    state = controller.query()

    assert backend.history == [":EXTernal:PROBe 10", ":EXTernal:PROBe?"]
    assert state == ExternalTriggerProbeState(10.0, "+1.00000000E+01")
    assert state.to_json() == {"attenuation": 10.0, "raw_attenuation": "+1.00000000E+01"}


@pytest.mark.parametrize("raw", ["", "abc", "NaN", "INF", "-INF"])
def test_external_trigger_probe_rejects_invalid_query_readbacks(raw):
    with pytest.raises(TriggerResponseError):
        ExternalTriggerProbeController(FakeBackend(responses={":EXTernal:PROBe?": raw})).query()


@pytest.mark.parametrize(
    ("units", "command"), [("volts", ":EXTernal:UNITs VOLT"), ("amps", ":EXTernal:UNITs AMPere")]
)
def test_external_trigger_units_builders_accept_only_canonical_values(units, command):
    assert external_trigger_units_command(units) == command
    assert external_trigger_units_query() == ":EXTernal:UNITs?"


@pytest.mark.parametrize("units", ["volt", "amp", "AMP", "AMPere", "voltage", "current", None, True])
def test_external_trigger_units_reject_aliases_and_invalid_values(units):
    with pytest.raises(ParameterValidationError):
        external_trigger_units_command(units)


@pytest.mark.parametrize(("raw", "normalized"), [(" VOLT ", "volts"), ("amp", "amps"), ("AMPere", "amps"), ("future", None)])
def test_external_trigger_units_query_normalizes_known_readbacks_and_preserves_unknown(raw, normalized):
    state = ExternalTriggerUnitsController(FakeBackend(responses={":EXTernal:UNITs?": raw})).query()
    assert state == ExternalTriggerUnitsState(normalized, raw.strip())


@pytest.mark.parametrize(
    "raw",
    [
        ":EXT:BWL 0;RANG +8E+00;UNIT VOLT;PROB +1.000E+00",
        ":EXTernal:PROBe +1.000E+00;EXTernal:UNITs VOLT;EXTernal:RANGe +8E+00;EXTernal:BWLimit OFF",
        "UNIT AMP;PROB +1.000E+01;BWL 0;RANG +8.000E+01",
        " UNKNOWN 7 ; UNIT AMPere ; FUTURE YES ; PROB +1 ; RANG +8 ; BWL OFF ; NEXT tail ",
    ],
)
def test_external_trigger_settings_parser_handles_headers_order_whitespace_and_unknown_fields(raw):
    state = parse_external_trigger_settings(raw)
    assert state.probe_attenuation in {1.0, 10.0}
    assert state.range_value in {8.0, 80.0}
    assert state.units in {"volts", "amps"}
    assert state.bandwidth_limit_enabled is False
    assert state.raw_response == raw.strip()


def test_external_trigger_settings_parser_ignores_unknown_field_without_value():
    raw = "UNIT VOLT;FUTURE;RANG 8;PROB 1;BWL 0"
    state = parse_external_trigger_settings(raw)

    assert state.units == "volts"
    assert state.range_value == 8.0
    assert state.probe_attenuation == 1.0
    assert state.bandwidth_limit_enabled is False
    assert state.raw_response == raw


def test_external_trigger_settings_parser_does_not_treat_known_header_prefix_as_known():
    state = parse_external_trigger_settings("BWLEXTRA;UNIT VOLT")

    assert state.units == "volts"
    assert state.bandwidth_limit_enabled is None


def test_external_trigger_settings_parser_uses_last_duplicate_known_field():
    state = parse_external_trigger_settings("RANG 1;RANGE 8;PROB 1;UNIT VOLT;BWL 1;BWL OFF")
    assert state.range_value == 8.0
    assert state.bandwidth_limit_enabled is False


def test_external_trigger_settings_parser_allows_missing_known_fields_and_preserves_raw_response():
    state = parse_external_trigger_settings("UNIT FUTURE;UNKNOWN field")
    assert state == ExternalTriggerSettingsState(None, None, None, None, "UNIT FUTURE;UNKNOWN field")


@pytest.mark.parametrize(
    "raw",
    ["", ";", "RANG nonsense", "PROB NaN", "BWL MAYBE", "UNIT", "RANG", "PROB", "BWL"],
)
def test_external_trigger_settings_parser_rejects_malformed_known_or_structural_fields(raw):
    with pytest.raises(TriggerResponseError):
        parse_external_trigger_settings(raw)


def test_external_trigger_settings_controller_scope_api_and_public_exports():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4034A,SIM000000,07.20",
            ":EXTernal?": ":EXT:BWL 0;RANG +8E+00;UNIT VOLT;PROB +1.000E+00",
            ":EXTernal:PROBe?": "1",
            ":EXTernal:UNITs?": "VOLT",
        }
    )
    scope = KeysightScope(backend)
    scope.query_idn()
    scope.configure_external_trigger_probe(10)
    probe = scope.query_external_trigger_probe()
    scope.configure_external_trigger_units("amps")
    units = scope.query_external_trigger_units()
    settings = scope.query_external_trigger_settings()

    assert backend.history[-5:] == [
        ":EXTernal:PROBe 10", ":EXTernal:PROBe?", ":EXTernal:UNITs AMPere", ":EXTernal:UNITs?", ":EXTernal?"
    ]
    assert probe.attenuation == 1.0
    assert units.units == "volts"
    assert settings.range_value == 8.0
    assert external_trigger_settings_query() == ":EXTernal?"
    assert keysight_scope_core.ExternalTriggerProbeController is ExternalTriggerProbeController
    assert keysight_scope_core.ExternalTriggerProbeState is ExternalTriggerProbeState
    assert keysight_scope_core.ExternalTriggerUnitsController is ExternalTriggerUnitsController
    assert keysight_scope_core.ExternalTriggerUnitsState is ExternalTriggerUnitsState
    assert keysight_scope_core.ExternalTriggerSettingsController is ExternalTriggerSettingsController
    assert keysight_scope_core.ExternalTriggerSettingsState is ExternalTriggerSettingsState
