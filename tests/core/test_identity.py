import re

import pytest
import scopes_tool_core.identity as identity_module

from scopes_tool_core import (
    PHYSICAL_MODEL_REGISTRY,
    VENDOR_REGISTRY,
    PhysicalModelInfo,
    VendorInfo,
    canonical_physical_model_id,
    resolve_physical_model_identity,
)
from scopes_tool_core.errors import UnsupportedModelError
from scopes_tool_core.idn import parse_idn


@pytest.mark.parametrize(
    ("model", "model_id", "series"),
    [
        ("DSOX2004A", "keysight-dsox2004a", "2000X"),
        ("DSOX3024A", "keysight-dsox3024a", "3000X"),
        ("DSOX4024A", "keysight-dsox4024a", "4000X"),
        ("DSOX4034A", "keysight-dsox4034a", "4000X"),
    ],
)
def test_resolves_registered_physical_models(model, model_id, series):
    identity = resolve_physical_model_identity("KEYSIGHT TECHNOLOGIES", model)

    assert identity.model_id == model_id
    assert identity.vendor_id == "keysight"
    assert identity.canonical_model == model
    assert identity.series == series


@pytest.mark.parametrize(
    "manufacturer",
    [
        "KEYSIGHT TECHNOLOGIES",
        "KEYSIGHT",
        "AGILENT TECHNOLOGIES",
        "AGILENT",
    ],
)
def test_resolves_keysight_manufacturer_aliases(manufacturer):
    assert (
        canonical_physical_model_id(manufacturer, "DSOX4024A")
        == "keysight-dsox4024a"
    )


@pytest.mark.parametrize("model", ["DSOX4024A", "DSO-X 4024A", "DSO-X-4024A"])
def test_resolves_model_punctuation_and_spacing(model):
    assert (
        canonical_physical_model_id("KEYSIGHT", model)
        == "keysight-dsox4024a"
    )


def test_manufacturer_matching_ignores_case_and_outer_whitespace():
    assert (
        canonical_physical_model_id("  keysight technologies  ", "DSOX4024A")
        == "keysight-dsox4024a"
    )


def test_rejects_unknown_manufacturer():
    with pytest.raises(UnsupportedModelError):
        resolve_physical_model_identity("UNKNOWN VENDOR", "UNKNOWN1000")


def test_rejects_unknown_model():
    with pytest.raises(UnsupportedModelError):
        resolve_physical_model_identity("KEYSIGHT", "DSOX9999A")


def test_parse_idn_keeps_unknown_four_field_identity():
    idn = parse_idn("UNKNOWN VENDOR,UNKNOWN1000,SERIAL1,1.0")

    assert idn.vendor == "UNKNOWN VENDOR"
    assert idn.model == "UNKNOWN1000"
    with pytest.raises(UnsupportedModelError):
        _ = idn.physical_model


def test_known_idn_exposes_canonical_identity():
    idn = parse_idn("KEYSIGHT TECHNOLOGIES,DSO-X 4024A,SERIAL1,1.0")

    assert idn.model_id == "keysight-dsox4024a"
    assert idn.physical_model.canonical_model == "DSOX4024A"


def test_public_identity_types_are_exported():
    assert isinstance(VENDOR_REGISTRY[0], VendorInfo)
    assert isinstance(PHYSICAL_MODEL_REGISTRY[0], PhysicalModelInfo)


def test_registry_ids_and_canonical_lookup_keys_are_unambiguous():
    vendor_ids = [vendor.vendor_id for vendor in VENDOR_REGISTRY]
    model_ids = [model.model_id for model in PHYSICAL_MODEL_REGISTRY]
    manufacturer_keys = [
        " ".join(name.strip().upper().split())
        for vendor in VENDOR_REGISTRY
        for name in (
            vendor.canonical_manufacturer,
            *vendor.manufacturer_aliases,
        )
    ]
    model_keys = [
        (
            model.vendor_id,
            re.sub(r"[^A-Z0-9]", "", model.canonical_model.strip().upper()),
        )
        for model in PHYSICAL_MODEL_REGISTRY
    ]

    assert len(vendor_ids) == len(set(vendor_ids))
    assert len(model_ids) == len(set(model_ids))
    assert len(manufacturer_keys) == len(set(manufacturer_keys))
    assert len(model_keys) == len(set(model_keys))
    assert {model.vendor_id for model in PHYSICAL_MODEL_REGISTRY} <= set(vendor_ids)


def _synthetic_vendors():
    return (
        VendorInfo(
            vendor_id="vendor-a",
            display_name="Vendor A",
            canonical_manufacturer="VENDOR A",
        ),
        VendorInfo(
            vendor_id="vendor-b",
            display_name="Vendor B",
            canonical_manufacturer="VENDOR B",
        ),
    )


def _synthetic_model(model_id, vendor_id, canonical_model, *, aliases=()):
    return PhysicalModelInfo(
        model_id=model_id,
        vendor_id=vendor_id,
        canonical_model=canonical_model,
        display_name=model_id,
        series="SYNTHETIC",
        capability_profile_id="synthetic-profile",
        model_aliases=aliases,
    )


def test_different_vendors_can_share_normalized_model_spelling():
    vendors = _synthetic_vendors()
    models = (
        _synthetic_model("vendor-a-model100", "vendor-a", "MODEL100"),
        _synthetic_model("vendor-b-model100", "vendor-b", "MODEL100"),
    )

    index = identity_module._build_model_index(vendors, models)

    assert index[("vendor-a", "MODEL100")] == models[0]
    assert index[("vendor-b", "MODEL100")] == models[1]


def test_same_vendor_rejects_normalized_model_conflict():
    vendors = _synthetic_vendors()
    models = (
        _synthetic_model("vendor-a-model100", "vendor-a", "MODEL100"),
        _synthetic_model(
            "vendor-a-other",
            "vendor-a",
            "OTHER",
            aliases=("MODEL-100",),
        ),
    )

    with pytest.raises(RuntimeError, match="Ambiguous physical model identity"):
        identity_module._build_model_index(vendors, models)


def test_resolver_uses_manufacturer_to_select_shared_model(monkeypatch):
    vendors = _synthetic_vendors()
    models = (
        _synthetic_model("vendor-a-model100", "vendor-a", "MODEL100"),
        _synthetic_model("vendor-b-model100", "vendor-b", "MODEL100"),
    )
    monkeypatch.setattr(
        identity_module,
        "_VENDOR_BY_MANUFACTURER",
        identity_module._build_vendor_index(vendors),
    )
    monkeypatch.setattr(
        identity_module,
        "_PHYSICAL_MODEL_BY_VENDOR_AND_MODEL",
        identity_module._build_model_index(vendors, models),
    )

    assert resolve_physical_model_identity("VENDOR A", "MODEL100") == models[0]
    assert resolve_physical_model_identity("VENDOR B", "MODEL100") == models[1]


def test_known_vendor_rejects_other_vendor_model(monkeypatch):
    vendors = _synthetic_vendors()
    models = (
        _synthetic_model("vendor-a-model100", "vendor-a", "MODEL100"),
        _synthetic_model("vendor-b-model200", "vendor-b", "MODEL200"),
    )
    monkeypatch.setattr(
        identity_module,
        "_VENDOR_BY_MANUFACTURER",
        identity_module._build_vendor_index(vendors),
    )
    monkeypatch.setattr(
        identity_module,
        "_PHYSICAL_MODEL_BY_VENDOR_AND_MODEL",
        identity_module._build_model_index(vendors, models),
    )

    with pytest.raises(UnsupportedModelError):
        resolve_physical_model_identity("VENDOR A", "MODEL200")
