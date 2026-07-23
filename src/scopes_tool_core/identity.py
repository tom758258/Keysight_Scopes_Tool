"""Canonical vendor and physical model identities."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import UnsupportedModelError


@dataclass(frozen=True)
class VendorInfo:
    """Canonical identity for an oscilloscope vendor."""

    vendor_id: str
    display_name: str
    canonical_manufacturer: str
    manufacturer_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhysicalModelInfo:
    """Canonical identity for a physical oscilloscope model."""

    model_id: str
    vendor_id: str
    canonical_model: str
    display_name: str
    series: str
    model_aliases: tuple[str, ...] = ()


VENDOR_REGISTRY = (
    VendorInfo(
        vendor_id="keysight",
        display_name="Keysight",
        canonical_manufacturer="KEYSIGHT TECHNOLOGIES",
        manufacturer_aliases=(
            "KEYSIGHT",
            "AGILENT TECHNOLOGIES",
            "AGILENT",
        ),
    ),
)

PHYSICAL_MODEL_REGISTRY = (
    PhysicalModelInfo(
        model_id="keysight-dsox2004a",
        vendor_id="keysight",
        canonical_model="DSOX2004A",
        display_name="Keysight DSO-X 2004A",
        series="2000X",
    ),
    PhysicalModelInfo(
        model_id="keysight-dsox3024a",
        vendor_id="keysight",
        canonical_model="DSOX3024A",
        display_name="Keysight DSO-X 3024A",
        series="3000X",
    ),
    PhysicalModelInfo(
        model_id="keysight-dsox4024a",
        vendor_id="keysight",
        canonical_model="DSOX4024A",
        display_name="Keysight DSO-X 4024A",
        series="4000X",
    ),
    PhysicalModelInfo(
        model_id="keysight-dsox4034a",
        vendor_id="keysight",
        canonical_model="DSOX4034A",
        display_name="Keysight DSO-X 4034A",
        series="4000X",
    ),
)

_MODEL_KEY_RE = re.compile(r"[^A-Z0-9]")


def _normalize_manufacturer_key(manufacturer: str) -> str:
    return " ".join(manufacturer.strip().upper().split())


def _normalize_model_key(model: str) -> str:
    return _MODEL_KEY_RE.sub("", model.strip().upper())


def _build_vendor_index() -> dict[str, VendorInfo]:
    index: dict[str, VendorInfo] = {}
    for vendor in VENDOR_REGISTRY:
        for manufacturer in (
            vendor.canonical_manufacturer,
            *vendor.manufacturer_aliases,
        ):
            key = _normalize_manufacturer_key(manufacturer)
            existing = index.get(key)
            if existing is not None and existing != vendor:
                raise RuntimeError(f"Ambiguous manufacturer identity: {manufacturer}")
            index[key] = vendor
    return index


def _build_model_index() -> dict[str, PhysicalModelInfo]:
    vendor_ids = {vendor.vendor_id for vendor in VENDOR_REGISTRY}
    index: dict[str, PhysicalModelInfo] = {}
    for model in PHYSICAL_MODEL_REGISTRY:
        if model.vendor_id not in vendor_ids:
            raise RuntimeError(
                f"Physical model {model.model_id} references unknown vendor "
                f"{model.vendor_id}"
            )
        for model_name in (model.canonical_model, *model.model_aliases):
            key = _normalize_model_key(model_name)
            existing = index.get(key)
            if existing is not None and existing != model:
                raise RuntimeError(f"Ambiguous physical model identity: {model_name}")
            index[key] = model
    return index


_VENDOR_BY_MANUFACTURER = _build_vendor_index()
_PHYSICAL_MODEL_BY_MODEL = _build_model_index()


def resolve_physical_model_identity(
    manufacturer: str,
    model: str,
) -> PhysicalModelInfo:
    """Resolve manufacturer and model strings to a canonical physical model."""

    vendor = _VENDOR_BY_MANUFACTURER.get(
        _normalize_manufacturer_key(manufacturer)
    )
    if vendor is None:
        raise UnsupportedModelError(
            f"Unsupported oscilloscope manufacturer: {manufacturer}"
        )

    physical_model = _PHYSICAL_MODEL_BY_MODEL.get(_normalize_model_key(model))
    if physical_model is None:
        raise UnsupportedModelError(
            f"Unsupported physical oscilloscope model: {model}"
        )
    if physical_model.vendor_id != vendor.vendor_id:
        raise UnsupportedModelError(
            "Oscilloscope manufacturer and model identities do not match: "
            f"{manufacturer}, {model}"
        )
    return physical_model


def canonical_physical_model_id(manufacturer: str, model: str) -> str:
    """Return the canonical physical model ID for an instrument identity."""

    return resolve_physical_model_identity(manufacturer, model).model_id
