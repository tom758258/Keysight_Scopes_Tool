"""Logging helpers for SCPI communication."""

from __future__ import annotations

import logging

LOGGER_NAME = "keysight_scope"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a package logger, optionally scoped to a submodule name."""

    if name is None:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
