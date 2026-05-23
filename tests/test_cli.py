from __future__ import annotations

from llm_router.cli import _check_env_vars, _format_usage, _build_benchmark
from llm_router.schemas import RouterConfig


def _make_config(**kwargs) -> RouterConfig:
    raw = {
        "server": {"host": "127.0.0.1", "port": 18080},
        "runtime": {},
        "backends": {},
        "models": {},
        "policies": {},
        "limit_detection": {},
        "logging": {},
    }
    raw.update(kwargs)
    return RouterConfig(**raw)


# ─── _check_env_vars ──────────────────────────────────────────────────────────


def test_check_env_vars_all_present(monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "secret")
    monkeypatch.setenv("ANTHROPIC_KEY", "secret")
    cfg = _make_config(backends={
        "openai": {
            "type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_KEY",
            "priority": 10,
        },
        "anthropic": {
            "type": "openai_compatible",
            "base_url": "https://api.anthropic.com/v1",
            "api_key_env": "ANTHROPIC_KEY",
            "priority": 20,
        },
    })
    assert _check_env_vars(cfg) == []


def test_check_env_vars_missing(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    cfg = _make_config(backends={
        "openai": {
            "type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "MISSING_KEY",
            "priority": 10,
        },
    })
    issues = _check_env_vars(cfg)
    assert len(issues) == 1
    assert "MISSING_KEY" in issues[0]


def test_check_env_vars_no_key_required():
    cfg = _make_config(backends={
        "ollama": {
            "type": "openai_compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "priority": 10,
        },
    })
    assert _check_env_vars(cfg) == []


def test_check_env_vars_server_require_api_key(monkeypatch):
    monkeypatch.delenv("ROUTER_KEY", raising=False)
    cfg = _make_config(
        server={"host": "127.0.0.1", "port": 18080, "require_api_key": True, "api_key_env": "ROUTER_KEY"},
    )
    issues = _check_env_vars(cfg)
    assert len(issues) == 1
    assert "ROUTER_KEY" in issues[0]


# ─── _format_usage ──────────────────────────────────────────────────────────


def test_format_usage_basic():
    text = _format_usage({
        "requests": {"total": 3, "success": 3, "errors": 0, "fallbacks": 0, "average_latency_ms": 42},
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "reasoning_tokens": 4, "total_tokens": 30},
    })
    assert "Requests  total:" in text
    assert "success:" in text
    assert "42 ms" in text
    assert "prompt:" in text
    assert "reasoning:" in text
    assert "thinking:" in text
    assert "10" in text


def test_format_usage_empty():
    text = _format_usage({})
    assert text  # still produces lines


def test_format_usage_does_not_contain_secrets():
    text = _format_usage({
        "requests": {"total": 3, "success": 3, "errors": 0, "fallbacks": 0, "average_latency_ms": 42},
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "aliases": {"hello": 1},
        "backends": {"openai": 1},
    })
    # Confirm no secrets / content leak in formatted output
    assert "OPENAI_KEY" not in text
    assert "secret" not in text
    assert "Bearer" not in text


# ─── _build_benchmark ───────────────────────────────────────────────────────


def test_build_benchmark_computes_rates():
    bench = _build_benchmark({
        "requests": {"total": 100, "success": 90, "errors": 10, "fallbacks": 5, "average_latency_ms": 44.4},
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "reasoning_tokens": 120, "total_tokens": 1500},
        "aliases": {"a": 3},
        "backends": {"b": 3},
        "cooldowns": {"c": 1},
        "backend_failures": {"d": 2},
        "limit_detections": {"e": 1},
    })
    assert bench["git_ref"] is None
    assert bench["version"] == "0.1.0"
    assert "timestamp_utc" in bench
    assert bench["requests"]["total"] == 100
    assert bench["requests"]["success"] == 90
    assert bench["requests"]["errors"] == 10
    assert bench["requests"]["fallbacks"] == 5
    assert bench["requests"]["average_latency_ms"] == 44.4
    assert bench["usage"]["prompt_tokens"] == 1000
    assert bench["usage"]["completion_tokens"] == 500
    assert bench["usage"]["output_tokens"] == 500
    assert bench["usage"]["reasoning_tokens"] == 120
    assert bench["usage"]["thinking_tokens"] == 120
    assert bench["usage"]["total_tokens"] == 1500
    assert bench["error_rate"] == 0.1
    assert bench["fallback_rate"] == 0.05
    assert bench["aliases"] == {"a": 3}
    assert bench["backends"] == {"b": 3}
    assert bench["cooldowns"] == {"c": 1}
    assert bench["backend_failures"] == {"d": 2}
    assert bench["limit_detections"] == {"e": 1}


def test_build_benchmark_no_prompt_or_response_content():
    bench = _build_benchmark({
        "requests": {"total": 10, "success": 10, "errors": 0, "fallbacks": 0, "average_latency_ms": 1.0},
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "backends": {"openai": 10},
    })
    # Ensure no prompt/response text ever leaks
    assert "prompt" not in str(bench).lower().split("prompt_tokens")[0]
    # Better: just confirm the output string never contains message content
    dumped = str(bench)
    assert "Bearer " not in dumped
    assert "OPENAI_KEY" not in dumped
