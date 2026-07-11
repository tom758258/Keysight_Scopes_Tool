import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import ParameterValidationError, SearchResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.search import (
    SearchController,
    parse_search_count,
    parse_search_mode,
    parse_search_state,
    search_count_query,
    search_mode_command,
    search_mode_query,
    search_state_command,
    search_state_query,
)
from keysight_scope_core.scpi import SCPIClient


def test_search_basic_scpi_builders():
    assert search_state_command(True) == ":SEARch:STATe 1"
    assert search_state_command(False) == ":SEARch:STATe 0"
    assert search_state_query() == ":SEARch:STATe?"
    assert search_mode_query() == ":SEARch:MODE?"
    assert search_count_query() == ":SEARch:COUNt?"
    assert search_mode_command("serial1") == ":SEARch:MODE SERial1"
    assert search_mode_command("serial2") == ":SEARch:MODE SERial2"
    assert search_mode_command("edge") == ":SEARch:MODE EDGE"
    assert search_mode_command("glitch") == ":SEARch:MODE GLITch"
    assert search_mode_command("runt") == ":SEARch:MODE RUNT"
    assert search_mode_command("transition") == ":SEARch:MODE TRANsition"
    assert search_mode_command("peak") == ":SEARch:MODE PEAK"


@pytest.mark.parametrize(
    "raw, expected", [("ON", True), ("1", True), ("+1", True), ("OFF", False), ("0", False)]
)
def test_parse_search_state(raw, expected):
    assert parse_search_state(raw) is expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("OFF", (None, False)),
        ("SER1", ("serial1", True)),
        ("SERial1", ("serial1", True)),
        ("SER2", ("serial2", True)),
        ("SERial2", ("serial2", True)),
        ("EDGE", ("edge", True)),
        ("GLIT", ("glitch", True)),
        ("GLITch", ("glitch", True)),
        ("RUNT", ("runt", True)),
        ("TRAN", ("transition", True)),
        ("TRANsition", ("transition", True)),
        ("PEAK", ("peak", True)),
    ],
)
def test_parse_search_mode_long_and_short_forms(raw, expected):
    assert parse_search_mode(raw) == expected


@pytest.mark.parametrize("raw", ["", "1.0", "abc", "1E+1", "-1"])
def test_parse_search_count_rejects_malformed_or_negative_readback(raw):
    with pytest.raises(SearchResponseError, match="Could not parse search count response"):
        parse_search_count(raw)


@pytest.mark.parametrize(
    "raw, expected_count, expected_raw",
    [("0", 0, "0"), ("+0", 0, "+0"), ("7", 7, "7"), (" +12 \n", 12, "+12")],
)
def test_parse_search_count_preserves_raw_non_negative_integer_readback(
    raw, expected_count, expected_raw
):
    state = parse_search_count(raw)
    assert state.count == expected_count
    assert state.raw_count == expected_raw


@pytest.mark.parametrize(
    "model, accepted, rejected",
    [
        ("DSOX2004A", {"serial1"}, {"serial2", "edge", "glitch", "runt", "transition", "peak"}),
        ("DSOX3024A", {"serial1", "serial2", "edge", "glitch", "runt", "transition"}, {"peak"}),
        ("DSOX4034A", {"serial1", "serial2", "edge", "glitch", "runt", "transition", "peak"}, set()),
    ],
)
def test_search_mode_profile_gating(model, accepted, rejected):
    for mode in accepted:
        backend = FakeBackend()
        controller = SearchController(SCPIClient(backend), capabilities_for_model(model))
        state = controller.configure_mode(mode)
        assert state.mode == mode
        assert backend.history == [":SEARch:STATe 1", search_mode_command(mode)]
    for mode in rejected:
        backend = FakeBackend()
        controller = SearchController(SCPIClient(backend), capabilities_for_model(model))
        with pytest.raises(ParameterValidationError, match="not supported by the selected"):
            controller.configure_mode(mode)
        assert backend.history == []


def test_keysight_scope_search_queries_preserve_raw_readbacks():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4034A,MY00000000,02.50",
            ":SEARch:STATe?": "ON",
            ":SEARch:MODE?": "TRAN",
            ":SEARch:COUNt?": "7",
        }
    )
    scope = KeysightScope(backend)
    scope.query_idn()

    assert scope.query_search_state().to_json() == {"enabled": True, "raw_state": "ON"}
    assert scope.query_search_mode().to_json() == {
        "mode": "transition",
        "enabled": True,
        "raw_mode": "TRAN",
    }
    assert scope.query_search_count().to_json() == {"count": 7, "raw_count": "7"}


def test_query_search_mode_off_preserves_raw_readback():
    backend = FakeBackend(responses={":SEARch:MODE?": "OFF"})
    controller = SearchController(SCPIClient(backend), capabilities_for_model("DSOX2004A"))
    assert controller.query_mode().to_json() == {
        "mode": None,
        "enabled": False,
        "raw_mode": "OFF",
    }
