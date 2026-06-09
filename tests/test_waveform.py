import json

import pytest

from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.errors import ParameterValidationError, WaveformResponseError
from keysight_scope.fake_backend import FakeBackend
from keysight_scope.idn import parse_idn
from keysight_scope.scpi import SCPIClient
from keysight_scope.waveform import (
    MultiChannelWaveformCapture,
    WaveformController,
    convert_byte_waveform,
    convert_word_waveform,
    parse_waveform_preamble,
    validate_waveform_points,
    waveform_byte_order_command,
    waveform_data_query,
    waveform_format_byte_command,
    waveform_format_word_command,
    waveform_points_command,
    waveform_preamble_query,
    waveform_source_command,
    waveform_unsigned_command,
    write_waveform_csv,
    write_waveform_metadata,
    write_waveforms_csv,
    write_waveforms_metadata,
)


PREAMBLE = "0,0,4,1,1.0E-6,-1.0E-6,0,2.0E-2,-2.56,128"


def test_waveform_commands_use_keysight_syntax():
    assert waveform_source_command(1) == ":WAVeform:SOURce CHANnel1"
    assert waveform_format_byte_command() == ":WAVeform:FORMat BYTE"
    assert waveform_format_word_command() == ":WAVeform:FORMat WORD"
    assert waveform_byte_order_command() == ":WAVeform:BYTeorder MSBFirst"
    assert waveform_unsigned_command() == ":WAVeform:UNSigned ON"
    assert waveform_points_command(1000) == ":WAVeform:POINts 1000"
    assert waveform_preamble_query() == ":WAVeform:PREamble?"
    assert waveform_data_query() == ":WAVeform:DATA?"


def test_parse_waveform_preamble():
    preamble = parse_waveform_preamble(PREAMBLE)

    assert preamble.format_code == 0
    assert preamble.type_code == 0
    assert preamble.points == 4
    assert preamble.count == 1
    assert preamble.x_increment == 1e-6
    assert preamble.x_origin == -1e-6
    assert preamble.x_reference == 0
    assert preamble.y_increment == 0.02
    assert preamble.y_origin == -2.56
    assert preamble.y_reference == 128


@pytest.mark.parametrize("raw", ["0,0,4", "0,0,0,1,1,0,0,1,0,0", "0,0,4,1,nan,0,0,1,0,0"])
def test_parse_waveform_preamble_rejects_invalid_response(raw):
    with pytest.raises(WaveformResponseError):
        parse_waveform_preamble(raw)


def test_convert_byte_waveform_uses_preamble_scaling():
    preamble = parse_waveform_preamble(PREAMBLE)

    capture = convert_byte_waveform(1, 1000, preamble, [128, 129, 130, 127])

    assert capture.time_s == pytest.approx((-1e-6, 0.0, 1e-6, 2e-6))
    assert capture.voltage_v == pytest.approx((-2.56, -2.54, -2.52, -2.58))


def test_convert_byte_waveform_rejects_out_of_range_byte():
    preamble = parse_waveform_preamble(PREAMBLE)

    with pytest.raises(WaveformResponseError):
        convert_byte_waveform(1, 1000, preamble, [256])


def test_convert_word_waveform_uses_preamble_scaling():
    preamble = parse_waveform_preamble("1,0,3,1,1.0E-6,0,0,1.0E-4,0,32768")

    capture = convert_word_waveform(1, 1000, preamble, [32768, 32769, 32767])

    assert capture.format_name == "WORD"
    assert capture.byte_order == "MSBFirst"
    assert capture.unsigned is True
    assert capture.time_s == pytest.approx((0.0, 1e-6, 2e-6))
    assert capture.voltage_v == pytest.approx((0.0, 0.0001, -0.0001))


def test_convert_word_waveform_rejects_out_of_range_word():
    preamble = parse_waveform_preamble("1,0,1,1,1.0E-6,0,0,1.0E-4,0,32768")

    with pytest.raises(WaveformResponseError):
        convert_word_waveform(1, 1000, preamble, [65536])


@pytest.mark.parametrize("points", [1000, 5000, 10000])
def test_validate_waveform_points_accepts_supported_byte_point_counts(points):
    assert validate_waveform_points(points, capabilities_for_model("DSOX4024A")) == points


def test_validate_waveform_points_rejects_unsupported_point_count():
    with pytest.raises(ParameterValidationError):
        validate_waveform_points(2000, capabilities_for_model("DSOX4024A"))


