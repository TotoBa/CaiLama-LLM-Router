from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.fixture
def mock_config_path(tmp_path):
    config_content = """
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 600
  connect_timeout_seconds: 10

backends:
  openai:
    type: openai_compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    priority: 10
  anthropic:
    type: openai_compatible
    base_url: https://api.anthropic.com/v1
    api_key_env: ANTHROPIC_API_KEY
    priority: 20

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: standard
  claude-opus:
    provider_model: claude-3-opus-20240229
    backends:
      - anthropic
    policy: standard
  fallback-model:
    provider_model: fallback-llm
    backends:
      - openai
      - anthropic
    policy: standard
  balanced-model:
    provider_model: balanced-llm
    backends:
      - openai
      - anthropic
    policy: standard
    routing_strategy: round_robin
  cooldown-model:
    provider_model: cooldown-llm
    backends:
      - openai
      - anthropic
    policy: cooldown
    routing_strategy: round_robin

policies:
  standard:
    max_attempts_per_backend: 1
    max_backend_failures_before_cooldown: 2
    backend_cooldown_seconds: 300
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: false
    fallback_on_4xx: false
    fallback_on_model_not_found: false
    timeout_seconds: 300
  cooldown:
    max_attempts_per_backend: 1
    max_backend_failures_before_cooldown: 1
    backend_cooldown_seconds: 300
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    fallback_on_model_not_found: false
    timeout_seconds: 300

limit_detection:
  status_codes:
    - 429
  body_markers:
    - "rate limit"

logging:
  level: INFO
"""
    path = tmp_path / "mock_router.yaml"
    path.write_text(config_content)
    return path


@pytest.fixture
def mock_app(mock_config_path):
    from llm_router.config import load_config
    from llm_router.app import create_app
    return create_app(config=load_config(mock_config_path))


@pytest.fixture
def mock_client(mock_app):
    from fastapi.testclient import TestClient
    return TestClient(mock_app)


def test_chat_completions_forwarding(mock_client):
    with respx.mock:
        route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "gpt-4o",
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]
            })
        )
        response = mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hi"}]
            },
            headers={"X-LLM-Client": "test-client"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "gpt-4o"
        assert response.headers["x-llm-router-backend"] == "openai"
        assert response.headers["x-llm-router-request-model"] == "gpt-4o"
        assert response.headers["x-llm-router-provider-model"] == "gpt-4o"
        assert route.called


def test_chat_completions_fallback_on_429(mock_client):
    with respx.mock:
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "rate limit"})
        )
        anthropic_route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "claude-3-opus-20240229",
                "choices": [{"message": {"role": "assistant", "content": "Hello from Claude!"}}]
            })
        )
        response = mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "fallback-model",
                "messages": [{"role": "user", "content": "Hi"}]
            },
            headers={"X-LLM-Client": "test-client"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Hello from Claude!"
        assert response.headers["x-llm-router-fallback-used"] == "true"
        assert openai_route.called
        assert anthropic_route.called


def test_chat_completions_round_robin_distribution(mock_client):
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test-openai",
                "object": "chat.completion",
                "model": "balanced-llm",
                "choices": [{"message": {"role": "assistant", "content": "openai"}}]
            })
        )
        respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test-anthropic",
                "object": "chat.completion",
                "model": "balanced-llm",
                "choices": [{"message": {"role": "assistant", "content": "anthropic"}}]
            })
        )

        first = mock_client.post(
            "/v1/chat/completions",
            json={"model": "balanced-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        second = mock_client.post(
            "/v1/chat/completions",
            json={"model": "balanced-model", "messages": [{"role": "user", "content": "Hi"}]},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.headers["x-llm-router-backend"] == "openai"
        assert second.headers["x-llm-router-backend"] == "anthropic"
        assert first.headers["x-llm-router-fallback-used"] == "false"
        assert second.headers["x-llm-router-fallback-used"] == "false"


def test_chat_completions_skips_backend_during_cooldown(mock_client):
    with respx.mock:
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "internal error"})
        )
        anthropic_route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test-anthropic",
                "object": "chat.completion",
                "model": "cooldown-llm",
                "choices": [{"message": {"role": "assistant", "content": "anthropic"}}]
            })
        )

        first = mock_client.post(
            "/v1/chat/completions",
            json={"model": "cooldown-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        second = mock_client.post(
            "/v1/chat/completions",
            json={"model": "cooldown-model", "messages": [{"role": "user", "content": "Hi"}]},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.headers["x-llm-router-backend"] == "anthropic"
        assert first.headers["x-llm-router-fallback-used"] == "true"
        assert second.headers["x-llm-router-backend"] == "anthropic"
        assert second.headers["x-llm-router-fallback-used"] == "false"
        assert openai_route.call_count == 1
        assert anthropic_route.call_count == 2


def test_chat_completions_model_mapping(mock_client):
    with respx.mock:
        route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "claude-3-opus-20240229",
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]
            })
        )
        response = mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-opus",
                "messages": [{"role": "user", "content": "Hi"}]
            }
        )
        assert response.status_code == 200
        assert response.headers["x-llm-router-backend"] == "anthropic"
        assert response.headers["x-llm-router-request-model"] == "claude-opus"
        assert response.headers["x-llm-router-provider-model"] == "claude-3-opus-20240229"
        assert route.called


def test_chat_completions_all_backends_fail(mock_client):
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "internal error"})
        )
        respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "internal error"})
        )
        response = mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-opus",
                "messages": [{"role": "user", "content": "Hi"}]
            }
        )
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
