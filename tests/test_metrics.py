from __future__ import annotations

import respx
from httpx import Response

from llm_router.metrics import get_metrics, init_metrics


class TestRequestMetrics:
    def test_record_request_counts(self):
        m = init_metrics()
        m.record_request(
            alias="chess-small", backend="openai", latency_ms=100.0,
            success=True, fallback_used=False, limit_detected=False,
        )
        m.record_request(
            alias="chess-small", backend="anthropic", latency_ms=200.0,
            success=True, fallback_used=True, limit_detected=False,
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
