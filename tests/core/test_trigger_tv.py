import pytest

from scopes_tool_core.capabilities import capabilities_for_model
from scopes_tool_core.errors import ParameterValidationError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scpi import SCPIClient
from scopes_tool_core.trigger import (
    TvTriggerController,
    parse_trigger_mode,
    tv_trigger_configure_commands,
    tv_trigger_query_commands,
)


def test_tv_trigger_configure_sequence_ntsc_field1_no_line():
    commands = tv_trigger_configure_commands(
        source_channel=1,
        standard="ntsc",
        mode="field1",
        polarity="negative",
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE TV",
        ":TRIGger:TV:SOURce CHANnel1",
        ":TRIGger:TV:STANdard NTSC",
        ":TRIGger:TV:MODE FIEld1",
        ":TRIGger:TV:POLarity NEGative",
    ]


def test_tv_trigger_configure_sequence_ntsc_line_field1():
    commands = tv_trigger_configure_commands(
        source_channel=1,
        standard="ntsc",
        mode="line-field1",
        line=20,
        polarity="negative",
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE TV",
        ":TRIGger:TV:SOURce CHANnel1",
        ":TRIGger:TV:STANdard NTSC",
        ":TRIGger:TV:MODE LFIeld1",
        ":TRIGger:TV:LINE 20",
        ":TRIGger:TV:POLarity NEGative",
    ]


def test_tv_trigger_configure_sequence_pal_line_field2():
    commands = tv_trigger_configure_commands(
        source_channel=2,
        standard="pal",
        mode="line-field2",
        line=400,
        polarity="positive",
        capabilities=capabilities_for_model("DSOX4024A"),
    )

    assert commands == [
        ":TRIGger:MODE TV",
        ":TRIGger:TV:SOURce CHANnel2",
        ":TRIGger:TV:STANdard PAL",
        ":TRIGger:TV:MODE LFIeld2",
        ":TRIGger:TV:LINE 400",
        ":TRIGger:TV:POLarity POSitive",
    ]


def test_tv_trigger_query_sequence_is_explicit():
    assert tv_trigger_query_commands() == [
        ":TRIGger:MODE?",
        ":TRIGger:TV:SOURce?",
        ":TRIGger:TV:STANdard?",
        ":TRIGger:TV:MODE?",
        ":TRIGger:TV:LINE?",
        ":TRIGger:TV:POLarity?",
    ]


def test_tv_trigger_query_parses_short_readbacks():
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "TV",
            ":TRIGger:TV:SOURce?": "CHAN1",
            ":TRIGger:TV:STANdard?": "SEC",
            ":TRIGger:TV:MODE?": "LFI1",
            ":TRIGger:TV:LINE?": "20",
            ":TRIGger:TV:POLarity?": "NEG",
        }
    )
    controller = TvTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    state = controller.query()

    assert state.to_json() == {
        "mode": "tv",
        "source_raw": "CHAN1",
        "source_channel": 1,
        "standard_raw": "SEC",
        "standard": "secam",
        "tv_mode_raw": "LFI1",
        "tv_mode": "line-field1",
        "line_raw": "20",
        "line": 20,
        "polarity_raw": "NEG",
        "polarity": "negative",
    }
    assert backend.history == tv_trigger_query_commands()


@pytest.mark.parametrize("source", ["DIG0", "DIGital1", "NONE", "EXT", "EXTernal", "", "BUS1"])
def test_tv_trigger_query_tolerates_non_analog_sources(source):
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "EDGE",
            ":TRIGger:TV:SOURce?": source,
            ":TRIGger:TV:STANdard?": "NTSC",
            ":TRIGger:TV:MODE?": "FIE1",
            ":TRIGger:TV:LINE?": "abc",
            ":TRIGger:TV:POLarity?": "POS",
        }
    )
    controller = TvTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    state = controller.query()

    assert state.source_raw == source.strip()
    assert state.source_channel is None
    assert state.line is None


