import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.dvm import (
    DVM_INVALID_SENTINEL_REASON,
    DvmController,
    dvm_auto_range_command,
    dvm_auto_range_query,
    dvm_current_query,
    dvm_enable_command,
    dvm_enable_query,
    dvm_mode_command,
    dvm_mode_query,
    dvm_query_commands,
    dvm_source_command,
    dvm_source_query,
    normalize_dvm_mode,
    parse_dvm_bool,
    parse_dvm_current,
    parse_dvm_mode,
    parse_dvm_source,
)
from keysight_scope_core.errors import ParameterValidationError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient


def test_dvm_v1_scpi_builders_use_only_common_commands():
    capabilities = capabilities_for_model("DSOX4024A")
    assert dvm_enable_command(True) == ":DVM:ENABle 1"
    assert dvm_enable_command(False) == ":DVM:ENABle 0"
    assert dvm_enable_query() == ":DVM:ENABle?"
    assert dvm_source_command(1, capabilities=capabilities) == ":DVM:SOURce CHANnel1"
    assert dvm_source_query() == ":DVM:SOURce?"
    assert dvm_mode_command("dc") == ":DVM:MODE DC"
    assert dvm_mode_command("dc-rms") == ":DVM:MODE DCRMs"
    assert dvm_mode_command("ac-rms") == ":DVM:MODE ACRMs"
    assert dvm_mode_query() == ":DVM:MODE?"
    assert dvm_auto_range_command(True) == ":DVM:ARANge 1"
    assert dvm_auto_range_query() == ":DVM:ARANge?"
    assert dvm_current_query() == ":DVM:CURRent?"
    assert dvm_query_commands() == [
        ":DVM:ENABle?",
        ":DVM:SOURce?",
        ":DVM:MODE?",
        ":DVM:ARANge?",
        ":DVM:CURRent?",
    ]
    assert all("FREQ" not in command.upper() for command in dvm_query_commands())
    assert all("COUNTER" not in command.upper() for command in dvm_query_commands())


@pytest.mark.parametrize("raw, expected", [("1", True), ("+1", True), ("ON", True), ("0", False), ("OFF", False)])
def test_parse_dvm_bool(raw, expected):
    assert parse_dvm_bool(raw) is expected


@pytest.mark.parametrize("raw, expected", [("CHAN1", 1), ("CHANnel2", 2), ("CHANNEL4", 4)])
def test_parse_dvm_source_common_keysight_forms(raw, expected):
    assert parse_dvm_source(raw) == expected


@pytest.mark.parametrize("raw, expected", [("DC", "dc"), ("DCRMS", "dc-rms"), ("DCRMs", "dc-rms"), ("ACRMS", "ac-rms"), ("ACRMs", "ac-rms")])
def test_parse_dvm_mode_common_keysight_forms(raw, expected):
    assert parse_dvm_mode(raw) == expected


@pytest.mark.parametrize("mode", ["frequency", "freq", "dcrms", "acrms", "DCRMS", "ACRMS", "unknown"])
def test_dvm_mode_rejects_aliases_and_frequency(mode):
    with pytest.raises(ParameterValidationError):
        normalize_dvm_mode(mode)


@pytest.mark.parametrize("model, channel", [("DSOX4022A", 3), ("DSOX4024A", 5), ("DSOX4024A", 0), ("DSOX4024A", -1)])
def test_dvm_source_rejects_invalid_analog_channel(model, channel):
    with pytest.raises(ParameterValidationError):
        dvm_source_command(channel, capabilities=capabilities_for_model(model))


def test_dvm_current_preserves_invalid_sentinel():
    reading = parse_dvm_current("9.9E+37")
    assert reading.value is None
    assert reading.raw_value == "9.9E+37"
    assert reading.valid is False
    assert reading.reason == DVM_INVALID_SENTINEL_REASON


def test_dvm_controller_aggregate_query_preserves_normalized_and_raw_fields():
    backend = FakeBackend(
        responses={
            ":DVM:ENABle?": "1",
            ":DVM:SOURce?": "CHANnel2",
            ":DVM:MODE?": "DCRMs",
            ":DVM:ARANge?": "0",
            ":DVM:CURRent?": "+1.23400000E+000",
        }
    )
    controller = DvmController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    state = controller.query()

    assert state.to_json() == {
        "enabled": True,
        "source_channel": 2,
        "mode": "dc-rms",
        "auto_range_enabled": False,
        "value": 1.234,
        "valid": True,
        "reason": None,
        "raw": {
            "enabled": "1",
            "source": "CHANnel2",
            "mode": "DCRMs",
            "auto_range": "0",
            "current": "+1.23400000E+000",
        },
    }
    assert backend.history == dvm_query_commands()
