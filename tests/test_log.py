"""Tests for the log module."""

import logging

from keysight_scope import log


class TestLoggerName:
    """Tests for the logger name constant."""

    def test_logger_name_is_keysight_scope(self):
        """Verify the base logger name is 'keysight_scope'."""
        assert log.LOGGER_NAME == "keysight_scope"


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_get_logger_without_name_returns_base_logger(self):
        """Test that get_logger() without arguments returns the base logger."""
        logger = log.get_logger()
        assert logger.name == "keysight_scope"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_none_returns_base_logger(self):
        """Test that get_logger(None) returns the base logger."""
        logger = log.get_logger(None)
        assert logger.name == "keysight_scope"

    def test_get_logger_with_name_returns_child_logger(self):
        """Test that get_logger with a name returns a child logger."""
        logger = log.get_logger("scpi")
        assert logger.name == "keysight_scope.scpi"

    def test_get_logger_with_submodule_name(self):
        """Test get_logger with various submodule names."""
        test_cases = [
            ("visa_backend", "keysight_scope.visa_backend"),
            ("channel", "keysight_scope.channel"),
            ("waveform", "keysight_scope.waveform"),
        ]
        for submodule, expected_name in test_cases:
            logger = log.get_logger(submodule)
            assert logger.name == expected_name

    def test_get_logger_returns_same_instance_for_same_name(self):
        """Test that get_logger returns the same logger instance for the same name."""
        logger1 = log.get_logger("test_module")
        logger2 = log.get_logger("test_module")
        assert logger1 is logger2

    def test_get_logger_base_returns_singleton(self):
        """Test that get_logger() without arguments returns the singleton base logger."""
        logger1 = log.get_logger()
        logger2 = log.get_logger()
        assert logger1 is logger2

    def test_get_logger_none_returns_singleton(self):
        """Test that get_logger(None) returns the same singleton as get_logger()."""
        logger1 = log.get_logger()
        logger2 = log.get_logger(None)
        assert logger1 is logger2


class TestLoggerConfiguration:
    """Tests for logger configuration and behavior."""

    def test_logger_has_default_level(self):
        """Test that the package logger delegates level filtering by default."""
        logger = log.get_logger()
        assert logger.level == logging.NOTSET

    def test_child_logger_propagates_to_parent(self):
        """Test that child loggers propagate to parent by default."""
        child_logger = log.get_logger("child")
        assert child_logger.propagate is True

    def test_logger_can_log_at_different_levels(self, caplog):
        """Test that the logger can log at different levels."""
        logger = log.get_logger("test")
        with caplog.at_level(logging.DEBUG, logger="keysight_scope"):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text
        assert "Critical message" in caplog.text

    def test_logger_respects_level_filtering(self, caplog):
        """Test that the logger respects level filtering."""
        logger = log.get_logger("test_filter")
        with caplog.at_level(logging.WARNING, logger="keysight_scope"):
            logger.debug("This should not appear")
            logger.info("This should not appear either")
            logger.warning("This should appear")

        assert "This should not appear" not in caplog.text
        assert "This should appear" in caplog.text


class TestLoggingIntegration:
    """Tests for integration with Python's logging system."""

    def test_logger_is_standard_python_logger(self):
        """Test that returned loggers are standard Python Logger instances."""
        logger = log.get_logger()
        assert isinstance(logger, logging.Logger)

    def test_logger_can_have_handlers_added(self):
        """Test that handlers can be added to the logger."""
        logger = log.get_logger("handler_test")
        handler = logging.StreamHandler()
        original_handler_count = len(logger.handlers)
        logger.addHandler(handler)
        assert len(logger.handlers) == original_handler_count + 1
        logger.removeHandler(handler)

    def test_logger_name_hierarchy(self):
        """Test that logger names follow proper hierarchy."""
        base = log.get_logger()
        scpi = log.get_logger("scpi")
        visa = log.get_logger("visa_backend")

        # Verify parent-child relationship through names
        assert scpi.name.startswith(base.name + ".")
        assert visa.name.startswith(base.name + ".")
        assert scpi.name != visa.name
