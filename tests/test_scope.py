from keysight_scope.fake_backend import FakeBackend
from keysight_scope.scope import KeysightScope
from keysight_scope.errors import ParameterValidationError


def test_scope_queries_idn_and_loads_capabilities():
    backend = FakeBackend(responses={"*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4034A,MY1,02.50"})
    scope = KeysightScope(backend)

    idn = scope.query_idn()

    assert idn.model == "DSOX4034A"
    assert scope.capabilities is not None
    assert scope.capabilities.series == "4000X"
    assert backend.history == ["*IDN?"]


def test_scope_keeps_unknown_capabilities_none():
    backend = FakeBackend(responses={"*IDN?": "ACME,MODEL1,SN1,FW1"})
    scope = KeysightScope(backend)

    idn = scope.query_idn()

    assert idn.model == "MODEL1"
    assert idn.series is None
    assert scope.capabilities is None


def test_scope_context_manager_closes_backend():
    backend = FakeBackend()

    with KeysightScope(backend):
        pass

    assert backend.closed is True


def test_scope_queries_system_error():
    backend = FakeBackend(responses={":SYSTem:ERRor?": '-113,"Undefined header"'})
    scope = KeysightScope(backend)

    entry = scope.query_system_error()

    assert entry.code == -113
    assert entry.message == "Undefined header"
    assert backend.history == [":SYSTem:ERRor?"]


def test_scope_control_methods_send_one_command_each():
    backend = FakeBackend()
    scope = KeysightScope(backend)

    scope.stop()
    scope.run()
    scope.single()

    assert backend.history == [":STOP", ":RUN", ":SINGle"]


def test_scope_drains_system_errors_until_no_error():
    class SequencedBackend(FakeBackend):
        def __init__(self):
            super().__init__()
            self.sequence = [
                '-113,"Undefined header"',
                '-222,"Data out of range"',
                '+0,"No error"',
            ]

        def query(self, command: str) -> str:
            self._ensure_open()
            self.history.append(command)
            if command == ":SYSTem:ERRor?":
                return self.sequence.pop(0)
            return super().query(command)

    backend = SequencedBackend()
    scope = KeysightScope(backend)

    entries = scope.drain_system_errors()

    assert [entry.code for entry in entries] == [-113, -222, 0]
    assert backend.history == [
        ":SYSTem:ERRor?",
        ":SYSTem:ERRor?",
        ":SYSTem:ERRor?",
    ]


def test_scope_rejects_invalid_error_drain_limit():
    scope = KeysightScope(FakeBackend())

    try:
        scope.drain_system_errors(max_reads=0)
    except ValueError as exc:
        assert "max_reads" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_scope_channel_display_requires_known_capabilities():
    scope = KeysightScope(FakeBackend())

    try:
        scope.set_channel_display(1, True)
    except ParameterValidationError as exc:
        assert "query_idn" in str(exc)
    else:
        raise AssertionError("Expected ParameterValidationError")


def test_scope_channel_display_uses_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4022A,MY1,07.20",
            ":CHANnel2:DISPlay?": "0",
        }
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    scope.set_channel_display(2, True)
    display = scope.query_channel_display(2)

    assert display is False
    assert backend.history == ["*IDN?", ":CHANnel2:DISPlay ON", ":CHANnel2:DISPlay?"]


def test_scope_rejects_channel_above_capability_before_display_scpi():
    backend = FakeBackend(responses={"*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4022A,MY1,07.20"})
    scope = KeysightScope(backend)

    scope.query_idn()
    try:
        scope.set_channel_display(3, True)
    except ParameterValidationError:
        pass
    else:
        raise AssertionError("Expected ParameterValidationError")

    assert backend.history == ["*IDN?"]


def test_scope_channel_scale_and_offset_use_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20",
            ":CHANnel1:SCALe?": "5.0E-1",
            ":CHANnel1:OFFSet?": "-1.25E-1",
        }
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    scope.set_channel_scale(1, 0.5)
    scale = scope.query_channel_scale(1)
    scope.set_channel_offset(1, -0.125)
    offset = scope.query_channel_offset(1)

    assert scale == 0.5
    assert offset == -0.125
    assert backend.history == [
        "*IDN?",
        ":CHANnel1:SCALe 0.5",
        ":CHANnel1:SCALe?",
        ":CHANnel1:OFFSet -0.125",
        ":CHANnel1:OFFSet?",
    ]


