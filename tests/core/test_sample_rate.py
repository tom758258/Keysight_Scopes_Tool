"""Tests for sample-rate query helper."""

import pytest

from keysight_scope_core.acquisition import (
    parse_sample_rate,
    sample_rate_query,
)
from keysight_scope_core.errors import AcquisitionResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.simulator_backend import SimulatorBackend


def test_sample_rate_query_returns_keysight_short_form():
    assert sample_rate_query() == ":ACQuire:SRATe:ANALog?"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5.000000E+09", 5e9),
        ('1E6' + chr(10), 1e6),
        ("1000000", 1e6),
        ("  2.5E3  ", 2500.0),
        ("5.0E+00", 5.0),
    ],
)
def test_parse_sample_rate_accepts_decimal_and_scientific_notation(raw, expected):
    assert parse_sample_rate(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "abc", "0", "-1", "nan", "inf", "-inf"],
)
def test_parse_sample_rate_rejects_invalid_response(raw):
    with pytest.raises(AcquisitionResponseError):
        parse_sample_rate(raw)


def test_simulator_backend_reports_default_sample_rate():
    backend = SimulatorBackend()

    assert backend.query(":ACQuire:SRATe:ANALog?") == "5.000000E+09"


def test_simulator_backend_reports_configured_sample_rate():
    backend = SimulatorBackend(sample_rate_hz=1.25e8)

    assert backend.query(":ACQuire:SRATe:ANALog?") == "1.250000E+08"


def test_fake_backend_records_sample_rate_query():
    backend = FakeBackend(responses={":ACQuire:SRATe:ANALog?": "5.000000E+09"})
    client = SCPIClient(backend)

    raw = client.query(sample_rate_query())
    value = parse_sample_rate(raw)

    assert value == 5e9
    assert backend.history == [":ACQuire:SRATe:ANALog?"]

