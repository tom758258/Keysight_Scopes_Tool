"""Tests for the errors module."""

import pytest

from scopes_tool_core import errors


class TestKeysightScopeError:
    """Tests for the base KeysightScopeError exception."""

    def test_inherits_from_exception(self):
        """Verify KeysightScopeError inherits from Exception."""
        assert issubclass(errors.KeysightScopeError, Exception)

    def test_can_be_raised_with_message(self):
        """Test raising KeysightScopeError with a message."""
        with pytest.raises(errors.KeysightScopeError) as excinfo:
            raise errors.KeysightScopeError("Something went wrong")
        assert "Something went wrong" in str(excinfo.value)

    def test_can_be_raised_without_message(self):
        """Test raising KeysightScopeError without a message."""
        with pytest.raises(errors.KeysightScopeError):
            raise errors.KeysightScopeError()


class TestVisaBackendError:
    """Tests for VisaBackendError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify VisaBackendError inherits from KeysightScopeError."""
        assert issubclass(errors.VisaBackendError, errors.KeysightScopeError)

    def test_inherits_from_exception(self):
        """Verify VisaBackendError inherits from Exception."""
        assert issubclass(errors.VisaBackendError, Exception)

    def test_can_be_raised_with_message(self):
        """Test raising VisaBackendError with a message."""
        with pytest.raises(errors.VisaBackendError) as excinfo:
            raise errors.VisaBackendError("VISA connection failed")
        assert "VISA connection failed" in str(excinfo.value)


class TestBackendClosedError:
    """Tests for BackendClosedError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify BackendClosedError inherits from KeysightScopeError."""
        assert issubclass(errors.BackendClosedError, errors.KeysightScopeError)

    def test_can_be_raised_with_message(self):
        """Test raising BackendClosedError with a message."""
        with pytest.raises(errors.BackendClosedError) as excinfo:
            raise errors.BackendClosedError("Backend already closed")
        assert "Backend already closed" in str(excinfo.value)


class TestIDNParseError:
    """Tests for IDNParseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify IDNParseError inherits from KeysightScopeError."""
        assert issubclass(errors.IDNParseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify IDNParseError inherits from ValueError."""
        assert issubclass(errors.IDNParseError, ValueError)

    def test_can_be_caught_as_value_error(self):
        """Test that IDNParseError can be caught as ValueError."""
        with pytest.raises(ValueError):
            raise errors.IDNParseError("Invalid IDN format")

    def test_can_be_caught_as_keysight_scope_error(self):
        """Test that IDNParseError can be caught as KeysightScopeError."""
        with pytest.raises(errors.KeysightScopeError):
            raise errors.IDNParseError("Invalid IDN format")


class TestUnsupportedModelError:
    """Tests for UnsupportedModelError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify UnsupportedModelError inherits from KeysightScopeError."""
        assert issubclass(errors.UnsupportedModelError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify UnsupportedModelError inherits from ValueError."""
        assert issubclass(errors.UnsupportedModelError, ValueError)

    def test_can_be_caught_as_value_error(self):
        """Test that UnsupportedModelError can be caught as ValueError."""
        with pytest.raises(ValueError):
            raise errors.UnsupportedModelError("Unknown model")


class TestSystemErrorParseError:
    """Tests for SystemErrorParseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify SystemErrorParseError inherits from KeysightScopeError."""
        assert issubclass(errors.SystemErrorParseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify SystemErrorParseError inherits from ValueError."""
        assert issubclass(errors.SystemErrorParseError, ValueError)


class TestParameterValidationError:
    """Tests for ParameterValidationError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify ParameterValidationError inherits from KeysightScopeError."""
        assert issubclass(errors.ParameterValidationError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify ParameterValidationError inherits from ValueError."""
        assert issubclass(errors.ParameterValidationError, ValueError)


class TestChannelResponseError:
    """Tests for ChannelResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify ChannelResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.ChannelResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify ChannelResponseError inherits from ValueError."""
        assert issubclass(errors.ChannelResponseError, ValueError)


class TestTimebaseResponseError:
    """Tests for TimebaseResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify TimebaseResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.TimebaseResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify TimebaseResponseError inherits from ValueError."""
        assert issubclass(errors.TimebaseResponseError, ValueError)


class TestTriggerResponseError:
    """Tests for TriggerResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify TriggerResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.TriggerResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify TriggerResponseError inherits from ValueError."""
        assert issubclass(errors.TriggerResponseError, ValueError)


class TestMeasurementResponseError:
    """Tests for MeasurementResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify MeasurementResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.MeasurementResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify MeasurementResponseError inherits from ValueError."""
        assert issubclass(errors.MeasurementResponseError, ValueError)


class TestWaveformResponseError:
    """Tests for WaveformResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify WaveformResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.WaveformResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify WaveformResponseError inherits from ValueError."""
        assert issubclass(errors.WaveformResponseError, ValueError)


class TestScreenshotResponseError:
    """Tests for ScreenshotResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify ScreenshotResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.ScreenshotResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify ScreenshotResponseError inherits from ValueError."""
        assert issubclass(errors.ScreenshotResponseError, ValueError)


class TestAcquisitionResponseError:
    """Tests for AcquisitionResponseError exception."""

    def test_inherits_from_keysight_scope_error(self):
        """Verify AcquisitionResponseError inherits from KeysightScopeError."""
        assert issubclass(errors.AcquisitionResponseError, errors.KeysightScopeError)

    def test_inherits_from_value_error(self):
        """Verify AcquisitionResponseError inherits from ValueError."""
        assert issubclass(errors.AcquisitionResponseError, ValueError)


class TestExceptionHierarchy:
    """Tests for the overall exception hierarchy."""

    def test_all_errors_are_keysight_scope_errors(self):
        """Verify all custom errors inherit from KeysightScopeError."""
        error_classes = [
            errors.VisaBackendError,
            errors.BackendClosedError,
            errors.IDNParseError,
            errors.UnsupportedModelError,
            errors.SystemErrorParseError,
            errors.ParameterValidationError,
            errors.ChannelResponseError,
            errors.TimebaseResponseError,
            errors.TriggerResponseError,
            errors.MeasurementResponseError,
            errors.WaveformResponseError,
            errors.ScreenshotResponseError,
            errors.AcquisitionResponseError,
        ]
        for error_class in error_classes:
            assert issubclass(error_class, errors.KeysightScopeError), (
                f"{error_class.__name__} should inherit from KeysightScopeError"
            )

    def test_parse_errors_are_value_errors(self):
        """Verify all parse-related errors inherit from ValueError."""
        parse_error_classes = [
            errors.IDNParseError,
            errors.UnsupportedModelError,
            errors.SystemErrorParseError,
            errors.ParameterValidationError,
            errors.ChannelResponseError,
            errors.TimebaseResponseError,
            errors.TriggerResponseError,
            errors.MeasurementResponseError,
            errors.WaveformResponseError,
            errors.ScreenshotResponseError,
            errors.AcquisitionResponseError,
        ]
        for error_class in parse_error_classes:
            assert issubclass(error_class, ValueError), (
                f"{error_class.__name__} should inherit from ValueError"
            )