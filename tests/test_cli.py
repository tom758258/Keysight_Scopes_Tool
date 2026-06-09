import pytest

from keysight_scope import cli
from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.errors import KeysightScopeError
from keysight_scope.idn import parse_idn
from keysight_scope.status import SystemErrorEntry
from keysight_scope.visa_backend import VisaResourceListing


def test_list_resources_cli_prints_backend_and_resources(monkeypatch, capsys):
    def fake_list_visa_resources(visa_library=None):
        assert visa_library is None
        return VisaResourceListing(
            resources=("USB0::0x2A8D::FAKE::INSTR",),
            backend="Test VISA backend",
        )

    monkeypatch.setattr(cli, "list_visa_resources", fake_list_visa_resources)

    assert cli.main(["list-resources"]) == 0

    out = capsys.readouterr().out
    assert "PyVISA backend: Test VISA backend" in out
    assert "USB0::0x2A8D::FAKE::INSTR" in out


def test_list_resources_cli_prints_empty_resources(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_visa_resources",
        lambda visa_library=None: VisaResourceListing(resources=(), backend="backend"),
    )

    assert cli.main(["list-resources"]) == 0

    assert "<none>" in capsys.readouterr().out


def test_list_resources_live_only_prints_only_idn_responsive_resources(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()

        def __init__(self, resource):
            self.resource = resource

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_idn(self):
            return parse_idn(f"KEYSIGHT TECHNOLOGIES,{self.resource},SN1,FW1")

    def fake_list_visa_resources(visa_library=None):
        assert visa_library == "@sim"
        return VisaResourceListing(
            resources=("DSOX4024A", "STALE::RESOURCE", "DSOX4034A"),
            backend="Test VISA backend",
        )

    def fake_open(resource, visa_library=None):
        assert visa_library == "@sim"
        if resource == "STALE::RESOURCE":
            raise KeysightScopeError("not reachable")
        return DummyScope(resource)

    monkeypatch.setattr(cli, "list_visa_resources", fake_list_visa_resources)
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fake_open))

    assert cli.main(["list-resources", "--live-only", "--visa-library", "@sim"]) == 0

    out = capsys.readouterr().out
    assert "PyVISA backend: Test VISA backend" in out
    assert "Live resources:" in out
    assert "DSOX4024A" in out
    assert "DSOX4034A" in out
    assert "STALE::RESOURCE" not in out


def test_list_resources_live_only_prints_none_when_no_resources_respond(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_visa_resources",
        lambda visa_library=None: VisaResourceListing(
            resources=("STALE::RESOURCE",),
            backend="backend",
        ),
    )
    monkeypatch.setattr(
        cli.KeysightScope,
        "open",
        staticmethod(
            lambda resource, visa_library=None: (_ for _ in ()).throw(
                KeysightScopeError("not reachable")
            )
        ),
    )

    assert cli.main(["list-resources", "--live-only"]) == 0

    out = capsys.readouterr().out
    assert "Live resources:" in out
    assert "<none>" in out
    assert "STALE::RESOURCE" not in out


def test_verify_cli_queries_scope(monkeypatch, capsys):
    class DummyBackend:
        backend = "Test VISA backend"
        timeout = 2000

    class DummyScope:
        backend = DummyBackend()
        capabilities = capabilities_for_model("DSOX4024A")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_idn(self):
            return parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY12345678,02.50")

    def fake_open(resource, visa_library=None):
        assert resource == "USB0::FAKE::INSTR"
        assert visa_library is None
        return DummyScope()

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fake_open))

    assert cli.main(["verify", "--resource", "USB0::FAKE::INSTR"]) == 0

    out = capsys.readouterr().out
    assert "Model: DSOX4024A" in out
    assert "Series: 4000X" in out
    assert "Analog channels: 4" in out


def test_verify_cli_uses_environment_resource(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()
        capabilities = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_idn(self):
            return parse_idn("ACME,MODEL1,SN1,FW1")

    monkeypatch.setenv("KEYSIGHT_SCOPE_RESOURCE", "USB0::ENV::INSTR")
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: DummyScope()))

    assert cli.main(["verify"]) == 0

    out = capsys.readouterr().out
    assert "Resource: USB0::ENV::INSTR" in out
    assert "Series: unknown" in out


def test_verify_cli_requires_resource(capsys):
    assert cli.main(["verify"]) == 2

    err = capsys.readouterr().err
    assert "--resource is required" in err


def test_old_list_command_is_not_registered():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["list"])

    assert excinfo.value.code == 2


