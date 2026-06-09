import pytest

from keysight_scope_core.errors import KeysightScopeError
from keysight_scope_core.simulator_backend import (
    SimulatedSignal,
    SimulatorBackend,
    SimulatorBackendError,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_dimensions(data):
    assert data.startswith(PNG_SIGNATURE)
    assert data[12:16] == b"IHDR"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


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


def test_simulator_state_queries_reflect_channel_timebase_and_trigger_writes():
    backend = SimulatorBackend()

    backend.write(":CHANnel1:SCALe 0.5")
    backend.write(":CHANnel1:OFFSet 0.25")
    backend.write(":CHANnel1:COUPling AC")
    backend.write(":CHANnel1:PROBe 10")
    backend.write(":CHANnel1:BWLimit ON")
    backend.write(":TIMebase:SCALe 0.002")
    backend.write(":TIMebase:POSition 0.001")
    backend.write(":TRIGger:MODE EDGE")
    backend.write(":TRIGger:EDGE:SOURce CHANnel2")
    backend.write(":TRIGger:EDGE:LEVel 0.15")
    backend.write(":TRIGger:EDGE:SLOPe NEGative")

    assert backend.query(":CHANnel1:SCALe?") == "0.5"
    assert backend.query(":CHANnel1:OFFSet?") == "0.25"
    assert backend.query(":CHANnel1:COUPling?") == "AC"
    assert backend.query(":CHANnel1:PROBe?") == "10"
    assert backend.query(":CHANnel1:BWLimit?") == "1"
    assert backend.query(":TIMebase:SCALe?") == "0.002"
    assert backend.query(":TIMebase:POSition?") == "0.001"
    assert backend.query(":TRIGger:EDGE:SOURce?") == "CHANnel2"
    assert backend.query(":TRIGger:EDGE:LEVel?") == "0.15"
    assert backend.query(":TRIGger:EDGE:SLOPe?") == "NEGative"


def test_simulator_waveform_model_reflects_scale_offset_timebase_and_channel_phase():
    backend = SimulatorBackend()

    backend.write(":TIMebase:SCALe 0.002")
    backend.write(":TIMebase:POSition 0.001")
    backend.write(":CHANnel1:SCALe 0.5")
    backend.write(":CHANnel1:OFFSet 0.25")
    backend.write(":WAVeform:SOURce CHANnel1")
    backend.write(":WAVeform:FORMat BYTE")
    backend.write(":WAVeform:POINts 1000")
    ch1_preamble = backend.query(":WAVeform:PREamble?").split(",")
    ch1_samples = backend.query_binary_values(":WAVeform:DATA?", datatype="B")

    backend.write(":WAVeform:SOURce CHANnel2")
    ch2_samples = backend.query_binary_values(":WAVeform:DATA?", datatype="B")

    assert float(ch1_preamble[4]) == pytest.approx(2.0e-5)
    assert float(ch1_preamble[5]) == pytest.approx(-0.009)
    assert float(ch1_preamble[7]) == pytest.approx(0.01)
    assert float(ch1_preamble[8]) == pytest.approx(0.25)
    assert len(ch1_samples) == 1000
    assert ch1_samples != ch2_samples


def test_simulator_respects_model_channel_capabilities():
    backend = SimulatorBackend(model="DSOX4022A")

    with pytest.raises(SimulatorBackendError, match="CH3 is not available"):
        backend.write(":WAVeform:SOURce CHANnel3")

    with pytest.raises(SimulatorBackendError, match="CH3 is not available"):
        backend.query(":MEASure:VPP? CHANnel3")

    with pytest.raises(SimulatorBackendError, match="CH3 is not available"):
        backend.write(":TRIGger:EDGE:SOURce CHANnel3")


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


def test_simulator_screenshot_png_reflects_inksaver_background():
    backend = SimulatorBackend()

    black = bytes(backend.query_binary_values(":DISPlay:DATA? PNG, COLor"))
    backend.write(":HARDcopy:INKSaver ON")
    white = bytes(backend.query_binary_values(":DISPlay:DATA? PNG, COLor"))

    assert black.startswith(PNG_SIGNATURE)
    assert white.startswith(PNG_SIGNATURE)
    assert black != white
    assert _png_dimensions(black) == (480, 272)
    assert _png_dimensions(white) == (480, 272)
    assert len(black) > 1000
    assert len(white) > 1000


def test_simulator_screenshot_png_reflects_model_label_deterministically():
    first = bytes(
        SimulatorBackend(model="DSOX4024A").query_binary_values(
            ":DISPlay:DATA? PNG, COLor"
        )
    )
    second = bytes(
        SimulatorBackend(model="DSOX4024A").query_binary_values(
            ":DISPlay:DATA? PNG, COLor"
        )
    )
    different_model = bytes(
        SimulatorBackend(model="DSOX3024A").query_binary_values(
            ":DISPlay:DATA? PNG, COLor"
        )
    )

    assert first == second
    assert first != different_model
    assert _png_dimensions(different_model) == (480, 272)


def test_simulator_supports_configured_signal_shapes_and_measurements():
    backend = SimulatorBackend(
        signals={
            1: SimulatedSignal("square", 2000.0, 2.0, 0.1, 0.0),
            2: SimulatedSignal("ramp", 500.0, 3.0, -0.2, 90.0),
            3: SimulatedSignal("dc", 0.0, 0.0, 1.25, 0.0),
            4: SimulatedSignal("noise", 0.0, 0.0, -0.1, 0.0, 0.05),
        }
    )

    assert float(backend.query(":MEASure:VPP? CHANnel1")) == pytest.approx(2.0)
    assert float(backend.query(":MEASure:VRMS? DISPlay,AC,CHANnel1")) == pytest.approx(1.0)
    assert float(backend.query(":MEASure:VAVerage? DISPlay,CHANnel2")) == pytest.approx(-0.2)
    assert float(backend.query(":MEASure:VAVerage? DISPlay,CHANnel3")) == pytest.approx(1.25)
    assert backend.query(":MEASure:FREQuency? CHANnel3") == "9.9E+37"
    assert backend.query(":MEASure:PERiod? CHANnel4") == "9.9E+37"


def test_simulator_signal_offset_adds_channel_offset_and_affects_y_at_x():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 2.0, 0.4, 0.0)}
    )
    backend.write(":CHANnel1:OFFSet 0.25")

    assert float(backend.query(":MEASure:VAVerage? DISPlay,CHANnel1")) == pytest.approx(
        0.65
    )
    assert float(backend.query(":MEASure:VTIMe? 0,CHANnel1")) == pytest.approx(0.65)


