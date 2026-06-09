from keysight_scope.fake_backend import FakeBackend
from keysight_scope.scope import KeysightScope


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
