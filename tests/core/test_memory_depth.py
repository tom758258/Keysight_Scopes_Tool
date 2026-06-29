"""Tests for memory-depth query helper."""

import pytest

from keysight_scope_core.acquisition import (
    parse_memory_depth,
    memory_depth_query,
)
from keysight_scope_core.errors import AcquisitionResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.simulator_backend import SimulatorBackend


def test_memory_depth_query_returns_keysight_short_form():
    assert memory_depth_query() == ":ACQuire:POINts?"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1000000", 1000000),
        ("1.000000E+06", 1000000),
        ("  2500  ", 2500),
        ("2.5E3", 2500),
    ],
)
def test_parse_memory_depth_accepts_decimal_and_scientific_notation(raw, expected):
    assert parse_memory_depth(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "abc", "0", "-1", "nan", "inf", "-inf", "1.5", "AUTO"],
)
def test_parse_memory_depth_rejects_invalid_response(raw):
    with pytest.raises(AcquisitionResponseError):
        parse_memory_depth(raw)


def test_simulator_backend_reports_default_memory_depth():
    backend = SimulatorBackend()

    assert backend.query(":ACQuire:POINts?") == "1000000"


def test_simulator_backend_reports_configured_memory_depth():
    backend = SimulatorBackend(memory_depth_points=2500)

    assert backend.query(":ACQuire:POINts?") == "2500"


def test_fake_backend_records_memory_depth_query():
    backend = FakeBackend(responses={":ACQuire:POINts?": "1000000"})
    client = SCPIClient(backend)

    raw = client.query(memory_depth_query())
    value = parse_memory_depth(raw)

    assert value == 1000000
    assert backend.history == [":ACQuire:POINts?"]