def test_simulator_trigger_alignment_respects_level_and_slope():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 2.0, 0.0, 0.0)}
    )
    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    backend.write(":TRIGger:EDGE:LEVel 0.5")
    backend.write(":TRIGger:EDGE:SLOPe POSitive")
    backend.write(":WAVeform:SOURce CHANnel1")

    assert backend._raw_waveform_voltage_at_index(500) == pytest.approx(0.5, abs=0.01)

    backend.write(":TRIGger:EDGE:SLOPe NEGative")

    assert backend._raw_waveform_voltage_at_index(500) == pytest.approx(0.5, abs=0.01)
    assert backend._raw_waveform_voltage_at_index(501) < backend._raw_waveform_voltage_at_index(
        500
    )


def test_simulator_channel_display_off_blocks_capture_and_invalidates_measurements():
    backend = SimulatorBackend()
    backend.write(":CHANnel1:DISPlay OFF")
    backend.write(":WAVeform:SOURce CHANnel1")

    with pytest.raises(SimulatorBackendError, match="display is off"):
        backend.query_binary_values(":WAVeform:DATA?", datatype="B")

    assert backend.query(":MEASure:VPP? CHANnel1") == "9.9E+37"
    assert backend.query(":MEASure:PHASe? CHANnel2,CHANnel1") == "9.9E+37"


def test_simulator_acquisition_modes_are_distinct_and_deterministic():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 1.0, 0.0, 0.0, 0.1)}
    )
    backend.write(":WAVeform:SOURce CHANnel1")

    normal = tuple(backend._waveform_voltage_at_index(index) for index in range(20))
    backend.write(":ACQuire:TYPE AVERage")
    backend.write(":ACQuire:COUNt 16")
    average = tuple(backend._waveform_voltage_at_index(index) for index in range(20))
    backend.write(":ACQuire:TYPE HRESolution")
    high_resolution = tuple(backend._waveform_voltage_at_index(index) for index in range(20))
    backend.write(":ACQuire:TYPE PEAK")
    peak = tuple(backend._waveform_voltage_at_index(index) for index in range(20))

    assert normal == tuple(backend._raw_waveform_voltage_at_index(index) for index in range(20))
    assert average != normal
    assert high_resolution != normal
    assert peak != normal
    assert peak == tuple(backend._waveform_voltage_at_index(index) for index in range(20))


