from __future__ import annotations

import pytest
import respx
import httpx
from httpx import Response

pytestmark = pytest.mark.asyncio


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
  legacy-error-model:
    provider_model: fallback-llm
    backends:
      - openai
      - anthropic
    policy: legacy_errors
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
  retry-connection-model:
    provider_model: retry-llm
    backends:
      - openai
      - anthropic
    policy: retry
  recovery-model:
    provider_model: recovery-llm
    backends:
      - openai
      - anthropic
    policy: cooldown

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
  legacy_errors:
    max_attempts_per_backend: 1
    max_backend_failures_before_cooldown: 2
    backend_cooldown_seconds: 300
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    fallback_on_model_not_found: false
    return_last_error_on_exhausted_backends: false
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
  retry:
    max_attempts_per_backend: 2
    max_backend_failures_before_cooldown: 2
    backend_cooldown_seconds: 300
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: false
    fallback_on_4xx: false
    fallback_on_model_not_found: false
    timeout_seconds: 300

  recovery-model:
    provider_model: recovery-llm
    backends:
      - openai
      - anthropic
    policy: cooldown

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
async def mock_client(mock_app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://test",
    ) as client:
        yield client


async def test_chat_completions_forwarding(mock_client):
    with respx.mock:
        route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "gpt-4o",
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]
            })
        )
        response = await mock_client.post(
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


async def test_chat_completions_fallback_on_429(mock_client):
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
        response = await mock_client.post(
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


async def test_chat_completions_returns_last_backend_error_when_exhausted(mock_client):
    with respx.mock:
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "openai rate limit"})
        )
        anthropic_route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "anthropic rate limit"})
        )
        response = await mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "fallback-model",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

        assert response.status_code == 429
        assert response.json() == {"error": "anthropic rate limit"}
        assert response.headers["x-llm-router-backend"] == "anthropic"
        assert response.headers["x-llm-router-fallback-used"] == "true"
        assert response.headers["x-llm-router-returned-last-error"] == "true"
        assert openai_route.called
        assert anthropic_route.called


async def test_chat_completions_can_disable_last_backend_error_passthrough(mock_client):
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "openai rate limit"})
        )
        respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(429, json={"error": "anthropic rate limit"})
        )
        response = await mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "legacy-error-model",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

        assert response.status_code == 503
        assert response.json()["error"]["type"] == "all_backends_failed"


async def test_chat_completions_round_robin_distribution(mock_client):
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

        first = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "balanced-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        second = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "balanced-model", "messages": [{"role": "user", "content": "Hi"}]},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.headers["x-llm-router-backend"] == "openai"
        assert second.headers["x-llm-router-backend"] == "anthropic"
        assert first.headers["x-llm-router-fallback-used"] == "false"
        assert second.headers["x-llm-router-fallback-used"] == "false"


async def test_chat_completions_skips_backend_during_cooldown(mock_client):
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

        first = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "cooldown-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        second = await mock_client.post(
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


async def test_chat_completions_model_mapping(mock_client):
    with respx.mock:
        route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "claude-3-opus-20240229",
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]
            })
        )
        response = await mock_client.post(
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


async def test_chat_completions_retries_connection_error(mock_client):
    with respx.mock:
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                Response(200, json={
                    "id": "chatcmpl-test-openai",
                    "object": "chat.completion",
                    "model": "retry-llm",
                    "choices": [{"message": {"role": "assistant", "content": "openai"}}]
                }),
            ]
        )
        response = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "retry-connection-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "openai"
        assert openai_route.call_count == 2
        assert response.headers["x-llm-router-backend"] == "openai"
        assert response.headers["x-llm-router-fallback-used"] == "false"


async def test_chat_completions_fallback_on_5xx(mock_client):
    with respx.mock:
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(502, json={"error": "bad gateway"})
        )
        anthropic_route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test-anthropic",
                "object": "chat.completion",
                "model": "fallback-llm",
                "choices": [{"message": {"role": "assistant", "content": "anthropic"}}]
            })
        )
        response = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "legacy-error-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "anthropic"
        assert openai_route.called
        assert anthropic_route.called
        assert response.headers["x-llm-router-fallback-used"] == "true"


async def test_chat_completions_recovered_backend_available_again(mock_client):
    """A backend in cooldown becomes available again after cooldown expires."""
    import time
    with respx.mock:
        _openai_calls = 0

        def _openai_resp(request):
            nonlocal _openai_calls
            _openai_calls += 1
            if _openai_calls == 1:
                return Response(500, json={"error": "internal error"})
            return Response(200, json={
                "id": "chatcmpl-recovered",
                "object": "chat.completion",
                "model": "recovery-llm",
                "choices": [{"message": {"role": "assistant", "content": "openai-recovered"}}]
            })

        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(side_effect=_openai_resp)
        anthropic_route = respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "recovery-llm",
                "choices": [{"message": {"role": "assistant", "content": "anthropic"}}]
            })
        )

        # First request: openai fails -> cooldown -> fallback to anthropic
        first = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "recovery-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert first.status_code == 200
        assert first.headers["x-llm-router-backend"] == "anthropic"

        # Travel forward in time past cooldown
        from llm_router import openai_compat as oa
        now = time.monotonic()
        for key, state in oa._BACKEND_STATE.items():
            state.cooldown_until = now - 1.0

        second = await mock_client.post(
            "/v1/chat/completions",
            json={"model": "recovery-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert second.status_code == 200
        # After recovery openai should be tried first again and succeed
        assert second.headers["x-llm-router-backend"] == "openai"
        assert second.json()["choices"][0]["message"]["content"] == "openai-recovered"
        assert openai_route.call_count == 2
        assert anthropic_route.call_count == 1


async def test_chat_completions_all_backends_fail(mock_client):
    with respx.mock:
        respx.post("https://api.anthropic.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "internal error"})
        )
        response = await mock_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-opus",
                "messages": [{"role": "user", "content": "Hi"}]
            }
        )
        assert response.status_code == 500
        assert response.json() == {"error": "internal error"}
        assert response.headers["x-llm-router-backend"] == "anthropic"
        assert response.headers["x-llm-router-returned-last-error"] == "true"


# Fixtures for passthrough strategy

@pytest.fixture
def mock_config_passthrough_path(tmp_path):
    config_content = """
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 600
  connect_timeout_seconds: 10
  unknown_model_strategy: passthrough

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
  default:
    provider_model: default-llm
    backends:
      - openai
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    fallback_on_model_not_found: false
    return_last_error_on_exhausted_backends: true
    timeout_seconds: 300

limit_detection:
  status_codes:
    - 429
  body_markers:
    - "rate limit"

logging:
  level: INFO
"""
    path = tmp_path / "passthrough_router.yaml"
    path.write_text(config_content)
    return path


@pytest.fixture
def mock_passthrough_app(mock_config_passthrough_path):
    from llm_router.config import load_config
    from llm_router.app import create_app
    return create_app(config=load_config(mock_config_passthrough_path))


@pytest.fixture
async def mock_passthrough_client(mock_passthrough_app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_passthrough_app),
        base_url="http://test",
    ) as client:
        yield client


async def test_chat_completions_passthrough_unknown_model(mock_passthrough_client):
    with respx.mock:
        route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "unknown-model",
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]
            })
        )
        response = await mock_passthrough_client.post(
            "/v1/chat/completions",
            json={"model": "unknown-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 200
        assert response.json()["model"] == "unknown-model"
        assert response.headers["x-llm-router-backend"] == "openai"
        assert response.headers.get("x-llm-router-fallback-used") == "false"
        assert route.called
