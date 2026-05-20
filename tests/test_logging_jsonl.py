from __future__ import annotations

import json
import logging
from io import StringIO

from llm_router.logging_jsonl import _JSONFormatter, log_backend_state_change, log_request


def test_json_formatter_outputs_dict_directly():
    formatter = _JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg={"key": "value"}, args=(), exc_info=None
    )
    assert json.loads(formatter.format(record)) == {"key": "value"}


def test_log_backend_state_change_no_sensitive_content():
    """Backend state changes must never contain prompt/response content."""
    logger = logging.getLogger("test_state")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JSONFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    log_backend_state_change(
        logger, backend="openai", model_alias="chess-small",
        state="cooldown_started", cooldown_seconds=300,
    )

    entry = json.loads(stream.getvalue().strip())
    assert entry["event"] == "backend_state_change"
    assert entry["backend"] == "openai"
    assert entry["model_alias"] == "chess-small"
    assert entry["state"] == "cooldown_started"
    assert entry["cooldown_seconds"] == 300
    # Privacy guard: no prompt/response/header content
    assert "prompt" not in entry
    assert "response" not in entry
    assert "message" not in entry


def test_log_request_privacy_defaults():
    """Default log_request must not include prompt/response chars unless explicitly provided."""
    logger = logging.getLogger("test_request")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JSONFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    log_request(
        logger,
        request_id="req-123",
        client="chess-system",
        path="/v1/chat/completions",
        request_model="chess-small",
        provider_model="deepseek-v4-flash:cloud",
        backend="openai",
        status_code=200,
        limit_detected=False,
        fallback_used=False,
        duration_ms=1234.5,
    )

    entry = json.loads(stream.getvalue().strip())
    assert entry["request_id"] == "req-123"
    assert entry["client"] == "chess-system"
    assert "prompt_chars" not in entry
    assert "response_chars" not in entry
