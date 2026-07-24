import pytest

from scopes_tool_core.capabilities import capabilities_for_model_id
from scopes_tool_core.drivers import driver_for_physical_model
from scopes_tool_core.identity import (
    PHYSICAL_MODEL_REGISTRY,
    VENDOR_REGISTRY,
)
from scopes_tool_core.idn import parse_idn
from scopes_tool_core.simulator_backend import SimulatorBackend


@pytest.mark.parametrize(
    "physical_model",
    PHYSICAL_MODEL_REGISTRY,
    ids=lambda model: model.model_id,
)
def test_registered_physical_model_is_consistent_across_core_layers(
    physical_model,
):
    vendor_ids = {vendor.vendor_id for vendor in VENDOR_REGISTRY}

    assert physical_model.vendor_id in vendor_ids
    assert (
        capabilities_for_model_id(physical_model.model_id).series
        == physical_model.series
    )
    driver_for_physical_model(physical_model)

    backend = SimulatorBackend(physical_model_id=physical_model.model_id)
    simulated_idn = parse_idn(backend.query("*IDN?"))

    assert simulated_idn.model_id == physical_model.model_id
