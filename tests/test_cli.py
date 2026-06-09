from keysight_scope import cli
from keysight_scope.capabilities import capabilities_for_model
from keysight_scope.idn import parse_idn
from keysight_scope.visa_backend import VisaResourceListing


def test_list_cli_prints_backend_and_resources(monkeypatch, capsys):
    def fake_list_visa_resources(visa_library=None):
        assert visa_library is None
        return VisaResourceListing(
            resources=("USB0::0x2A8D::FAKE::INSTR",),
            backend="Test VISA backend",
        )

    monkeypatch.setattr(cli, "list_visa_resources", fake_list_visa_resources)

    assert cli.main(["list"]) == 0

    out = capsys.readouterr().out
    assert "PyVISA backend: Test VISA backend" in out
    assert "USB0::0x2A8D::FAKE::INSTR" in out


def test_list_cli_prints_empty_resources(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_visa_resources",
        lambda visa_library=None: VisaResourceListing(resources=(), backend="backend"),
    )

    assert cli.main(["list"]) == 0

    assert "<none>" in capsys.readouterr().out


def test_idn_cli_queries_scope(monkeypatch, capsys):
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

    assert cli.main(["idn", "--resource", "USB0::FAKE::INSTR"]) == 0

    out = capsys.readouterr().out
    assert "Model: DSOX4024A" in out
    assert "Series: 4000X" in out
    assert "Analog channels: 4" in out


def test_idn_cli_uses_environment_resource(monkeypatch, capsys):
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

    assert cli.main(["idn"]) == 0

    out = capsys.readouterr().out
    assert "Resource: USB0::ENV::INSTR" in out
    assert "Series: unknown" in out


def test_idn_cli_requires_resource(capsys):
    assert cli.main(["idn"]) == 2

    err = capsys.readouterr().err
    assert "--resource is required" in err
