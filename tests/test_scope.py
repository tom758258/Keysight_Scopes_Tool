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
