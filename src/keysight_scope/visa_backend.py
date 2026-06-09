"""Low-level PyVISA backend helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .errors import VisaBackendError


@dataclass(frozen=True)
class VisaResourceListing:
    """Visible VISA resources and selected backend description."""

    resources: tuple[str, ...]
    backend: str


def list_visa_resources(visa_library: str | None = None) -> VisaResourceListing:
    """List VISA resources using PyVISA's selected backend."""

    resource_manager = _create_resource_manager(visa_library)
    try:
        resources = tuple(str(resource) for resource in resource_manager.list_resources())
        backend = _describe_backend(resource_manager)
        return VisaResourceListing(resources=resources, backend=backend)
    except Exception as exc:  # pragma: no cover - depends on installed VISA stack
        raise VisaBackendError(f"Failed to list VISA resources: {exc}") from exc
    finally:
        _close_quietly(resource_manager)


class VisaBackend:
    """Low-level PyVISA session wrapper."""

    def __init__(self, resource_name: str, visa_library: str | None = None) -> None:
        self.resource_name = resource_name
        self._resource_manager = _create_resource_manager(visa_library)
        self.backend = _describe_backend(self._resource_manager)
        self._closed = False
        try:
            self._resource = self._resource_manager.open_resource(resource_name)
        except Exception as exc:  # pragma: no cover - depends on installed VISA stack
            _close_quietly(self._resource_manager)
            raise VisaBackendError(f"Failed to open VISA resource {resource_name}: {exc}") from exc

    @property
    def timeout(self) -> int | None:
        """Return the backend timeout in milliseconds without changing it."""

        return getattr(self._resource, "timeout", None)

    def write(self, command: str) -> None:
        """Write one raw command to the VISA resource."""

        self._ensure_open()
        try:
            self._resource.write(command)
        except Exception as exc:  # pragma: no cover - depends on installed VISA stack
            raise VisaBackendError(f"VISA write failed for {command!r}: {exc}") from exc

    def query(self, command: str) -> str:
        """Write one raw query and return its response."""

        self._ensure_open()
        try:
            return str(self._resource.query(command))
        except Exception as exc:  # pragma: no cover - depends on installed VISA stack
            raise VisaBackendError(f"VISA query failed for {command!r}: {exc}") from exc

    def read_raw(self) -> bytes:
        """Read raw bytes from the VISA resource."""

        self._ensure_open()
        try:
            return bytes(self._resource.read_raw())
        except Exception as exc:  # pragma: no cover - depends on installed VISA stack
            raise VisaBackendError(f"VISA raw read failed: {exc}") from exc

    def query_binary_values(self, command: str, **kwargs: Any) -> Sequence[Any]:
        """Query binary values through PyVISA."""

        self._ensure_open()
        try:
            return self._resource.query_binary_values(command, **kwargs)
        except Exception as exc:  # pragma: no cover - depends on installed VISA stack
            raise VisaBackendError(f"VISA binary query failed for {command!r}: {exc}") from exc

    def close(self) -> None:
        """Close the VISA session and resource manager."""

        if self._closed:
            return
        _close_quietly(self._resource)
        _close_quietly(self._resource_manager)
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise VisaBackendError("VISA backend is closed.")


def _load_pyvisa() -> Any:
    try:
        import pyvisa
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise VisaBackendError(
            "PyVISA is not installed. Install the project with `uv pip install -e .`."
        ) from exc
    return pyvisa


def _create_resource_manager(visa_library: str | None = None) -> Any:
    pyvisa = _load_pyvisa()
    try:
        if visa_library is None:
            return pyvisa.ResourceManager()
        return pyvisa.ResourceManager(visa_library)
    except Exception as exc:  # pragma: no cover - depends on installed VISA stack
        raise VisaBackendError(f"Failed to create PyVISA ResourceManager: {exc}") from exc


def _describe_backend(resource_manager: Any) -> str:
    return str(getattr(resource_manager, "visalib", "unknown"))


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        pass
