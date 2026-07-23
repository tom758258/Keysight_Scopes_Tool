import pytest

from scopes_tool_core.errors import StatusResponseError, SystemErrorParseError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.status import (
    StatusController,
    parse_operation_complete,
    parse_status_register,
    parse_system_error,
    parse_system_options,
)


def test_parse_system_error_no_error():
    entry = parse_system_error('+0,"No error"\n')

    assert entry.code == 0
    assert entry.message == "No error"
    assert entry.raw == '+0,"No error"'
    assert entry.is_error is False
    assert entry.format() == '+0, "No error"'


def test_parse_system_error_with_negative_code_and_comma_in_message():
    entry = parse_system_error('-113,"Undefined header, bad command"')

    assert entry.code == -113
    assert entry.message == "Undefined header, bad command"
    assert entry.is_error is True
    assert entry.format() == '-113, "Undefined header, bad command"'


def test_parse_system_error_rejects_bad_shape():
    with pytest.raises(SystemErrorParseError):
        parse_system_error("not an error response")


def test_parse_system_error_rejects_bad_code():
    with pytest.raises(SystemErrorParseError):
        parse_system_error('abc,"No error"')


def test_parse_operation_complete_accepts_only_one_and_preserves_raw():
    state = parse_operation_complete(" 1\n")

    assert state.complete is True
    assert state.raw == "1"


@pytest.mark.parametrize("response", ["", "0", "+1", "ON", "2"])
def test_parse_operation_complete_rejects_non_success(response):
    with pytest.raises(StatusResponseError):
        parse_operation_complete(response)


def test_parse_status_register_preserves_raw_and_lists_set_bits_low_to_high():
    state = parse_status_register(" +137\n", maximum=255)

    assert state.value == 137
    assert state.raw == "+137"
    assert state.set_bits == (0, 3, 7)


@pytest.mark.parametrize("response", ["", "abc", "1.0", "-1", "256"])
def test_parse_status_register_rejects_invalid_byte_values(response):
    with pytest.raises(StatusResponseError):
        parse_status_register(response, maximum=255)


def test_parse_status_register_allows_wider_operation_condition_range():
    assert parse_status_register("65535", maximum=65535).value == 65535
    with pytest.raises(StatusResponseError):
        parse_status_register("65536", maximum=65535)


def test_parse_system_options_trims_tokens_and_preserves_no_option_response():
    state = parse_system_options(" OPTA, OPTB \n")
    no_options = parse_system_options("0")

    assert state.raw == "OPTA, OPTB"
    assert state.options == ("OPTA", "OPTB")
    assert no_options.raw == "0"
    assert no_options.options == ("0",)


@pytest.mark.parametrize("response", ["", "A,,B", ",A", "A,"])
def test_parse_system_options_rejects_empty_tokens(response):
    with pytest.raises(StatusResponseError):
        parse_system_options(response)


def test_status_controller_sends_exact_scpi():
    backend = FakeBackend(
        responses={
            "*OPC?": "1",
            "*STB?": "3",
            "*ESR?": "4",
            ":OPERegister:CONDition?": "8",
            "*OPT?": "0",
        }
    )
    controller = StatusController(SCPIClient(backend))

    controller.clear_status()
    assert controller.query_operation_complete().complete is True
    assert controller.query_status_byte().value == 3
    assert controller.query_standard_event_status().value == 4
    assert controller.query_operation_status().value == 8
    assert controller.query_system_options().options == ("0",)
    assert backend.history == [
        "*CLS",
        "*OPC?",
        "*STB?",
        "*ESR?",
        ":OPERegister:CONDition?",
        "*OPT?",
    ]
