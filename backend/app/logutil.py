"""Unified logging — output to stderr and log file."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_logger: logging.Logger | None = None
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "app.log"


def get_logger(name: str = "exceltoweb") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(fmt)
        logger.addHandler(stderr_handler)

        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError:
            pass

    _logger = logger
    return logger


def log(msg: str) -> None:
    """Log one line to stderr + file."""
    get_logger().info(msg)
    sys.stderr.flush()
