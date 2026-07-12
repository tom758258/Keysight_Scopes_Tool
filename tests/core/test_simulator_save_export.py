import pytest

from keysight_scope_core.scope import KeysightScope
from keysight_scope_core.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_save_export_roundtrip_and_start_recording(tmp_path):
    backend = SimulatorBackend(model="DSOX4024A")
    scope = KeysightScope(backend)
    scope.query_idn()

    scope.configure_save_pwd(r"USB:\captures")
    scope.configure_save_filename("scope_01")
    scope.configure_save_image_format("bmp24")
    scope.configure_save_image_palette("grayscale")
    scope.configure_save_image_ink_saver(True)
    scope.configure_save_image_factors(True)
    scope.configure_save_waveform_format("ascii-xy")
    scope.configure_save_waveform_length(2500)

    assert scope.query_save_pwd().path == r"USB:\captures"
    assert scope.query_save_filename().name == "scope_01"
    assert scope.query_save_image_format().format == "bmp24"
    assert scope.query_save_image_palette().palette == "grayscale"
    assert scope.query_save_image_ink_saver().enabled is True
    assert scope.query_save_image_factors().enabled is True
    assert scope.query_save_waveform_format().format == "ascii-xy"
    assert scope.query_save_waveform_length().points == 2500
    assert scope.query_save_waveform_length_max().enabled is False

    image = scope.save_image("USB:/screen.bmp")
    waveform = scope.save_waveform("USB:/wave.csv")
    assert image.operation == "save-image"
    assert waveform.operation == "save-waveform"
    assert backend.last_save_image_filename == "USB:/screen.bmp"
    assert backend.last_save_waveform_filename == "USB:/wave.csv"
    assert backend.history[-4:] == [
        ':SAVE:IMAGe "USB:/screen.bmp"',
        "*OPC?",
        ':SAVE:WAVeform "USB:/wave.csv"',
        "*OPC?",
    ]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "command",
    [":SAVE:IMAGe:FORMat NONE", ":SAVE:WAVeform:FORMat NONE"],
)
def test_simulator_rejects_none_format_writes(command):
    backend = SimulatorBackend(model="DSOX4024A")
    with pytest.raises(SimulatorBackendError):
        backend.write(command)


def test_simulator_none_format_readbacks_remain_parseable():
    backend = SimulatorBackend(model="DSOX4024A")
    scope = KeysightScope(backend)
    backend.save_image_format = "NONE"
    backend.save_waveform_format = "NONE"
    assert scope.query_save_image_format().format == "none"
    assert scope.query_save_waveform_format().format == "none"
