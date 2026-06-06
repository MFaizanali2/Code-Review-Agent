"""Logging configuration for the backend server."""

from __future__ import annotations

import logging
import sys

from config.settings import get_settings


def setup_logging() -> logging.Logger:
    """Configure and return the backend logger."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logger = logging.getLogger("backend")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
