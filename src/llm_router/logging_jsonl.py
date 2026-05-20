from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from llm_router.schemas import RouterConfig


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, dict):
            return json.dumps(record.msg, default=str)
        return json.dumps({"message": record.getMessage()}, default=str)


def init_logger(config: RouterConfig) -> logging.Logger:
    logger = logging.getLogger("llm_router")
    logger.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))
    for existing_handler in logger.handlers:
        existing_handler.close()
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)

    if config.logging.jsonl_path:
        Path(config.logging.jsonl_path).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(config.logging.jsonl_path)
        fh.setFormatter(_JSONFormatter())
        logger.addHandler(fh)
    return logger


def log_backend_state_change(
    logger: logging.Logger,
    *,
    backend: str,
    model_alias: str,
    state: str,  # e.g. "cooldown_started" or "cooldown_ended"
    cooldown_seconds: int | None = None,
) -> None:
    """Log a backend state change event without any prompt/response content."""
    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "event": "backend_state_change",
        "backend": backend,
        "model_alias": model_alias,
        "state": state,
    }
    if cooldown_seconds is not None:
        entry["cooldown_seconds"] = cooldown_seconds
    logger.info(entry)


def log_request(
    logger: logging.Logger,
    *,
    request_id: str,
    client: str,
    path: str,
    request_model: str,
    provider_model: str,
    backend: str,
    status_code: int | None,
    limit_detected: bool,
    fallback_used: bool,
    duration_ms: float,
    prompt_chars: int | None = None,
    response_chars: int | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "request_id": request_id,
        "client": client,
        "path": path,
        "request_model": request_model,
        "provider_model": provider_model,
        "backend": backend,
        "status_code": status_code,
        "limit_detected": limit_detected,
        "fallback_used": fallback_used,
        "duration_ms": duration_ms,
    }
    if prompt_chars is not None:
        entry["prompt_chars"] = prompt_chars
    if response_chars is not None:
        entry["response_chars"] = response_chars
    logger.info(entry)
