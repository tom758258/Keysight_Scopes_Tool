import pytest

from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.channel import (
    ChannelController,
    channel_display_command,
    channel_display_query,
    parse_channel_display,
    validate_analog_channel,
)
from keysight_scope.errors import ChannelResponseError, ParameterValidationError
from keysight_scope.fake_backend import FakeBackend
from keysight_scope.scpi import SCPIClient


def test_channel_display_command_uses_keysight_channel_syntax():
    assert channel_display_command(1, True) == ":CHANnel1:DISPlay ON"
    assert channel_display_command(2, False) == ":CHANnel2:DISPlay OFF"
    assert channel_display_query(3) == ":CHANnel3:DISPlay?"


@pytest.mark.parametrize("raw", ["1", "+1", "ON", " on "])
def test_parse_channel_display_enabled(raw):
    assert parse_channel_display(raw) is True


@pytest.mark.parametrize("raw", ["0", "+0", "OFF", " off "])
def test_parse_channel_display_disabled(raw):
    assert parse_channel_display(raw) is False


def test_parse_channel_display_rejects_unexpected_response():
    with pytest.raises(ChannelResponseError):
        parse_channel_display("MAYBE")


def test_validate_analog_channel_uses_capability_channel_count():
    capabilities = capabilities_for_model("DSOX4022A")

    assert validate_analog_channel(2, capabilities) == 2
    with pytest.raises(ParameterValidationError):
        validate_analog_channel(3, capabilities)


def test_channel_controller_sets_display_and_reads_back_state():
    backend = FakeBackend(responses={":CHANnel1:DISPlay?": "1"})
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_display(1, True)
    enabled = controller.query_display(1)

    assert enabled is True
    assert backend.history == [":CHANnel1:DISPlay ON", ":CHANnel1:DISPlay?"]


def test_channel_controller_rejects_invalid_channel_before_display_scpi():
    backend = FakeBackend()
    controller = ChannelController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.set_display(3, True)

    assert backend.history == []
