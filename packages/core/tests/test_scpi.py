import logging

import pytest

from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient


def test_scpi_query_strips_response_and_logs(caplog):
    backend = FakeBackend(responses={"*IDN?": "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,02.50\n"})
    client = SCPIClient(backend)

    with caplog.at_level(logging.DEBUG, logger="keysight_scope_core.scpi"):
        response = client.query("*IDN?")

    assert response == "KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,02.50"
    assert backend.history == ["*IDN?"]
    assert "SCPI >> *IDN?" in caplog.text
    assert "SCPI << KEYSIGHT TECHNOLOGIES,DSOX4024A,MY1,02.50" in caplog.text


def test_scpi_rejects_empty_command():
    client = SCPIClient(FakeBackend())

    with pytest.raises(ValueError):
        client.query(" ")
