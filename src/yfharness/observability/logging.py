"""Rotating console/file/JSONL logging with recursive redaction."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from yfharness.config.paths import log_dir
from yfharness.observability.tracing import current_run_id, current_trace_id

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "credential",
}
_BEARER_PREFIX = "bearer "


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>"
            if any(marker in str(key).lower() for marker in _SENSITIVE_KEYS)
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if _BEARER_PREFIX in lowered or "sk-" in lowered:
            return "<redacted sensitive text>"
        return value
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": getattr(record, "run_id", None) or current_run_id.get(),
            "trace_id": getattr(record, "trace_id", None) or current_trace_id.get(),
        }
        for name in ("provider", "model", "tool_name", "duration", "error_type"):
            value = getattr(record, name, None)
            if value is not None:
                fields[name] = value
        if record.exc_info:
            fields["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact(fields), ensure_ascii=False, default=str)


def configure_logging(
    *,
    level: str = "INFO",
    directory: Path | None = None,
    console: bool = False,
) -> logging.Logger:
    target = directory or log_dir()
    target.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("yfharness")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False
    json_handler = RotatingFileHandler(
        target / "debug.jsonl",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    json_handler.setFormatter(JsonFormatter())
    logger.addHandler(json_handler)
    text_handler = RotatingFileHandler(
        target / "yfharness.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    text_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s run=%(run_id)s trace=%(trace_id)s %(message)s")
    )
    text_handler.addFilter(_ContextFilter())
    logger.addHandler(text_handler)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(console_handler)
    return logger


def get_logger(name: str = "yfharness") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logging.getLogger("yfharness").handlers:
        configure_logging()
    return logger


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", None) or current_run_id.get() or "-"
        record.trace_id = getattr(record, "trace_id", None) or current_trace_id.get() or "-"
        record.msg = redact(record.msg)
        record.args = redact(record.args)
        return True
