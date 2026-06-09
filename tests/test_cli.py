from datetime import datetime
from pathlib import Path

import pytest

from keysight_scope import cli
from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.errors import KeysightScopeError
from keysight_scope.idn import parse_idn
from keysight_scope.measurements import MeasurementResult
from keysight_scope.screenshot import ScreenshotCapture
from keysight_scope.status import SystemErrorEntry
from keysight_scope.visa_backend import VisaResourceListing
from keysight_scope.waveform import WaveformCapture, WaveformPreamble


class _ChannelParameterDummyBackend:
    backend = "backend"
    timeout = 2000


class _ChannelParameterDummyScope:
    backend = _ChannelParameterDummyBackend()

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

    def set_channel_coupling(self, channel, coupling):
        self.calls.append(("set_channel_coupling", channel, coupling))

    def query_channel_coupling(self, channel):
        self.calls.append(("query_channel_coupling", channel))
        return "dc"

    def set_channel_probe_ratio(self, channel, ratio):
        self.calls.append(("set_channel_probe_ratio", channel, ratio))

    def query_channel_probe_ratio(self, channel):
        self.calls.append(("query_channel_probe_ratio", channel))
        return 10

    def set_channel_bandwidth_limit(self, channel, enabled):
        self.calls.append(("set_channel_bandwidth_limit", channel, enabled))

    def query_channel_bandwidth_limit(self, channel):
        self.calls.append(("query_channel_bandwidth_limit", channel))
        return True

    def query_system_error(self):
        self.calls.append("query_system_error")
        return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')


def _install_channel_parameter_scope(monkeypatch):
    scope = _ChannelParameterDummyScope()
    monkeypatch.setattr(
        cli.KeysightScope,
        "open",
        staticmethod(lambda resource, visa_library=None: scope),
    )
    return scope


class _MeasurementDummyBackend:
    backend = "backend"
    timeout = None


class _MeasurementDummyScope:
    backend = _MeasurementDummyBackend()

    def __init__(self, result_value, raw_value, unit, valid=True, reason=None):
        self.capabilities = None
        self.calls = []
        self.result_value = result_value
        self.raw_value = raw_value
        self.unit = unit
        self.valid = valid
        self.reason = reason

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback

    def query_idn(self):
        self.calls.append("query_idn")
        self.capabilities = capabilities_for_model("DSOX4024A")
        return parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY123,07.20")

    def query_measurement(self, channel, item):
        self.calls.append(("query_measurement", channel, item))
        return MeasurementResult(
            item=item,
            channel=channel,
            value=self.result_value,
            raw_value=self.raw_value,
            valid=self.valid,
            unit=self.unit,
            reason=self.reason,
        )

    def query_system_error(self):
        self.calls.append("query_system_error")
        return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')


def _install_measurement_scope(monkeypatch, result_value, raw_value, unit, valid=True, reason=None):
    scope = _MeasurementDummyScope(result_value, raw_value, unit, valid=valid, reason=reason)
    monkeypatch.setattr(
        cli.KeysightScope,
        "open",
        staticmethod(lambda resource, visa_library=None: scope),
    )
    return scope


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


def test_channel_scale_cli_sets_scale_then_checks_error(monkeypatch, capsys):
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

        def set_channel_scale(self, channel, volts_per_division):
            self.calls.append(("set_channel_scale", channel, volts_per_division))

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-scale",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--volts-per-division",
                "0.5",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("set_channel_scale", 1, 0.5), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned change: CH1 scale 0.5 V/div" in out
    assert "Command: :CHANnel1:SCALe 0.5" in out
    assert 'System error: +0, "No error"' in out


def test_channel_scale_cli_queries_scale_then_checks_error(monkeypatch, capsys):
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

        def query_channel_scale(self, channel):
            self.calls.append(("query_channel_scale", channel))
            return 0.5

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-scale",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "2",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_channel_scale", 2), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH2 scale" in out
    assert "Command: :CHANnel2:SCALe?" in out
    assert "Scale V/div: 0.5" in out


