import pytest

import scopes_tool_core
from scopes_tool_core.errors import ParameterValidationError
from scopes_tool_core.fake_backend import FakeBackend
from scopes_tool_core.scope import KeysightScope
from scopes_tool_core.trigger import (
    EdgeTriggerSourceController,
    EdgeTriggerSourceState,
    parse_trigger_edge_source,
    trigger_edge_source_channel_command,
    trigger_edge_source_command,
    trigger_edge_source_external_command,
    trigger_edge_source_line_command,
    trigger_edge_source_query,
)


def test_trigger_edge_source_builders():
    assert trigger_edge_source_channel_command(1) == ":TRIGger:EDGE:SOURce CHANnel1"
    assert trigger_edge_source_external_command() == ":TRIGger:EDGE:SOURce EXTernal"
    assert trigger_edge_source_line_command() == ":TRIGger:EDGE:SOURce LINE"
    assert trigger_edge_source_query() == ":TRIGger:EDGE:SOURce?"


@pytest.mark.parametrize(
    ("raw", "source", "source_channel"),
    [
        ("CHAN1", "analog-channel", 1),
        ("CHANnel2", "analog-channel", 2),
        ("CHANNEL3", "analog-channel", 3),
        ("EXT", "external", None),
        ("EXTernal", "external", None),
        ("LINE", "line", None),
        ("NONE", None, None),
        ("WGEN", None, None),
        ("WGEN1", None, None),
        ("WGEN2", None, None),
        ("WMOD", None, None),
        ("DIG0", None, None),
        ("DIGITAL0", None, None),
        ("future-source", None, None),
    ],
)
def test_parse_trigger_edge_source_is_tolerant(raw, source, source_channel):
    state = parse_trigger_edge_source(f"  {raw} \n")

    assert state.source == source
    assert state.source_channel == source_channel
    assert state.raw_source == raw


def test_edge_trigger_source_configure_validation_and_controller_routing():
    backend = FakeBackend(
        responses={
            ":TRIGger:EDGE:SOURce?": "EXT",
        }
    )
    controller = EdgeTriggerSourceController(backend, _capabilities())

    controller.configure(source="analog-channel", source_channel=2)
    controller.configure(source="external")
    controller.configure(source="line")
    state = controller.query()

    assert backend.history == [
        ":TRIGger:EDGE:SOURce CHANnel2",
        ":TRIGger:EDGE:SOURce EXTernal",
        ":TRIGger:EDGE:SOURce LINE",
        ":TRIGger:EDGE:SOURce?",
    ]
    assert state == EdgeTriggerSourceState("external", None, "EXT")
    assert state.to_json() == {
        "source": "external",
        "source_channel": None,
        "raw_source": "EXT",
    }

    with pytest.raises(ParameterValidationError):
        controller.configure(source="wgen")
    with pytest.raises(ParameterValidationError):
        controller.configure(source="analog-channel")
    with pytest.raises(ParameterValidationError):
        controller.configure(source="external", source_channel=1)
    with pytest.raises(ParameterValidationError):
        controller.configure(source="line", source_channel=1)
    with pytest.raises(ParameterValidationError):
        controller.configure(source="analog-channel", source_channel=True)
    with pytest.raises(ParameterValidationError):
        controller.configure(source="analog-channel", source_channel=5)


def test_scope_public_edge_trigger_source_methods_and_exports():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX3024A,SIM000000,07.20",
            ":TRIGger:EDGE:SOURce?": "WGEN1",
        }
    )
    scope = KeysightScope(backend)
    scope.query_idn()

    scope.configure_trigger_edge_source(source="analog-channel", source_channel=4)
    state = scope.query_trigger_edge_source()

    assert backend.history[-2:] == [
        ":TRIGger:EDGE:SOURce CHANnel4",
        ":TRIGger:EDGE:SOURce?",
    ]
    assert state.source is None
    assert state.source_channel is None
    assert state.raw_source == "WGEN1"
    assert scopes_tool_core.EdgeTriggerSourceController is EdgeTriggerSourceController
    assert scopes_tool_core.EdgeTriggerSourceState is EdgeTriggerSourceState


def test_trigger_edge_source_builder_rejects_invalid_configuration():
    with pytest.raises(ParameterValidationError):
        trigger_edge_source_command("unsupported")
    with pytest.raises(ParameterValidationError):
        trigger_edge_source_command("analog-channel")
    with pytest.raises(ParameterValidationError):
        trigger_edge_source_command("external", source_channel=1)
    with pytest.raises(ParameterValidationError):
        trigger_edge_source_command("line", source_channel=1)
    with pytest.raises(ParameterValidationError):
        trigger_edge_source_command("analog-channel", source_channel=False)


def _capabilities():
    from scopes_tool_core.capabilities import capabilities_for_model

    return capabilities_for_model("DSOX4024A")
