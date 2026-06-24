import sys
from types import SimpleNamespace

import pytest

from keysight_scope_core.errors import VisaBackendError
from keysight_scope_core.visa_backend import VisaBackend, list_visa_resources


class _FakeResource:
    def __init__(self):
        self.timeout = 2000
        self.closed = False
        self.history = []
        self.binary_kwargs = []

    def write(self, command):
        self.history.append(("write", command))

    def query(self, command):
        self.history.append(("query", command))
        return " response \n"

    def read_raw(self):
        self.history.append(("read_raw",))
        return bytearray(b"raw-bytes")

    def query_binary_values(self, command, **kwargs):
        self.history.append(("query_binary_values", command))
        self.binary_kwargs.append(kwargs)
        return [1, 2, 3]

    def close(self):
        self.closed = True


class _FakeResourceManager:
    def __init__(self, resources=("USB0::FAKE::INSTR",), opened_resource=None):
        self.resources = resources
        self.opened_resource = opened_resource or _FakeResource()
        self.visalib = "fake visa library"
        self.opened_names = []
        self.closed = False

    def list_resources(self):
        return self.resources

    def open_resource(self, resource_name):
        self.opened_names.append(resource_name)
        return self.opened_resource

    def close(self):
        self.closed = True


def _install_fake_pyvisa(monkeypatch, factory):
    calls = []

    def resource_manager(*args):
        calls.append(args)
        return factory(*args)

    monkeypatch.setitem(
        sys.modules,
        "pyvisa",
        SimpleNamespace(ResourceManager=resource_manager),
    )
    return calls


def test_list_visa_resources_uses_pyvisa_resource_manager_and_closes(monkeypatch):
    manager = _FakeResourceManager(resources=("USB0::FAKE::INSTR", 123))
    calls = _install_fake_pyvisa(monkeypatch, lambda: manager)

    listing = list_visa_resources()

    assert listing.resources == ("USB0::FAKE::INSTR", "123")
    assert listing.backend == "fake visa library"
    assert calls == [()]
    assert manager.closed is True


def test_list_visa_resources_wraps_list_failures_and_closes(monkeypatch):
    class FailingResourceManager(_FakeResourceManager):
        def list_resources(self):
            raise RuntimeError("VISA unavailable")

    manager = FailingResourceManager()
    _install_fake_pyvisa(monkeypatch, lambda visa_library: manager)

    with pytest.raises(VisaBackendError) as excinfo:
        list_visa_resources("@sim")

    assert "Failed to list VISA resources: VISA unavailable" in str(excinfo.value)
    assert manager.closed is True


def test_visa_backend_opens_resource_delegates_io_and_closes(monkeypatch):
    resource = _FakeResource()
    manager = _FakeResourceManager(opened_resource=resource)
    calls = _install_fake_pyvisa(monkeypatch, lambda visa_library: manager)

    backend = VisaBackend("USB0::FAKE::INSTR", visa_library="@sim")

    assert backend.resource_name == "USB0::FAKE::INSTR"
    assert backend.backend == "fake visa library"
    assert backend.timeout == 2000
    assert calls == [("@sim",)]
    assert manager.opened_names == ["USB0::FAKE::INSTR"]

    backend.set_timeout(5000)
    backend.write(":RUN")
    response = backend.query("*IDN?")
    raw = backend.read_raw()
    binary = backend.query_binary_values(":WAVeform:DATA?", datatype="B")

    assert resource.timeout == 5000
    assert response == " response \n"
    assert raw == b"raw-bytes"
    assert binary == [1, 2, 3]
    assert resource.binary_kwargs == [{"datatype": "B"}]
    assert resource.history == [
        ("write", ":RUN"),
        ("query", "*IDN?"),
        ("read_raw",),
        ("query_binary_values", ":WAVeform:DATA?"),
    ]

    backend.close()
    backend.close()

    assert resource.closed is True
    assert manager.closed is True
    with pytest.raises(VisaBackendError) as excinfo:
        backend.query("*IDN?")
    assert "VISA backend is closed" in str(excinfo.value)


def test_visa_backend_wraps_resource_manager_creation_failure(monkeypatch):
    def fail_resource_manager():
        raise RuntimeError("no backend")

    monkeypatch.setitem(
        sys.modules,
        "pyvisa",
        SimpleNamespace(ResourceManager=fail_resource_manager),
    )

    with pytest.raises(VisaBackendError) as excinfo:
        VisaBackend("USB0::FAKE::INSTR")

    assert "Failed to create PyVISA ResourceManager: no backend" in str(excinfo.value)


def test_visa_backend_wraps_open_failure_and_closes_manager(monkeypatch):
    class FailingOpenResourceManager(_FakeResourceManager):
        def open_resource(self, resource_name):
            self.opened_names.append(resource_name)
            raise RuntimeError("device busy")

    manager = FailingOpenResourceManager()
    _install_fake_pyvisa(monkeypatch, lambda: manager)

    with pytest.raises(VisaBackendError) as excinfo:
        VisaBackend("USB0::FAKE::INSTR")

    assert "Failed to open VISA resource USB0::FAKE::INSTR: device busy" in str(
        excinfo.value
    )
    assert manager.opened_names == ["USB0::FAKE::INSTR"]
    assert manager.closed is True


@pytest.mark.parametrize(
    ("operation", "expected_message"),
    [
        (lambda backend: backend.set_timeout(1000), "Failed to set VISA timeout to 1000"),
        (lambda backend: backend.write(":STOP"), "VISA write failed for ':STOP'"),
        (lambda backend: backend.query("*IDN?"), "VISA query failed for '*IDN?'"),
        (lambda backend: backend.read_raw(), "VISA raw read failed"),
        (
            lambda backend: backend.query_binary_values(":WAVeform:DATA?"),
            "VISA binary query failed for ':WAVeform:DATA?'",
        ),
    ],
)
def test_visa_backend_wraps_session_operation_failures(
    monkeypatch, operation, expected_message
):
    class FailingResource(_FakeResource):
        def __init__(self):
            self.closed = False

        @property
        def timeout(self):
            return 2000

        @timeout.setter
        def timeout(self, value):
            raise RuntimeError("timeout failed")

        def write(self, command):
            raise RuntimeError("write failed")

        def query(self, command):
            raise RuntimeError("query failed")

        def read_raw(self):
            raise RuntimeError("read failed")

        def query_binary_values(self, command, **kwargs):
            raise RuntimeError("binary failed")

    manager = _FakeResourceManager(opened_resource=FailingResource())
    _install_fake_pyvisa(monkeypatch, lambda: manager)
    backend = VisaBackend("USB0::FAKE::INSTR")

    with pytest.raises(VisaBackendError) as excinfo:
        operation(backend)

    assert expected_message in str(excinfo.value)