def test_channel_offset_cli_sets_offset_then_checks_error(monkeypatch, capsys):
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

        def set_channel_offset(self, channel, volts):
            self.calls.append(("set_channel_offset", channel, volts))

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-offset",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--volts",
                "-0.125",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("set_channel_offset", 1, -0.125), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned change: CH1 offset -0.125 V" in out
    assert "Command: :CHANnel1:OFFSet -0.125" in out
    assert 'System error: +0, "No error"' in out


def test_channel_offset_cli_queries_offset_then_checks_error(monkeypatch, capsys):
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

        def query_channel_offset(self, channel):
            self.calls.append(("query_channel_offset", channel))
            return -0.125

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-offset",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "2",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_channel_offset", 2), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH2 offset" in out
    assert "Command: :CHANnel2:OFFSet?" in out
    assert "Offset V: -0.125" in out


def test_channel_scale_cli_rejects_channel_above_detected_capabilities(monkeypatch, capsys):
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

        def set_channel_scale(self, channel, volts_per_division):
            self.calls.append(("set_channel_scale", channel, volts_per_division))

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "channel-scale",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "3",
                "--volts-per-division",
                "0.5",
            ]
        )
        == 1
    )

    assert scope.calls == ["query_idn"]
    err = capsys.readouterr().err
    assert "channel 3 is not available" in err