def test_waveform_controller_captures_byte_data():
    backend = FakeBackend(
        responses={":WAVeform:PREamble?": PREAMBLE},
        binary_responses={":WAVeform:DATA?": [128, 129, 130, 127]},
    )
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    capture = controller.capture_byte(1, points=5000)

    assert capture.channel == 1
    assert capture.requested_points == 5000
    assert capture.raw_samples == (128, 129, 130, 127)
    assert backend.history == [
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat BYTE",
        ":WAVeform:POINts 5000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
    ]


def test_waveform_controller_captures_word_data_with_fixed_binary_options():
    backend = FakeBackend(
        responses={":WAVeform:PREamble?": "1,0,3,1,1.0E-6,0,0,1.0E-4,0,32768"},
        binary_responses={":WAVeform:DATA?": [32768, 32769, 32767]},
    )
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    capture = controller.capture_word(1, points=10000)

    assert capture.channel == 1
    assert capture.requested_points == 10000
    assert capture.raw_samples == (32768, 32769, 32767)
    assert capture.format_name == "WORD"
    assert backend.history == [
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat WORD",
        ":WAVeform:BYTeorder MSBFirst",
        ":WAVeform:UNSigned ON",
        ":WAVeform:POINts 10000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
    ]
    assert backend.binary_query_kwargs == [{"datatype": "H", "is_big_endian": True}]


def test_waveform_controller_captures_multiple_byte_channels_in_order():
    backend = FakeBackend(
        responses={":WAVeform:PREamble?": PREAMBLE},
        binary_responses={":WAVeform:DATA?": [128, 129, 130, 127]},
    )
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    capture = controller.capture_channels_byte((2, 1), points=5000)

    assert isinstance(capture, MultiChannelWaveformCapture)
    assert capture.channels == (2, 1)
    assert [item.channel for item in capture.captures] == [2, 1]
    assert backend.history == [
        ":WAVeform:SOURce CHANnel2",
        ":WAVeform:FORMat BYTE",
        ":WAVeform:POINts 5000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat BYTE",
        ":WAVeform:POINts 5000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
    ]


def test_waveform_controller_captures_multiple_word_channels_in_order():
    backend = FakeBackend(
        responses={":WAVeform:PREamble?": "1,0,3,1,1.0E-6,0,0,1.0E-4,0,32768"},
        binary_responses={":WAVeform:DATA?": [32768, 32769, 32767]},
    )
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    capture = controller.capture_channels_word((1, 3), points=10000)

    assert capture.channels == (1, 3)
    assert backend.history == [
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat WORD",
        ":WAVeform:BYTeorder MSBFirst",
        ":WAVeform:UNSigned ON",
        ":WAVeform:POINts 10000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
        ":WAVeform:SOURce CHANnel3",
        ":WAVeform:FORMat WORD",
        ":WAVeform:BYTeorder MSBFirst",
        ":WAVeform:UNSigned ON",
        ":WAVeform:POINts 10000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
    ]
    assert backend.binary_query_kwargs == [
        {"datatype": "H", "is_big_endian": True},
        {"datatype": "H", "is_big_endian": True},
    ]


def test_waveform_controller_rejects_duplicate_channels_before_scpi():
    backend = FakeBackend()
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    with pytest.raises(ParameterValidationError, match="duplicate waveform channels"):
        controller.capture_channels_byte((1, 1), points=1000)

    assert backend.history == []


def test_waveform_controller_rejects_unexpected_word_preamble_format():
    backend = FakeBackend(
        responses={":WAVeform:PREamble?": PREAMBLE},
        binary_responses={":WAVeform:DATA?": [128, 129]},
    )
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    with pytest.raises(WaveformResponseError, match="Expected WORD waveform preamble format 1"):
        controller.capture_word(1, points=1000)

    assert backend.history == [
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat WORD",
        ":WAVeform:BYTeorder MSBFirst",
        ":WAVeform:UNSigned ON",
        ":WAVeform:POINts 1000",
        ":WAVeform:PREamble?",
    ]


def test_waveform_controller_rejects_invalid_channel_before_scpi():
    backend = FakeBackend()
    controller = WaveformController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.capture_byte(3, points=1000)

    assert backend.history == []