def test_simulator_average_count_scales_deterministic_noise():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("dc", 0.0, 0.0, 0.0, 0.0, 0.16)}
    )
    backend.write(":WAVeform:SOURce CHANnel1")
    normal = backend._waveform_voltage_at_index(17)

    backend.write(":ACQuire:TYPE AVERage")
    backend.write(":ACQuire:COUNt 16")
    averaged = backend._waveform_voltage_at_index(17)

    assert averaged == pytest.approx(normal / 4.0)


def test_simulator_high_resolution_smooths_neighbors_and_reduces_noise():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 1.0, 0.0, 0.0, 0.12)}
    )
    backend.write(":WAVeform:SOURce CHANnel1")
    raw_neighbors = [
        backend._raw_waveform_voltage_at_index(index, noise_scale=0.5)
        for index in (99, 100, 101)
    ]

    backend.write(":ACQuire:TYPE HRESolution")

    assert backend._waveform_voltage_at_index(100) == pytest.approx(
        sum(raw_neighbors) / 3.0
    )


def test_simulator_peak_envelope_affects_measurement_extrema():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 2.0, 0.0, 0.0, 0.2)}
    )
    backend.write(":ACQuire:TYPE PEAK")

    assert float(backend.query(":MEASure:VPP? CHANnel1")) == pytest.approx(2.8)
    assert float(backend.query(":MEASure:VAMPLitude? CHANnel1")) == pytest.approx(1.4)
    assert float(backend.query(":MEASure:VMIN? CHANnel1")) == pytest.approx(-1.4)
    assert float(backend.query(":MEASure:VMAX? CHANnel1")) == pytest.approx(1.4)


def test_simulator_invalid_measurement_conditions_return_sentinel():
    backend = SimulatorBackend(
        signals={
            1: SimulatedSignal("sine", 10.0, 1.0, 0.0, 0.0),
            2: SimulatedSignal("sine", 1000.0, 0.0, 0.0, 0.0),
        }
    )

    assert backend.query(":MEASure:FREQuency? CHANnel1") == "9.9E+37"
    assert backend.query(":MEASure:TEDGe? +99,CHANnel1") == "9.9E+37"
    assert backend.query(":MEASure:TVALue? 2,+1,CHANnel1") == "9.9E+37"
    assert backend.query(":MEASure:RISetime? CHANnel2") == "9.9E+37"
    assert float(backend.query(":MEASure:VPP? CHANnel2")) == pytest.approx(0.0)


def test_simulator_trigger_alignment_handles_all_public_slopes():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 2.0, 0.0, 0.0)}
    )
    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    backend.write(":TRIGger:EDGE:LEVel 0")
    backend.write(":WAVeform:SOURce CHANnel1")

    backend.write(":TRIGger:EDGE:SLOPe POSitive")
    assert backend._raw_waveform_voltage_at_index(500) == pytest.approx(0.0, abs=0.01)
    assert backend._raw_waveform_voltage_at_index(501) > backend._raw_waveform_voltage_at_index(500)

    backend.write(":TRIGger:EDGE:SLOPe NEGative")
    assert backend._raw_waveform_voltage_at_index(500) == pytest.approx(0.0, abs=0.01)
    assert backend._raw_waveform_voltage_at_index(501) < backend._raw_waveform_voltage_at_index(500)

    backend.write(":TRIGger:EDGE:SLOPe EITHer")
    assert backend._trigger_time_offset_s() == pytest.approx(0.0)

    backend.write(":TRIGger:EDGE:SLOPe ALTernate")
    first = tuple(backend.query_binary_values(":WAVeform:DATA?", datatype="B")[:3])
    second = tuple(backend.query_binary_values(":WAVeform:DATA?", datatype="B")[:3])
    assert first != second


def test_simulator_trigger_out_of_range_level_does_not_align():
    backend = SimulatorBackend(
        signals={1: SimulatedSignal("sine", 1000.0, 2.0, 0.0, 90.0)}
    )
    backend.write(":TRIGger:EDGE:SOURce CHANnel1")
    backend.write(":TRIGger:EDGE:LEVel 5")

    assert backend._trigger_time_offset_s() == 0.0