def test_scope_rejects_channel_above_capability_before_scale_scpi():
    backend = FakeBackend(responses={"*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4022A,MY1,07.20"})
    scope = KeysightScope(backend)

    scope.query_idn()
    try:
        scope.set_channel_scale(3, 0.5)
    except ParameterValidationError:
        pass
    else:
        raise AssertionError("Expected ParameterValidationError")

    assert backend.history == ["*IDN?"]


def test_scope_timebase_requires_known_capabilities():
    scope = KeysightScope(FakeBackend())

    try:
        scope.set_timebase_scale(0.001)
    except ParameterValidationError as exc:
        assert "query_idn" in str(exc)
    else:
        raise AssertionError("Expected ParameterValidationError")


def test_scope_timebase_scale_and_position_use_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20",
            ":TIMebase:SCALe?": "1.0E-3",
            ":TIMebase:POSition?": "-5.0E-4",
        }
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    scope.set_timebase_scale(0.001)
    scale = scope.query_timebase_scale()
    scope.set_timebase_position(-0.0005)
    position = scope.query_timebase_position()

    assert scale == 0.001
    assert position == -0.0005
    assert backend.history == [
        "*IDN?",
        ":TIMebase:SCALe 0.001",
        ":TIMebase:SCALe?",
        ":TIMebase:POSition -0.0005",
        ":TIMebase:POSition?",
    ]


def test_scope_edge_trigger_requires_known_capabilities():
    scope = KeysightScope(FakeBackend())

    try:
        scope.configure_edge_trigger(source_channel=1, level_volts=0.0, slope="positive")
    except ParameterValidationError as exc:
        assert "query_idn" in str(exc)
    else:
        raise AssertionError("Expected ParameterValidationError")


def test_scope_edge_trigger_uses_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20",
            ":TRIGger:EDGE:SOURce?": "CHAN1",
            ":TRIGger:EDGE:LEVel?": "2.5E-1",
            ":TRIGger:EDGE:SLOPe?": "POS",
        }
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    scope.configure_edge_trigger(source_channel=1, level_volts=0.25, slope="positive")
    state = scope.query_edge_trigger()

    assert state.source_channel == 1
    assert state.level_volts == 0.25
    assert state.slope == "positive"
    assert backend.history == [
        "*IDN?",
        ":TRIGger:MODE EDGE",
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel 0.25",
        ":TRIGger:EDGE:SLOPe POSitive",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:SLOPe?",
    ]


def test_scope_waveform_requires_known_capabilities():
    scope = KeysightScope(FakeBackend())

    try:
        scope.capture_waveform_byte(1, points=1000)
    except ParameterValidationError as exc:
        assert "query_idn" in str(exc)
    else:
        raise AssertionError("Expected ParameterValidationError")


def test_scope_measurement_requires_known_capabilities():
    scope = KeysightScope(FakeBackend())

    try:
        scope.query_measurement(1, "vpp")
    except ParameterValidationError as exc:
        assert "query_idn" in str(exc)
    else:
        raise AssertionError("Expected ParameterValidationError")


def test_scope_measurement_uses_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20",
            ":MEASure:VPP? CHANnel1": "5.0E-1",
        }
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    result = scope.query_measurement(1, "vpp")

    assert result.valid is True
    assert result.value == 0.5
    assert backend.history == ["*IDN?", ":MEASure:VPP? CHANnel1"]


def test_scope_waveform_capture_uses_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20",
            ":WAVeform:PREamble?": "0,0,2,1,1.0E-6,0,0,2.0E-2,-2.56,128",
        },
        binary_responses={":WAVeform:DATA?": [128, 129]},
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    capture = scope.capture_waveform_byte(1, points=1000)

    assert capture.raw_samples == (128, 129)
    assert backend.history == [
        "*IDN?",
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat BYTE",
        ":WAVeform:POINts 1000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
    ]


def test_scope_word_waveform_capture_uses_capabilities_from_idn():
    backend = FakeBackend(
        responses={
            "*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,07.20",
            ":WAVeform:PREamble?": "1,0,2,1,1.0E-6,0,0,1.0E-4,0,32768",
        },
        binary_responses={":WAVeform:DATA?": [32768, 32769]},
    )
    scope = KeysightScope(backend)

    scope.query_idn()
    capture = scope.capture_waveform_word(1, points=1000)

    assert capture.raw_samples == (32768, 32769)
    assert capture.format_name == "WORD"
    assert backend.history == [
        "*IDN?",
        ":WAVeform:SOURce CHANnel1",
        ":WAVeform:FORMat WORD",
        ":WAVeform:BYTeorder MSBFirst",
        ":WAVeform:UNSigned ON",
        ":WAVeform:POINts 1000",
        ":WAVeform:PREamble?",
        ":WAVeform:DATA?",
    ]
