"""Tests for acquisition-points and record-length query helpers."""

import pytest

from scopes_tool_core.acquisition import (
    acquisition_points_query,
    parse_acquisition_points,
    parse_record_length,
    record_length_query,
)
from scopes_tool_core.errors import AcquisitionResponseError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.simulator_backend import SimulatorBackend


def test_acquisition_points_query_returns_keysight_short_form():
    assert acquisition_points_query() == ":ACQuire:POINts?"


def test_record_length_query_returns_keysight_short_form():
    assert record_length_query() == ":ACQuire:RLENgth?"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1000000", 1000000),
        ("1.000000E+06", 1000000),
        ("  2500  ", 2500),
        ("2.5E3", 2500),
    ],
)
def test_parse_acquisition_points_accepts_decimal_and_scientific_notation(
    raw, expected
):
    assert parse_acquisition_points(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("65536", 65536),
        ("6.5536E+04", 65536),
        ("  5000  ", 5000),
        ("5E3", 5000),
    ],
)
def test_parse_record_length_accepts_decimal_and_scientific_notation(raw, expected):
    assert parse_record_length(raw) == expected


@pytest.mark.parametrize(
    "parser",
    (parse_acquisition_points, parse_record_length),
)
@pytest.mark.parametrize(
    "raw",
    ["", "   ", "abc", "0", "-1", "nan", "inf", "-inf", "1.5", "AUTO"],
)
def test_positive_integer_parsers_reject_invalid_response(parser, raw):
    with pytest.raises(AcquisitionResponseError):
        parser(raw)


def test_simulator_backend_reports_default_acquisition_points_and_record_length():
    backend = SimulatorBackend()

    assert backend.query(":ACQuire:POINts?") == "1000000"
    assert backend.query(":ACQuire:RLENgth?") == "65536"


def test_simulator_backend_reports_configured_distinct_values():
    backend = SimulatorBackend(acquisition_points=2500, record_length_points=8192)

    assert backend.query(":ACQuire:POINts?") == "2500"
    assert backend.query(":ACQuire:RLENgth?") == "8192"


def test_fake_backend_records_acquisition_points_query():
    backend = FakeBackend(responses={":ACQuire:POINts?": "1000000"})
    client = SCPIClient(backend)

    raw = client.query(acquisition_points_query())
    value = parse_acquisition_points(raw)

    assert value == 1000000
    assert backend.history == [":ACQuire:POINts?"]


def test_fake_backend_records_record_length_query():
    backend = FakeBackend(responses={":ACQuire:RLENgth?": "65536"})
    client = SCPIClient(backend)

    raw = client.query(record_length_query())
    value = parse_record_length(raw)

    assert value == 65536
    assert backend.history == [":ACQuire:RLENgth?"]
