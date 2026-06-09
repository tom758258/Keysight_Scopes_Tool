import pytest

from keysight_scope_core.errors import SystemErrorParseError
from keysight_scope_core.status import parse_system_error


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
