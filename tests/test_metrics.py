from __future__ import annotations

import respx
from httpx import Response

from llm_router.metrics import get_metrics, init_metrics, snapshot_to_prometheus


class TestRequestMetrics:
    def test_record_request_counts(self):
        m = init_metrics()
        m.record_request(
            alias="chess-small", backend="openai", latency_ms=100.0,
            success=True, fallback_used=False, limit_detected=False,
            prompt_tokens=5, completion_tokens=3, reasoning_tokens=2, total_tokens=8,
        )
        m.record_request(
            alias="chess-small", backend="anthropic", latency_ms=200.0,
            success=True, fallback_used=True, limit_detected=False,
            prompt_tokens=10, completion_tokens=5, reasoning_tokens=4, total_tokens=15,
        )
        m.record_request(
            alias="chess-large", backend="openai", latency_ms=50.0,
            success=False, fallback_used=False, limit_detected=True,
        )
        snap = m.snapshot()
        assert snap["requests"]["total"] == 3
        assert snap["requests"]["success"] == 2
        assert snap["requests"]["errors"] == 1
        assert snap["requests"]["fallbacks"] == 1
        assert snap["aliases"]["chess-small"] == 2
        assert snap["aliases"]["chess-large"] == 1
        assert snap["backends"]["openai"] == 2
        assert snap["backends"]["anthropic"] == 1
        assert snap["limit_detections"]["openai"] == 1
        assert round(snap["requests"]["average_latency_ms"], 2) == 116.67
        assert snap["usage"]["prompt_tokens"] == 15
        assert snap["usage"]["completion_tokens"] == 8
        assert snap["usage"]["output_tokens"] == 8
        assert snap["usage"]["reasoning_tokens"] == 6
        assert snap["usage"]["thinking_tokens"] == 6
        assert snap["usage"]["total_tokens"] == 23

    def test_record_cooldown_does_not_leak_content(self):
        m = init_metrics()
        m.record_cooldown("openai")
        snap = m.snapshot()
        assert snap["cooldowns"]["openai"] == 1
        # Privacy guard
        assert "prompt" not in snap
        assert "response" not in snap
        assert "message" not in snap

    def test_snapshot_isolation(self):
        m1 = init_metrics()
        m1.record_request(alias="a", backend="b", latency_ms=1, success=True, fallback_used=False, limit_detected=False)
        m2 = get_metrics()
        snap2 = m2.snapshot()
        assert snap2["requests"]["total"] == 1


async def test_metrics_endpoint(async_client):
    """/metrics returns privacy-safe aggregated counters."""
    init_metrics()
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "gpt-4o",
                "choices": [{"message": {"role": "assistant", "content": "hi"}}]
            })
        )
        await async_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )

    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests"]["total"] == 1
    assert data["requests"]["success"] == 1
    assert data["aliases"]["gpt-4o"] == 1
    assert data["backends"]["openai"] == 1
    assert "prompt" not in data
    assert "response" not in data
    assert "authorization" not in data
    assert data["timestamp"] > 0


async def test_metrics_endpoint_with_usage(async_client):
    """Usage tokens from successful backend responses are aggregated."""
    init_metrics()
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "gpt-4o",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "completion_tokens_details": {"reasoning_tokens": 2},
                    "total_tokens": 15,
                },
                "choices": [{"message": {"role": "assistant", "content": "hi"}}]
            })
        )
        await async_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )

    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["usage"]["prompt_tokens"] == 10
    assert data["usage"]["completion_tokens"] == 5
    assert data["usage"]["output_tokens"] == 5
    assert data["usage"]["reasoning_tokens"] == 2
    assert data["usage"]["thinking_tokens"] == 2
    assert data["usage"]["total_tokens"] == 15
    assert "content" not in str(data)


async def test_metrics_endpoint_prometheus_format(async_client):
    init_metrics()
    get_metrics().record_request(
        alias="chess-small",
        backend="openai",
        latency_ms=42.0,
        success=True,
        fallback_used=False,
        limit_detected=False,
    )

    resp = await async_client.get("/metrics?format=prometheus")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "llm_router_requests_total 1" in resp.text
    assert 'llm_router_alias_requests_total{alias="chess-small"} 1' in resp.text
    # no actual prompt/response content leaked (metric names with token fields are fine)
    assert "content" not in resp.text
    assert "authorization" not in resp.text


async def test_metrics_endpoint_prometheus_format_includes_usage(async_client):
    init_metrics()
    get_metrics().record_request(
        alias="chess-small",
        backend="openai",
        latency_ms=42.0,
        success=True,
        fallback_used=False,
        limit_detected=False,
        prompt_tokens=7,
        completion_tokens=3,
        reasoning_tokens=2,
        total_tokens=10,
    )

    resp = await async_client.get("/metrics?format=prometheus")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "llm_router_requests_total 1" in resp.text
    assert 'llm_router_alias_requests_total{alias="chess-small"} 1' in resp.text
    assert "llm_router_usage_prompt_tokens_total 7" in resp.text
    assert "llm_router_usage_completion_tokens_total 3" in resp.text
    assert "llm_router_usage_output_tokens_total 3" in resp.text
    assert "llm_router_usage_reasoning_tokens_total 2" in resp.text
    assert "llm_router_usage_thinking_tokens_total 2" in resp.text
    assert "llm_router_usage_total_tokens_total 10" in resp.text
    # no actual content leaked (metric names with token fields are fine)
    assert "content" not in resp.text
    assert "authorization" not in resp.text


def test_snapshot_to_prometheus_is_privacy_safe():
    m = init_metrics()
    m.record_backend_failure("openai")
    text = snapshot_to_prometheus(m.snapshot())
    assert "llm_router_backend_failures_total" in text
    # no actual prompt/response content leaked
    assert "content" not in text
    assert "authorization" not in text


async def test_metrics_endpoint_resets_on_init(async_client):
    init_metrics()
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "rate limit"})
        )
        await async_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )

    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests"]["total"] == 1
    assert data["requests"]["errors"] == 1
    assert data["backend_failures"]["openai"] == 1
    assert data["limit_detections"]["openai"] == 1


async def test_metrics_cooldown_counts_only_started_cooldowns(async_client):
    init_metrics()
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "rate limit"})
        )
        first = await async_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )
        first_metrics = (await async_client.get("/metrics")).json()
        second = await async_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )

    assert first.status_code == 429
    assert second.status_code == 429
    assert first_metrics["backend_failures"]["openai"] == 1
    assert "openai" not in first_metrics["cooldowns"]

    final_metrics = (await async_client.get("/metrics")).json()
    assert final_metrics["backend_failures"]["openai"] == 2
    assert final_metrics["cooldowns"]["openai"] == 1


async def test_metrics_errors_do_not_contribute_usage(async_client):
    """Failed requests must not increase token counters."""
    init_metrics()
    with respx.mock:
        respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "internal error"})
        )
        await async_client.post(
            "/v1/chat/completions",
            json={"model": "claude-opus", "messages": [{"role": "user", "content": "Hi"}]},
        )

    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests"]["errors"] == 1
    assert data["usage"]["prompt_tokens"] == 0
    assert data["usage"]["completion_tokens"] == 0
    assert data["usage"]["reasoning_tokens"] == 0
    assert data["usage"]["thinking_tokens"] == 0
    assert data["usage"]["total_tokens"] == 0
