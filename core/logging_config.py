"""
core/logging_config.py

Centralized logging setup for the application.
Logs are written to console and to logs/app.log.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import settings


def configure_logging() -> None:
    """Configure root logger once for the process."""
    root = logging.getLogger()
    if root.handlers:
        return

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    level_name = str(settings.log_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