def test_waveform_export_writes_csv_and_metadata(tmp_path):
    preamble = parse_waveform_preamble(PREAMBLE)
    capture = convert_byte_waveform(1, 1000, preamble, [128, 129])
    idn = parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20")
    csv_path = tmp_path / "waveform.csv"
    meta_path = tmp_path / "waveform_meta.json"

    write_waveform_csv(capture, csv_path)
    write_waveform_metadata(capture, meta_path, idn=idn, resource="USB0::FAKE::INSTR")

    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        "time_s,ch1_v",
        "-1e-06,-2.56",
        "0.0,-2.54",
    ]
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["idn"] == "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20"
    assert metadata["resource"] == "USB0::FAKE::INSTR"
    assert metadata["channel"] == 1
    assert metadata["actual_points"] == 2
    assert metadata["format"] == "BYTE"


def test_waveform_export_writes_word_metadata(tmp_path):
    preamble = parse_waveform_preamble("1,0,2,1,1.0E-6,0,0,1.0E-4,0,32768")
    capture = convert_word_waveform(1, 1000, preamble, [32768, 32769])
    idn = parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20")
    meta_path = tmp_path / "waveform_meta.json"

    write_waveform_metadata(capture, meta_path, idn=idn, resource="USB0::FAKE::INSTR")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["format"] == "WORD"
    assert metadata["byte_order"] == "MSBFirst"
    assert metadata["unsigned"] is True


def test_multi_channel_waveform_export_writes_aligned_csv(tmp_path):
    preamble = parse_waveform_preamble(PREAMBLE)
    ch1 = convert_byte_waveform(1, 1000, preamble, [128, 129])
    ch2 = convert_byte_waveform(2, 1000, preamble, [130, 127])
    capture = MultiChannelWaveformCapture((ch1, ch2))
    csv_path = tmp_path / "waveform.csv"

    write_waveforms_csv(capture, csv_path)

    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        "time_s,ch1_v,ch2_v",
        "-1e-06,-2.56,-2.52",
        "0.0,-2.54,-2.58",
    ]


def test_multi_channel_waveform_export_rejects_mismatched_sample_count(tmp_path):
    preamble = parse_waveform_preamble(PREAMBLE)
    ch1 = convert_byte_waveform(1, 1000, preamble, [128, 129])
    ch2 = convert_byte_waveform(2, 1000, preamble, [130])
    capture = MultiChannelWaveformCapture((ch1, ch2))

    with pytest.raises(WaveformResponseError, match="has 1 samples"):
        write_waveforms_csv(capture, tmp_path / "waveform.csv")

    assert not (tmp_path / "waveform.csv").exists()


def test_multi_channel_waveform_export_rejects_mismatched_time_axis(tmp_path):
    ch1 = convert_byte_waveform(1, 1000, parse_waveform_preamble(PREAMBLE), [128, 129])
    ch2 = convert_byte_waveform(
        2,
        1000,
        parse_waveform_preamble("0,0,2,1,2.0E-6,-1.0E-6,0,2.0E-2,-2.56,128"),
        [130, 127],
    )
    capture = MultiChannelWaveformCapture((ch1, ch2))

    with pytest.raises(WaveformResponseError, match="time axis does not match"):
        write_waveforms_csv(capture, tmp_path / "waveform.csv")

    assert not (tmp_path / "waveform.csv").exists()


def test_multi_channel_waveform_export_writes_ordered_metadata(tmp_path):
    preamble = parse_waveform_preamble("1,0,2,1,1.0E-6,0,0,1.0E-4,0,32768")
    ch2 = convert_word_waveform(2, 5000, preamble, [32768, 32769])
    ch1 = convert_word_waveform(1, 5000, preamble, [32770, 32767])
    capture = MultiChannelWaveformCapture((ch2, ch1))
    idn = parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20")
    meta_path = tmp_path / "waveform_meta.json"

    write_waveforms_metadata(capture, meta_path, idn=idn, resource="USB0::FAKE::INSTR")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["idn"] == "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20"
    assert metadata["resource"] == "USB0::FAKE::INSTR"
    assert metadata["requested_points"] == 5000
    assert metadata["format"] == "WORD"
    assert [item["channel"] for item in metadata["channels"]] == [2, 1]
    assert [item["actual_points"] for item in metadata["channels"]] == [2, 2]
    assert metadata["channels"][0]["byte_order"] == "MSBFirst"
    assert metadata["channels"][0]["unsigned"] is True