def test_channel_coupling_cli_sets_coupling_then_checks_error(monkeypatch, capsys):
    scope = _install_channel_parameter_scope(monkeypatch)

    assert (
        cli.main(
            [
                "channel-coupling",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--coupling",
                "ac",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("set_channel_coupling", 1, "ac"), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned change: CH1 coupling AC" in out
    assert "Command: :CHANnel1:COUPling AC" in out
    assert 'System error: +0, "No error"' in out


def test_channel_coupling_cli_queries_coupling_then_checks_error(monkeypatch, capsys):
    scope = _install_channel_parameter_scope(monkeypatch)

    assert (
        cli.main(
            [
                "channel-coupling",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "2",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_channel_coupling", 2), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH2 coupling" in out
    assert "Command: :CHANnel2:COUPling?" in out
    assert "Coupling: DC" in out


def test_channel_probe_cli_sets_ratio_then_checks_error(monkeypatch, capsys):
    scope = _install_channel_parameter_scope(monkeypatch)

    assert (
        cli.main(
            [
                "channel-probe",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--ratio",
                "10",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("set_channel_probe_ratio", 1, 10.0), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned change: CH1 probe ratio 10" in out
    assert "Command: :CHANnel1:PROBe 10" in out
    assert 'System error: +0, "No error"' in out


def test_channel_probe_cli_queries_ratio_then_checks_error(monkeypatch, capsys):
    scope = _install_channel_parameter_scope(monkeypatch)

    assert (
        cli.main(
            [
                "channel-probe",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "2",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_channel_probe_ratio", 2), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH2 probe ratio" in out
    assert "Command: :CHANnel2:PROBe?" in out
    assert "Probe ratio: 10" in out


def test_channel_bandwidth_limit_cli_turns_limit_on_then_checks_error(monkeypatch, capsys):
    scope = _install_channel_parameter_scope(monkeypatch)

    assert (
        cli.main(
            [
                "channel-bandwidth-limit",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--on",
            ]
        )
        == 0
    )

    assert scope.calls == [
        "query_idn",
        ("set_channel_bandwidth_limit", 1, True),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Planned change: CH1 bandwidth limit ON" in out
    assert "Command: :CHANnel1:BWLimit ON" in out
    assert 'System error: +0, "No error"' in out


def test_channel_bandwidth_limit_cli_queries_limit_then_checks_error(monkeypatch, capsys):
    scope = _install_channel_parameter_scope(monkeypatch)

    assert (
        cli.main(
            [
                "channel-bandwidth-limit",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "2",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == [
        "query_idn",
        ("query_channel_bandwidth_limit", 2),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Planned query: CH2 bandwidth limit" in out
    assert "Command: :CHANnel2:BWLimit?" in out
    assert "Bandwidth limit: ON" in out


def test_timebase_scale_cli_sets_scale_then_checks_error(monkeypatch, capsys):
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

        def set_timebase_scale(self, seconds_per_division):
            self.calls.append(("set_timebase_scale", seconds_per_division))

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "timebase-scale",
                "--resource",
                "USB0::FAKE::INSTR",
                "--seconds-per-division",
                "0.001",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("set_timebase_scale", 0.001), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned change: timebase scale 0.001 s/div" in out
    assert "Command: :TIMebase:SCALe 0.001" in out
    assert 'System error: +0, "No error"' in out


def test_timebase_scale_cli_queries_scale_then_checks_error(monkeypatch, capsys):
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

        def query_timebase_scale(self):
            self.calls.append("query_timebase_scale")
            return 0.001

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "timebase-scale",
                "--resource",
                "USB0::FAKE::INSTR",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", "query_timebase_scale", "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: timebase scale" in out
    assert "Command: :TIMebase:SCALe?" in out
    assert "Timebase scale s/div: 0.001" in out


def test_timebase_position_cli_sets_position_then_checks_error(monkeypatch, capsys):
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

        def set_timebase_position(self, seconds):
            self.calls.append(("set_timebase_position", seconds))

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "timebase-position",
                "--resource",
                "USB0::FAKE::INSTR",
                "--seconds",
                "-0.0005",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("set_timebase_position", -0.0005), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned change: timebase position -0.0005 s" in out
    assert "Command: :TIMebase:POSition -0.0005" in out
    assert 'System error: +0, "No error"' in out


def test_timebase_position_cli_queries_position_then_checks_error(monkeypatch, capsys):
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

        def query_timebase_position(self):
            self.calls.append("query_timebase_position")
            return -0.0005

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "timebase-position",
                "--resource",
                "USB0::FAKE::INSTR",
                "--query",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", "query_timebase_position", "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: timebase position" in out
    assert "Command: :TIMebase:POSition?" in out
    assert "Timebase position s: -0.0005" in out


def test_edge_trigger_cli_configures_edge_trigger_then_checks_error(monkeypatch, capsys):
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

        def configure_edge_trigger(self, source_channel, level_volts, slope):
            self.calls.append(("configure_edge_trigger", source_channel, level_volts, slope))

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "edge-trigger",
                "--resource",
                "USB0::FAKE::INSTR",
                "--source-channel",
                "1",
                "--level",
                "0.25",
                "--slope",
                "positive",
            ]
        )
        == 0
    )

    assert scope.calls == [
        "query_idn",
        ("configure_edge_trigger", 1, 0.25, "POSitive"),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Planned change: edge trigger CH1, level 0.25 V, slope positive" in out
    assert "Command: :TRIGger:MODE EDGE" in out
    assert "Command: :TRIGger:EDGE:SOURce CHANnel1" in out
    assert "Command: :TRIGger:EDGE:LEVel 0.25" in out
    assert "Command: :TRIGger:EDGE:SLOPe POSitive" in out
    assert 'System error: +0, "No error"' in out


def test_edge_trigger_cli_queries_edge_trigger_then_checks_error(monkeypatch, capsys):
    class DummyBackend:
        backend = "backend"
        timeout = None

    class DummyState:
        source_channel = 1
        level_volts = 0.25
        slope = "positive"

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

        def query_edge_trigger(self):
            self.calls.append("query_edge_trigger")
            return DummyState()

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert cli.main(["edge-trigger", "--resource", "USB0::FAKE::INSTR", "--query"]) == 0

    assert scope.calls == ["query_idn", "query_edge_trigger", "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: edge trigger source, level, and slope" in out
    assert "Command: :TRIGger:EDGE:SOURce?" in out
    assert "Source: CH1" in out
    assert "Command: :TRIGger:EDGE:LEVel?" in out
    assert "Level V: 0.25" in out
    assert "Command: :TRIGger:EDGE:SLOPe?" in out
    assert "Slope: positive" in out


def test_edge_trigger_cli_rejects_missing_configuration_args(monkeypatch, capsys):
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

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert cli.main(["edge-trigger", "--resource", "USB0::FAKE::INSTR", "--source-channel", "1"]) == 1

    assert scope.calls == ["query_idn"]
    err = capsys.readouterr().err
    assert "requires --source-channel, --level, and --slope" in err


def test_capture_cli_writes_csv_and_metadata_then_checks_error(monkeypatch, capsys, tmp_path):
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

        def capture_waveform_byte(self, channel, points=1000):
            self.calls.append(("capture_waveform_byte", channel, points))
            preamble = WaveformPreamble(
                raw="0,0,2,1,1.0E-6,0,0,2.0E-2,-2.56,128",
                format_code=0,
                type_code=0,
                points=2,
                count=1,
                x_increment=1e-6,
                x_origin=0.0,
                x_reference=0,
                y_increment=0.02,
                y_origin=-2.56,
                y_reference=128,
            )
            return WaveformCapture(
                channel=channel,
                requested_points=points,
                format_name="BYTE",
                preamble=preamble,
                raw_samples=(128, 129),
                time_s=(0.0, 1e-6),
                voltage_v=(-2.56, -2.54),
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))
    csv_path = tmp_path / "capture.csv"

    assert (
        cli.main(
            [
                "capture",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--points",
                "10000",
                "--csv",
                str(csv_path),
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("capture_waveform_byte", 1, 10000), "query_system_error"]
    assert (tmp_path / "capture_meta.json").exists()
    assert csv_path.read_text(encoding="utf-8").splitlines()[0] == "time_s,ch1_v"
    out = capsys.readouterr().out
    assert "Planned capture: CH1, 10000 points, BYTE format" in out
    assert "Command: :WAVeform:SOURce CHANnel1" in out
    assert "Command: :WAVeform:FORMat BYTE" in out
    assert "Command: :WAVeform:POINts 10000" in out
    assert "Command: :WAVeform:PREamble?" in out
    assert "Command: :WAVeform:DATA?" in out
    assert "Actual points: 2" in out
    assert 'System error: +0, "No error"' in out


def test_capture_cli_supports_word_format(monkeypatch, capsys, tmp_path):
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

        def capture_waveform_word(self, channel, points=1000):
            self.calls.append(("capture_waveform_word", channel, points))
            preamble = WaveformPreamble(
                raw="1,0,2,1,1.0E-6,0,0,1.0E-4,0,32768",
                format_code=1,
                type_code=0,
                points=2,
                count=1,
                x_increment=1e-6,
                x_origin=0.0,
                x_reference=0,
                y_increment=0.0001,
                y_origin=0.0,
                y_reference=32768,
            )
            return WaveformCapture(
                channel=channel,
                requested_points=points,
                format_name="WORD",
                preamble=preamble,
                raw_samples=(32768, 32769),
                time_s=(0.0, 1e-6),
                voltage_v=(0.0, 0.0001),
                byte_order="MSBFirst",
                unsigned=True,
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))
    csv_path = tmp_path / "capture.csv"

    assert (
        cli.main(
            [
                "capture",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--points",
                "5000",
                "--format",
                "word",
                "--csv",
                str(csv_path),
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("capture_waveform_word", 1, 5000), "query_system_error"]
    metadata = (tmp_path / "capture_meta.json").read_text(encoding="utf-8")
    assert '"format": "WORD"' in metadata
    assert '"byte_order": "MSBFirst"' in metadata
    assert '"unsigned": true' in metadata
    out = capsys.readouterr().out
    assert "Planned capture: CH1, 5000 points, WORD format" in out
    assert "Command: :WAVeform:SOURce CHANnel1" in out
    assert "Command: :WAVeform:FORMat WORD" in out
    assert "Command: :WAVeform:BYTeorder MSBFirst" in out
    assert "Command: :WAVeform:UNSigned ON" in out
    assert "Command: :WAVeform:POINts 5000" in out
    assert "Command: :WAVeform:PREamble?" in out
    assert "Command: :WAVeform:DATA?" in out
    assert "Actual points: 2" in out
    assert 'System error: +0, "No error"' in out


def test_capture_cli_uses_timestamped_default_csv_when_omitted(monkeypatch, capsys, tmp_path):
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

        def capture_waveform_byte(self, channel, points=1000):
            self.calls.append(("capture_waveform_byte", channel, points))
            preamble = WaveformPreamble(
                raw="0,0,2,1,1.0E-6,0,0,2.0E-2,-2.56,128",
                format_code=0,
                type_code=0,
                points=2,
                count=1,
                x_increment=1e-6,
                x_origin=0.0,
                x_reference=0,
                y_increment=0.02,
                y_origin=-2.56,
                y_reference=128,
            )
            return WaveformCapture(
                channel=channel,
                requested_points=points,
                format_name="BYTE",
                preamble=preamble,
                raw_samples=(128, 129),
                time_s=(0.0, 1e-6),
                voltage_v=(-2.56, -2.54),
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    default_csv_path = tmp_path / "data" / "2026-05-12-14-30-05.csv"
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))
    monkeypatch.setattr(cli, "_default_capture_csv_path", lambda: default_csv_path)

    assert cli.main(["capture", "--resource", "USB0::FAKE::INSTR", "--channel", "1"]) == 0

    assert scope.calls == ["query_idn", ("capture_waveform_byte", 1, 1000), "query_system_error"]
    assert default_csv_path.exists()
    assert (tmp_path / "data" / "2026-05-12-14-30-05_meta.json").exists()
    assert default_csv_path.read_text(encoding="utf-8").splitlines()[0] == "time_s,ch1_v"
    out = capsys.readouterr().out
    assert f"CSV: {default_csv_path}" in out
    assert f"Metadata: {tmp_path / 'data' / '2026-05-12-14-30-05_meta.json'}" in out
    assert 'System error: +0, "No error"' in out


def test_capture_cli_reports_csv_permission_error_without_traceback(monkeypatch, capsys, tmp_path):
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

        def capture_waveform_byte(self, channel, points=1000):
            self.calls.append(("capture_waveform_byte", channel, points))
            preamble = WaveformPreamble(
                raw="0,0,2,1,1.0E-6,0,0,2.0E-2,-2.56,128",
                format_code=0,
                type_code=0,
                points=2,
                count=1,
                x_increment=1e-6,
                x_origin=0.0,
                x_reference=0,
                y_increment=0.02,
                y_origin=-2.56,
                y_reference=128,
            )
            return WaveformCapture(
                channel=channel,
                requested_points=points,
                format_name="BYTE",
                preamble=preamble,
                raw_samples=(128, 129),
                time_s=(0.0, 1e-6),
                voltage_v=(-2.56, -2.54),
            )

    scope = DummyScope()
    csv_path = tmp_path / "capture.csv"

    def fake_write_waveform_csv(capture, path):
        del capture
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))
    monkeypatch.setattr(cli, "write_waveform_csv", fake_write_waveform_csv)

    assert (
        cli.main(
            [
                "capture",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--csv",
                str(csv_path),
            ]
        )
        == 1
    )

    assert scope.calls == ["query_idn", ("capture_waveform_byte", 1, 1000)]
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "could not write waveform CSV file" in captured.err
    assert str(csv_path) in captured.err
    assert "Permission denied" in captured.err
    assert "file may be open in another program" in captured.err
    assert "Excel" in captured.err


def test_capture_cli_rejects_channel_above_detected_capabilities(monkeypatch, capsys, tmp_path):
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

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "capture",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "3",
                "--csv",
                str(tmp_path / "capture.csv"),
            ]
        )
        == 1
    )

    assert scope.calls == ["query_idn"]
    err = capsys.readouterr().err
    assert "channel 3 is not available" in err


def test_screenshot_cli_writes_png_then_checks_error(monkeypatch, capsys, tmp_path):
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

        def capture_screenshot_png(self, *, background="black"):
            self.calls.append(("capture_screenshot_png", background))
            return ScreenshotCapture(
                format_name="PNG",
                palette="COLor",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                background=background,
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    output_path = tmp_path / "screen.png"
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "screenshot",
                "--resource",
                "USB0::FAKE::INSTR",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("capture_screenshot_png", "black"), "query_system_error"]
    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    out = capsys.readouterr().out
    assert "Resource: USB0::FAKE::INSTR" in out
    assert "Timeout ms: 2000" in out
    assert "Planned capture: current screen PNG image with black background" in out
    assert "Screenshot timeout ms: 10000 (temporary)" in out
    assert "Command: :HARDcopy:INKSaver OFF" in out
    assert "Command: :DISPlay:DATA? PNG, COLor" in out
    assert "Format: PNG" in out
    assert "Palette: COLor" in out
    assert "Background: black" in out
    assert "Bytes: 16" in out
    assert f"PNG: {output_path}" in out
    assert 'System error: +0, "No error"' in out


def test_screenshot_cli_uses_timestamped_default_output_when_omitted(monkeypatch, capsys, tmp_path):
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

        def capture_screenshot_png(self, *, background="black"):
            self.calls.append(("capture_screenshot_png", background))
            return ScreenshotCapture(
                format_name="PNG",
                palette="COLor",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                background=background,
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    default_output_path = tmp_path / "data" / "2026-05-13-10-20-30.png"
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))
    monkeypatch.setattr(cli, "_default_screenshot_path", lambda: default_output_path)

    assert cli.main(["screenshot", "--resource", "USB0::FAKE::INSTR"]) == 0

    assert scope.calls == ["query_idn", ("capture_screenshot_png", "black"), "query_system_error"]
    assert default_output_path.exists()
    out = capsys.readouterr().out
    assert f"PNG: {default_output_path}" in out


def test_screenshot_cli_supports_white_background(monkeypatch, capsys, tmp_path):
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

        def capture_screenshot_png(self, *, background="black"):
            self.calls.append(("capture_screenshot_png", background))
            return ScreenshotCapture(
                format_name="PNG",
                palette="COLor",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                background=background,
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    output_path = tmp_path / "screen.png"
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "screenshot",
                "--resource",
                "USB0::FAKE::INSTR",
                "--output",
                str(output_path),
                "--background",
                "white",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("capture_screenshot_png", "white"), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned capture: current screen PNG image with white background" in out
    assert "Command: :HARDcopy:INKSaver ON" in out
    assert "Background: white" in out


def test_default_screenshot_path_matches_capture_timestamp_format():
    assert cli._default_screenshot_path(datetime(2026, 5, 13, 10, 20, 30)) == (
        Path("data") / "2026-05-13-10-20-30.png"
    )


def test_screenshot_cli_reports_png_permission_error_without_traceback(monkeypatch, capsys, tmp_path):
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

        def capture_screenshot_png(self, *, background="black"):
            self.calls.append(("capture_screenshot_png", background))
            return ScreenshotCapture(
                format_name="PNG",
                palette="COLor",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                background=background,
            )

    scope = DummyScope()
    output_path = tmp_path / "screen.png"

    def fake_write_screenshot_png(capture, path):
        del capture
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))
    monkeypatch.setattr(cli, "write_screenshot_png", fake_write_screenshot_png)

    assert (
        cli.main(
            [
                "screenshot",
                "--resource",
                "USB0::FAKE::INSTR",
                "--output",
                str(output_path),
            ]
        )
        == 1
    )

    assert scope.calls == ["query_idn", ("capture_screenshot_png", "black")]
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "could not write screenshot PNG file" in captured.err
    assert str(output_path) in captured.err
    assert "Permission denied" in captured.err
    assert "file may be open in another program" in captured.err


@pytest.mark.parametrize(
    (
        "requested_item",
        "normalized_item",
        "value",
        "raw_value",
        "unit",
        "expected_command",
        "expected_value_line",
    ),
    [
        (
            "amplitude",
            "amplitude",
            1.2,
            "1.20E+0",
            "V",
            ":MEASure:VAMPlitude? CHANnel1",
            "Value V: 1.2",
        ),
        (
            "pwidth",
            "positive_width",
            0.000002,
            "2.00E-6",
            "s",
            ":MEASure:PWIDth? CHANnel1",
            "Value s: 2e-06",
        ),
        (
            "duty-cycle",
            "duty_cycle",
            48.0,
            "4.80E+1",
            "%",
            ":MEASure:DUTYcycle? CHANnel1",
            "Value %: 48",
        ),
    ],
)
def test_measure_cli_queries_new_items_then_checks_error(
    monkeypatch,
    capsys,
    requested_item,
    normalized_item,
    value,
    raw_value,
    unit,
    expected_command,
    expected_value_line,
):
    scope = _install_measurement_scope(monkeypatch, value, raw_value, unit)

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                requested_item,
            ]
        )
        == 0
    )

    assert scope.calls == [
        "query_idn",
        ("query_measurement", 1, normalized_item),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert f"Planned query: CH1 {normalized_item} measurement" in out
    assert f"Command: {expected_command}" in out
    assert f"Measurement: {normalized_item}" in out
    assert expected_value_line in out
    assert f"Raw response: {raw_value}" in out
    assert 'System error: +0, "No error"' in out


@pytest.mark.parametrize(
    ("requested_item", "normalized_item", "unit", "expected_command"),
    [
        ("overshoot", "overshoot", "%", ":MEASure:OVERshoot? CHANnel1"),
        ("positive_width", "positive_width", "s", ":MEASure:PWIDth? CHANnel1"),
    ],
)
def test_measure_cli_reports_invalid_sentinel_for_new_items(
    monkeypatch, capsys, requested_item, normalized_item, unit, expected_command
):
    scope = _install_measurement_scope(
        monkeypatch,
        None,
        "9.9E+37",
        unit,
        valid=False,
        reason="invalid measurement sentinel",
    )

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                requested_item,
            ]
        )
        == 1
    )

    assert scope.calls == [
        "query_idn",
        ("query_measurement", 1, normalized_item),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert f"Command: {expected_command}" in out
    assert f"Measurement: {normalized_item}" in out
    assert "Valid: false" in out
    assert "Value: unavailable" in out
    assert "Raw response: 9.9E+37" in out
    assert "Reason: invalid measurement sentinel" in out
    assert 'System error: +0, "No error"' in out


def test_measure_cli_queries_vpp_then_checks_error(monkeypatch, capsys):
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

        def query_measurement(self, channel, item):
            self.calls.append(("query_measurement", channel, item))
            return MeasurementResult(
                item=item,
                channel=channel,
                value=0.5,
                raw_value="5.0E-1",
                valid=True,
                unit="V",
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                "vpp",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_measurement", 1, "vpp"), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH1 vpp measurement" in out
    assert "Command: :MEASure:VPP? CHANnel1" in out
    assert "Measurement: vpp" in out
    assert "Channel: 1" in out
    assert "Valid: true" in out
    assert "Value V: 0.5" in out
    assert "Raw response: 5.0E-1" in out
    assert 'System error: +0, "No error"' in out


def test_measure_cli_queries_vrms_then_checks_error(monkeypatch, capsys):
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

        def query_measurement(self, channel, item):
            self.calls.append(("query_measurement", channel, item))
            return MeasurementResult(
                item=item,
                channel=channel,
                value=0.707,
                raw_value="7.07E-1",
                valid=True,
                unit="V",
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                "vrms",
            ]
        )
        == 0
    )

    assert scope.calls == ["query_idn", ("query_measurement", 1, "vrms"), "query_system_error"]
    out = capsys.readouterr().out
    assert "Planned query: CH1 vrms measurement" in out
    assert "Command: :MEASure:VRMS? DISPlay,DC,CHANnel1" in out
    assert "Measurement: vrms" in out
    assert "Value V: 0.707" in out
    assert "Raw response: 7.07E-1" in out
    assert 'System error: +0, "No error"' in out


def test_measure_cli_accepts_risetime_alias_then_checks_error(monkeypatch, capsys):
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

        def query_measurement(self, channel, item):
            self.calls.append(("query_measurement", channel, item))
            return MeasurementResult(
                item=item,
                channel=channel,
                value=0.000001,
                raw_value="1.00E-6",
                valid=True,
                unit="s",
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                "risetime",
            ]
        )
        == 0
    )

    assert scope.calls == [
        "query_idn",
        ("query_measurement", 1, "rise_time"),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Planned query: CH1 rise_time measurement" in out
    assert "Command: :MEASure:RISetime? CHANnel1" in out
    assert "Measurement: rise_time" in out
    assert "Value s: 1e-06" in out
    assert "Raw response: 1.00E-6" in out
    assert 'System error: +0, "No error"' in out


def test_measure_cli_accepts_freq_alias(monkeypatch, capsys):
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

        def query_measurement(self, channel, item):
            self.calls.append(("query_measurement", channel, item))
            return MeasurementResult(
                item=item,
                channel=channel,
                value=1000.0,
                raw_value="1.0E+3",
                valid=True,
                unit="Hz",
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                "freq",
            ]
        )
        == 0
    )

    assert scope.calls == [
        "query_idn",
        ("query_measurement", 1, "frequency"),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Planned query: CH1 frequency measurement" in out
    assert "Command: :MEASure:FREQuency? CHANnel1" in out
    assert "Measurement: frequency" in out


def test_measure_cli_reports_invalid_sentinel_without_losing_raw(monkeypatch, capsys):
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

        def query_measurement(self, channel, item):
            self.calls.append(("query_measurement", channel, item))
            return MeasurementResult(
                item=item,
                channel=channel,
                value=None,
                raw_value="9.9E+37",
                valid=False,
                unit="Hz",
                reason="invalid measurement sentinel",
            )

        def query_system_error(self):
            self.calls.append("query_system_error")
            return SystemErrorEntry(code=0, message="No error", raw='+0,"No error"')

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "1",
                "--item",
                "frequency",
            ]
        )
        == 1
    )

    assert scope.calls == [
        "query_idn",
        ("query_measurement", 1, "frequency"),
        "query_system_error",
    ]
    out = capsys.readouterr().out
    assert "Command: :MEASure:FREQuency? CHANnel1" in out
    assert "Measurement: frequency" in out
    assert "Valid: false" in out
    assert "Value: unavailable" in out
    assert "Raw response: 9.9E+37" in out
    assert "Reason: invalid measurement sentinel" in out
    assert 'System error: +0, "No error"' in out


def test_measure_cli_rejects_channel_above_detected_capabilities(monkeypatch, capsys):
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

        def query_measurement(self, channel, item):
            self.calls.append(("query_measurement", channel, item))
            raise AssertionError("measurement query should not be sent")

    scope = DummyScope()
    monkeypatch.setattr(cli.KeysightScope, "open", staticmethod(lambda resource, visa_library=None: scope))

    assert (
        cli.main(
            [
                "measure",
                "--resource",
                "USB0::FAKE::INSTR",
                "--channel",
                "3",
                "--item",
                "vpp",
            ]
        )
        == 1
    )

    assert scope.calls == ["query_idn"]
    err = capsys.readouterr().err
    assert "channel 3 is not available" in err
