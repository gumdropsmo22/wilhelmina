from __future__ import annotations
import json
import logging
import sys
import time
import traceback
from typing import Any, Dict

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc"] = self._format_exc(record.exc_info)
        for key in ("event", "user_id", "guild_id", "channel_id"):
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _format_exc(exc_info) -> str:
        return "".join(traceback.format_exception(*exc_info))

def configure(root_level: int = logging.INFO) -> None:
    """Configure root logger for JSON output to stdout."""
    root = logging.getLogger()
    root.setLevel(root_level)
    while root.handlers:
        root.handlers.pop()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

def log_exception(msg: str, **extra: Any) -> None:
    logging.getLogger("wilhelmina").error(msg, exc_info=True, extra=extra)