def test_old_idn_command_is_not_registered():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["idn"])

    assert excinfo.value.code == 2


def test_state_command_is_not_registered():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["state"])

    assert excinfo.value.code == 2


def test_check_error_cli_reads_one_entry(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_system_error(self):
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: DummyScope()))

    assert cli.main(["check-error", "--resource", "USB0::FAKE::INSTR"]) == 0

    assert 'System error: +0, "No error"' in capsys.readouterr().out


def test_check_error_cli_drain_returns_failure_when_errors_found(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def drain_system_errors(self, max_reads=30):
            assert max_reads == 5
            return (
                SystemErrorEntry(code=-113, message="Undefined header", raw='-113,"Undefined header"'),
                SystemErrorEntry(code=0, message="No error", raw='+0,"No error"'),
            )

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: DummyScope()))

    assert cli.main(["check-error", "--resource", "USB0::FAKE::INSTR", "--all", "--max-reads", "5"]) == 1

    out = capsys.readouterr().out
    assert 'System error 1: -113, "Undefined header"' in out
    assert 'System error 2: +0, "No error"' in out


def test_control_cli_sends_command_then_error_post_check(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = 2000

    class DummyScope:
        backend = DummyBackend()

        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def stop(self):
            self.calls.append("stop")

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scopes = []

    def fake_open(resource, visa_library=None):
        assert resource == "USB0::FAKE::INSTR"
        assert visa_library is None
        scope = DummyScope()
        scopes.append(scope)
        return scope

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fake_open))

    assert cli.main(["stop", "--resource", "USB0::FAKE::INSTR"]) == 0

    assert scopes[0].calls == ["stop", "query_system_error"]
    out = capsys.readouterr().out
    assert "Command: :STOP" in out
    assert 'System error: +0, "No error"' in out


def test_control_cli_returns_failure_when_post_check_reports_error(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def run(self):
            pass

        def query_system_error(self):
            return SystemErrorEntry(code=-113, message="Undefined header", raw='-113,"Undefined header"')

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: DummyScope()))

    assert cli.main(["run", "--resource", "USB0::FAKE::INSTR"]) == 1

    assert 'System error: -113, "Undefined header"' in capsys.readouterr().out


def test_channel_display_cli_turns_channel_on_then_checks_error(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = 2000

    class DummyScope:
        backend = DummyBackend()

        def __init__(self):
            self.capabilities = None
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_idn(self):
            self.calls.append("query_idn")
            self.capabilities = capabilities_for_model("DSOX4024A")
            return parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY123,07.20")

        def set_channel_display(self, channel, enabled):
            self.calls.append(("set_channel_display", channel, enabled))

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scopes = []

    def fake_open(resource, visa_library=None):
        assert resource == "USB0::FAKE::INSTR"
        assert visa_library is None
        scope = DummyScope()
        scopes.append(scope)
        return scope

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(fake_open))

    assert (
        cli.main(
            [
                "channel-display",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--on",
            ]
        )
        == 0
    )

    assert scopes[0].calls == [
        "query_idn",
        ("set_channel_display", 1, True),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Resource: USB0::FAKE::INSTR" in out
    assert "Timeout ms: 2000" in out
    assert "Planned change: CH1 display ON" in out
    assert "Command: :CHANnel1:DISPlay ON" in out
    assert 'System error: +0, "No error"' in out


def test_channel_display_cli_queries_display_then_checks_error(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()

        def __init__(self):
            self.capabilities = None
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_idn(self):
            self.calls.append("query_idn")
            self.capabilities = capabilities_for_model("DSOX4024A")
            return parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY123,07.20")

        def query_channel_display(self, channel):
            self.calls.append(("query_channel_display", channel))
            return False

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-display",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "2",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_channel_display", 2), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH2 display state" in out
    assert "Command: :CHANnel2:DISPlay?" in out
    assert "Display: OFF" in out


def test_channel_display_cli_rejects_channel_above_detected_capabilities(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyScope:
        backend = DummyBackend()

        def __init__(self):
            self.capabilities = None
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback

        def query_idn(self):
            self.calls.append("query_idn")
            self.capabilities = capabilities_for_model("DSOX4022A")
            return parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4022A,MY123,07.20")

        def set_channel_display(self, channel, enabled):
            self.calls.append(("set_channel_display", channel, enabled))

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-display",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "3",
                "--on",
            ]
        )
        == 1
    )

    assert scope.calls == ["query_idn"]
    err = capsys.readouterr().err
    assert "channel 3 is not available" in err
