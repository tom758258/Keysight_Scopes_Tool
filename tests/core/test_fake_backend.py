import pytest

from scopes_tool_core.errors import BackendClosedError
from scopes_tool_core.fake_backend import FakeBackend, FakeBackendError


def test_fake_backend_records_write_and_query_order():
    backend = FakeBackend(responses={"*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,02.50"})

    backend.write(":WAVeform:SOURce CHANnel1")
    response = backend.query("*IDN?")

    assert response == "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,02.50"
    assert backend.history == [":WAVeform:SOURce CHANnel1", "*IDN?"]


def test_fake_backend_requires_configured_response():
    backend = FakeBackend(responses={})

    with pytest.raises(FakeBackendError):
        backend.query("*IDN?")


def test_fake_backend_rejects_use_after_close():
    backend = FakeBackend()
    backend.close()

    with pytest.raises(BackendClosedError):
        backend.query("*IDN?")
