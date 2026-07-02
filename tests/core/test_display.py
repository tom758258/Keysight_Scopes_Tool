import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.display import (
    DisplayController,
    annotation_commands,
    annotation_query_commands,
    display_label_command,
    display_label_query,
    parse_annotation_background,
    parse_annotation_color,
    parse_display_label,
    validate_annotation_text,
    validate_annotation_slot,
)
from keysight_scope_core.errors import ChannelResponseError, ParameterValidationError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient


@pytest.mark.parametrize("raw", ["1", "+1", "ON", " on "])
def test_parse_display_label_enabled(raw):
    assert parse_display_label(raw) is True


@pytest.mark.parametrize("raw", ["0", "+0", "OFF", " off "])
def test_parse_display_label_disabled(raw):
    assert parse_display_label(raw) is False


def test_parse_display_label_rejects_unexpected_response():
    with pytest.raises(ChannelResponseError):
        parse_display_label("maybe")


def test_display_label_command_uses_keysight_display_syntax():
    assert display_label_command(True) == ":DISPlay:LABel ON"
    assert display_label_command(False) == ":DISPlay:LABel OFF"
    assert display_label_query() == ":DISPlay:LABel?"


def test_annotation_unindexed_commands_omit_position_for_3000x_query():
    capabilities = capabilities_for_model("DSOX3024A")

    assert annotation_query_commands(slot=1, capabilities=capabilities) == [
        ":DISPlay:ANNotation?",
        ":DISPlay:ANNotation:TEXT?",
        ":DISPlay:ANNotation:COLor?",
        ":DISPlay:ANNotation:BACKground?",
    ]
    assert annotation_commands(
        capabilities=capabilities,
        slot=1,
        enabled=True,
        text="lower ok",
        color="red",
        background="opaque",
    ) == [
        ":DISPlay:ANNotation ON",
        ':DISPlay:ANNotation:TEXT "lower ok"',
        ":DISPlay:ANNotation:COLor RED",
        ":DISPlay:ANNotation:BACKground OPAQ",
    ]


def test_annotation_indexed_commands_include_position_for_4000x():
    capabilities = capabilities_for_model("DSOX4024A")

    assert annotation_query_commands(slot=2, capabilities=capabilities) == [
        ":DISPlay:ANNotation2?",
        ":DISPlay:ANNotation2:TEXT?",
        ":DISPlay:ANNotation2:COLor?",
        ":DISPlay:ANNotation2:BACKground?",
        ":DISPlay:ANNotation2:X1Position?",
        ":DISPlay:ANNotation2:Y1Position?",
    ]
    assert annotation_commands(
        capabilities=capabilities,
        slot=2,
        enabled=False,
        clear=True,
        x=10,
        y=20,
    ) == [
        ":DISPlay:ANNotation2 OFF",
        ':DISPlay:ANNotation2:TEXT ""',
        ":DISPlay:ANNotation2:X1Position 10",
        ":DISPlay:ANNotation2:Y1Position 20",
    ]


def test_annotation_slot_uses_profile_slot_count():
    with pytest.raises(ParameterValidationError):
        validate_annotation_slot(2, capabilities_for_model("DSOX3024A"))
    assert validate_annotation_slot(10, capabilities_for_model("DSOX4024A")) == 10


def test_validate_annotation_text_accepts_254_printable_ascii_characters():
    text = "x" * 254

    assert validate_annotation_text(text) == text


def test_validate_annotation_text_rejects_255_characters():
    with pytest.raises(ParameterValidationError, match="at most 254"):
        validate_annotation_text("x" * 255)


@pytest.mark.parametrize("text", ['bad"quote', "bad\nline", "non-ascii-\u00e9"])
def test_validate_annotation_text_rejects_invalid_characters(text):
    with pytest.raises(ParameterValidationError):
        validate_annotation_text(text)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" WHIT ", "WHITE"),
        ("whit", "WHITE"),
        ("WHITE", "WHITE"),
        ("MARK", "MARK"),
        ("DIG", "DIG"),
        ("CH1", "CH1"),
    ],
)
def test_parse_annotation_color_accepts_readback_abbreviations(raw, expected):
    assert parse_annotation_color(raw) == expected


def test_parse_annotation_color_rejects_unknown_readback():
    with pytest.raises(ChannelResponseError):
        parse_annotation_color("BLUE")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("opaq", "OPAQ"),
        ("INV", "INV"),
        ("TRAN", "TRAN"),
    ],
)
def test_parse_annotation_background_accepts_canonical_readback(raw, expected):
    assert parse_annotation_background(raw) == expected


def test_parse_annotation_background_rejects_unknown_readback():
    with pytest.raises(ChannelResponseError):
        parse_annotation_background("transparent")


def test_display_controller_sets_and_queries_label_and_annotation():
    backend = FakeBackend(
        responses={
            ":DISPlay:LABel?": "1",
            ":DISPlay:ANNotation1?": "1",
            ":DISPlay:ANNotation1:TEXT?": '"Note"',
            ":DISPlay:ANNotation1:COLor?": " WHIT ",
            ":DISPlay:ANNotation1:BACKground?": "tran",
            ":DISPlay:ANNotation1:X1Position?": "10",
            ":DISPlay:ANNotation1:Y1Position?": "20",
        }
    )
    controller = DisplayController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.set_label(True)
    assert controller.query_label() is True
    controller.set_annotation_enabled(True)
    controller.set_annotation_text("Note")
    controller.set_annotation_position(10, 20)
    state = controller.query_annotation()

    assert state.enabled is True
    assert state.text == "Note"
    assert state.color == "WHITE"
    assert state.background == "TRAN"
    assert state.x == 10
    assert state.y == 20
    assert backend.history == [
        ":DISPlay:LABel ON",
        ":DISPlay:LABel?",
        ":DISPlay:ANNotation1 ON",
        ':DISPlay:ANNotation1:TEXT "Note"',
        ":DISPlay:ANNotation1:X1Position 10",
        ":DISPlay:ANNotation1:Y1Position 20",
        ":DISPlay:ANNotation1?",
        ":DISPlay:ANNotation1:TEXT?",
        ":DISPlay:ANNotation1:COLor?",
        ":DISPlay:ANNotation1:BACKground?",
        ":DISPlay:ANNotation1:X1Position?",
        ":DISPlay:ANNotation1:Y1Position?",
    ]
