"""Project exception types."""


class KeysightScopeError(Exception):
    """Base exception for package-specific errors."""


class VisaBackendError(KeysightScopeError):
    """Raised when VISA setup or I/O fails."""


class BackendClosedError(KeysightScopeError):
    """Raised when a backend is used after it has been closed."""


class IDNParseError(KeysightScopeError, ValueError):
    """Raised when an `*IDN?` response cannot be parsed."""


class UnsupportedModelError(KeysightScopeError, ValueError):
    """Raised when a model cannot be mapped to a capability profile."""


class SystemErrorParseError(KeysightScopeError, ValueError):
    """Raised when `:SYSTem:ERRor?` cannot be parsed."""


class ParameterValidationError(KeysightScopeError, ValueError):
    """Raised when a setting would be invalid for the selected instrument."""


class ChannelResponseError(KeysightScopeError, ValueError):
    """Raised when a channel query response cannot be parsed."""
