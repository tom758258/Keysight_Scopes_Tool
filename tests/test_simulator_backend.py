import pytest

from keysight_scope.errors import KeysightScopeError
from keysight_scope.simulator_backend import SimulatorBackend, SimulatorBackendError


def test_simulator_system_error_queue_drains_to_no_error():
    backend = SimulatorBackend(
        system_errors=['-113,"Undefined header"', '-222,"Data out of range"']
    )

    assert backend.query(":SYSTem:ERRor?") == '-113,"Undefined header"'
    assert backend.query(":SYSTem:ERRor?") == '-222,"Data out of range"'
    assert backend.query(":SYSTem:ERRor?") == '+0,"No error"'
    assert backend.history == [
        ":SYSTem:ERRor?",
        ":SYSTem:ERRor?",
        ":SYSTem:ERRor?",
    ]


def test_simulator_rejects_unknown_scpi_in_strict_mode():
    backend = SimulatorBackend()

    with pytest.raises(SimulatorBackendError, match="Unsupported simulator query"):
        backend.query(":FOO:BAR?")

    with pytest.raises(SimulatorBackendError, match="Unsupported simulator write"):
        backend.write(":FOO:BAR 1")

    with pytest.raises(SimulatorBackendError, match="Unsupported simulator binary query"):
        backend.query_binary_values(":FOO:DATA?")


def test_simulator_allows_supported_control_and_word_waveform_commands():
    backend = SimulatorBackend()

    backend.write(":RUN")
    backend.write(":STOP")
    backend.write(":SINGle")
    backend.write(":WAVeform:SOURce CHANnel2")
    backend.write(":WAVeform:FORMat WORD")
    backend.write(":WAVeform:BYTeorder MSBFirst")
    backend.write(":WAVeform:UNSigned ON")
    backend.write(":WAVeform:POINts 1000")

    assert backend.run_state == "single"
    assert backend.waveform_source == 2
    assert backend.waveform_format == "WORD"
    assert backend.waveform_byte_order == "MSBFirst"
    assert backend.waveform_unsigned is True
    assert backend.query(":WAVeform:PREamble?").startswith("1,0,1000,")
    assert len(backend.query_binary_values(":WAVeform:DATA?", datatype="H")) == 1000


def test_simulator_byte_waveform_uses_requested_5000_points():
    backend = SimulatorBackend()

    backend.write(":WAVeform:SOURce CHANnel1")
    backend.write(":WAVeform:FORMat BYTE")
    backend.write(":WAVeform:POINts 5000")

    preamble = backend.query(":WAVeform:PREamble?")
    samples = backend.query_binary_values(":WAVeform:DATA?", datatype="B")

    assert preamble.split(",")[2] == "5000"
    assert len(samples) == 5000
    assert min(samples) >= 0
    assert max(samples) <= 255


def test_simulator_word_waveform_uses_requested_10000_points():
    backend = SimulatorBackend()

    backend.write(":WAVeform:SOURce CHANnel2")
    backend.write(":WAVeform:FORMat WORD")
    backend.write(":WAVeform:BYTeorder MSBFirst")
    backend.write(":WAVeform:UNSigned ON")
    backend.write(":WAVeform:POINts 10000")

    preamble = backend.query(":WAVeform:PREamble?")
    samples = backend.query_binary_values(":WAVeform:DATA?", datatype="H")

    assert preamble.split(",")[2] == "10000"
    assert len(samples) == 10000
    assert min(samples) >= 0
    assert max(samples) <= 65535


def test_simulator_rejects_unsupported_waveform_points_in_strict_mode():
    backend = SimulatorBackend()

    with pytest.raises(SimulatorBackendError, match="waveform point count"):
        backend.write(":WAVeform:POINts 2000")


def test_simulator_measurements_use_channel_and_pair_signal_model():
    backend = SimulatorBackend()

    assert float(backend.query(":MEASure:VPP? CHANnel1")) == pytest.approx(0.5)
    assert float(backend.query(":MEASure:VPP? CHANnel2")) == pytest.approx(1.0)
    assert float(backend.query(":MEASure:PHASe? CHANnel1,CHANnel2")) == pytest.approx(45.0)
    assert float(backend.query(":MEASure:DELay? AUTO,CHANnel1,CHANnel2")) == pytest.approx(
        45.0 / 360.0 / 1000.0
    )


def test_simulator_parameterized_measurements_are_deterministic():
    backend = SimulatorBackend()

    assert float(backend.query(":MEASure:VTIMe? 0,CHANnel1")) == pytest.approx(0.0)
    assert float(backend.query(":MEASure:TEDGe? +1,CHANnel1")) == pytest.approx(0.0)
    assert float(backend.query(":MEASure:TVALue? 0,+1,CHANnel1")) == pytest.approx(0.0)


def test_simulator_measurement_invalid_sentinel_hooks():
    backend = SimulatorBackend(invalid_measurement_channels={2})

    assert backend.query(":MEASure:VPP? CHANnel2") == "9.9E+37"
    assert backend.query(":MEASure:TVALue? 99,+1,CHANnel1") == "9.9E+37"


def test_simulator_failure_and_override_hooks_record_attempted_command():
    query_error = KeysightScopeError("configured query failure")
    binary_error = KeysightScopeError("configured binary failure")
    backend = SimulatorBackend(
        query_failures={":MEASure:VPP? CHANnel1": query_error},
        binary_failures={":WAVeform:DATA?": binary_error},
        query_overrides={":ACQuire:TYPE?": "bad-type"},
        binary_overrides={":DISPlay:DATA? PNG, COLor": []},
    )

    with pytest.raises(KeysightScopeError, match="configured query failure"):
        backend.query(":MEASure:VPP? CHANnel1")
    assert backend.history[-1] == ":MEASure:VPP? CHANnel1"

    with pytest.raises(KeysightScopeError, match="configured binary failure"):
        backend.query_binary_values(":WAVeform:DATA?")
    assert backend.history[-1] == ":WAVeform:DATA?"

    assert backend.query(":ACQuire:TYPE?") == "bad-type"
    assert backend.query_binary_values(":DISPlay:DATA? PNG, COLor") == []
