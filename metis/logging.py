"""Centralized logging configuration for Metis."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"metis.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        level_name = os.getenv("METIS_LOG_LEVEL", "WARNING").upper()
        level = getattr(logging, level_name, logging.WARNING)
        handler.setLevel(level)
        log_format = os.getenv("METIS_LOG_FORMAT", "text").lower()
        if log_format == "json":
            handler.setFormatter(_StructuredFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
        logger.setLevel(level)
        logger.addHandler(handler)
    return logger
