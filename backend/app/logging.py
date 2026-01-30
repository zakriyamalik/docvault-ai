# backend/app/logging.py

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """
    Emit one JSON object per log line.
    Enforces structured logging with required fields.
    Fallbacks to plain messages if structured data missing.
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).isoformat()
        log_obj = {
            "ts": ts,
            "level": record.levelname,
            "module": getattr(record, "module_name", record.name),
        }

        # Structured fields passed via extra
        structured = getattr(record, "structured", None)

        if structured:
            # Validate event key exists
            if "event" not in structured:
                raise ValueError("Structured log entry missing required field: 'event'")
            log_obj.update(structured)
        else:
            # fallback: plain message
            log_obj["message"] = record.getMessage()

        return json.dumps(log_obj, ensure_ascii=False)


class StructuredLogger:
    """
    Thin wrapper enforcing event-based structured logging.
    """

    def __init__(self, logger: logging.Logger, module_name: str):
        self._logger = logger
        self._module_name = module_name

    def info(self, *, event: str, **fields: Any) -> None:
        self._log(logging.INFO, event, fields)

    def warning(self, *, event: str, **fields: Any) -> None:
        self._log(logging.WARNING, event, fields)

    def error(self, *, event: str, **fields: Any) -> None:
        self._log(logging.ERROR, event, fields)

    def _log(self, level: int, event: str, fields: dict) -> None:
        structured = {"event": event, **fields}
        self._logger.log(
            level,
            msg="",  # message unused; everything is structured
            extra={
                "structured": structured,
                "module_name": self._module_name,
            },
        )


_LOGGING_INITIALIZED = False


def get_logger(module_name: str) -> StructuredLogger:
    """
    Factory for structured JSON loggers.
    Safe to call multiple times.
    """
    global _LOGGING_INITIALIZED

    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    if not _LOGGING_INITIALIZED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        _LOGGING_INITIALIZED = True

    return StructuredLogger(logger, module_name)