@pytest.mark.parametrize("standard", ["GEN", "P1080L60HZ"])
def test_tv_trigger_query_tolerates_extended_standard_readbacks(standard):
    backend = FakeBackend(
        responses={
            ":TRIGger:MODE?": "TV",
            ":TRIGger:TV:SOURce?": "CHAN1",
            ":TRIGger:TV:STANdard?": standard,
            ":TRIGger:TV:MODE?": "LINE",
            ":TRIGger:TV:LINE?": "1",
            ":TRIGger:TV:POLarity?": "UNKNOWN",
        }
    )
    controller = TvTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    state = controller.query()

    assert state.standard_raw == standard
    assert state.standard is None
    assert state.tv_mode_raw == "LINE"
    assert state.tv_mode is None
    assert state.polarity is None


def test_parse_trigger_mode_supports_tv():
    assert parse_trigger_mode("TV") == "tv"


def test_tv_trigger_validation_rejects_unsupported_channel_for_profile():
    with pytest.raises(ParameterValidationError):
        tv_trigger_configure_commands(
            source_channel=5,
            standard="ntsc",
            mode="field1",
            polarity="negative",
            capabilities=capabilities_for_model("DSOX4024A"),
        )


@pytest.mark.parametrize(
    "standard",
    [
        "generic",
        "p480",
        "p720",
        "p1080",
        "i1080",
        "p480l60hz",
        "p720l60hz",
        "p1080l24hz",
        "p1080l25hz",
        "p1080l50hz",
        "p1080l60hz",
        "i1080l50hz",
        "i1080l60hz",
    ],
)
def test_tv_trigger_validation_rejects_extended_standards(standard):
    with pytest.raises(ParameterValidationError):
        tv_trigger_configure_commands(
            source_channel=1,
            standard=standard,
            mode="field1",
            polarity="negative",
            capabilities=capabilities_for_model("DSOX4024A"),
        )


def test_tv_trigger_validation_rejects_line_mode():
    with pytest.raises(ParameterValidationError):
        tv_trigger_configure_commands(
            source_channel=1,
            standard="ntsc",
            mode="line",
            polarity="negative",
            capabilities=capabilities_for_model("DSOX4024A"),
        )


@pytest.mark.parametrize("mode", ["line-field1", "line-field2", "line-alternate"])
def test_tv_trigger_validation_requires_line_for_line_modes(mode):
    with pytest.raises(ParameterValidationError):
        tv_trigger_configure_commands(
            source_channel=1,
            standard="ntsc",
            mode=mode,
            polarity="negative",
            capabilities=capabilities_for_model("DSOX4024A"),
        )


@pytest.mark.parametrize("mode", ["field1", "field2", "all-fields", "all-lines"])
def test_tv_trigger_validation_rejects_line_for_non_line_modes(mode):
    with pytest.raises(ParameterValidationError):
        tv_trigger_configure_commands(
            source_channel=1,
            standard="ntsc",
            mode=mode,
            line=1,
            polarity="negative",
            capabilities=capabilities_for_model("DSOX4024A"),
        )


@pytest.mark.parametrize(
    "standard, mode, accepts, rejects",
    [
        ("ntsc", "line-field1", [1, 263], [0, 264]),
        ("pal", "line-field2", [314, 625], [313, 626]),
        ("palm", "line-field2", [264, 525], [263, 526]),
        ("secam", "line-alternate", [1, 312], [0, 313]),
    ],
)
def test_tv_trigger_validation_line_boundaries(standard, mode, accepts, rejects):
    capabilities = capabilities_for_model("DSOX4024A")
    for line in accepts:
        tv_trigger_configure_commands(
            source_channel=1,
            standard=standard,
            mode=mode,
            line=line,
            polarity="negative",
            capabilities=capabilities,
        )
    for line in rejects:
        with pytest.raises(ParameterValidationError):
            tv_trigger_configure_commands(
                source_channel=1,
                standard=standard,
                mode=mode,
                line=line,
                polarity="negative",
                capabilities=capabilities,
            )
