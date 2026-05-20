from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from llm_router.backends import backend_order, resolve_backend_model
from llm_router.errors import RouterError, error_response
from llm_router.fallback import looks_like_limit_error, should_fallback
from llm_router.logging_jsonl import log_backend_state_change, log_request
from llm_router.metrics import get_metrics, snapshot_to_prometheus
from llm_router.schemas import BackendConfig, PolicyConfig, RouterConfig

router = APIRouter()

# App state is injected by the app module at startup
_CONFIG: RouterConfig | None = None
_CONFIG_PATH: Path | None = None
_HTTP_CLIENT: httpx.AsyncClient | None = None
_LOGGER: Any = None
_ROUND_ROBIN_OFFSETS: dict[str, int] = {}
_BACKEND_STATE: dict[tuple[str, str], "BackendState"] = {}


@dataclass
class BackendState:
    failures: int = 0
    cooldown_until: float = 0.0


def _get_logger() -> Any:
    return _LOGGER


def _get_config() -> RouterConfig:
    global _CONFIG
    if _CONFIG is None:
        raise RouterError("Config not loaded", 500, "configuration_error")
    if _CONFIG.runtime.reload_config_on_request and _CONFIG_PATH is not None:
        from llm_router.config import load_config

        _CONFIG = load_config(_CONFIG_PATH)
    return _CONFIG


def set_config(config: RouterConfig, config_path: Path | str | None = None) -> None:
    global _CONFIG, _CONFIG_PATH
    _CONFIG = config
    _CONFIG_PATH = Path(config_path) if config_path is not None else None
    _ROUND_ROBIN_OFFSETS.clear()
    _BACKEND_STATE.clear()


def set_http_client(client: httpx.AsyncClient) -> None:
    global _HTTP_CLIENT
    _HTTP_CLIENT = client


def set_logger(logger: Any) -> None:
    global _LOGGER
    _LOGGER = logger


def _build_headers(backend: BackendConfig, api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _unknown_model_error(model: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_response(f"Unknown model '{model}'", "model_not_found"),
    )


def _router_response_headers(
    *,
    backend_name: str,
    model_alias: str,
    provider_model: str,
    fallback_used: bool,
    returned_last_error: bool = False,
) -> dict[str, str]:
    headers = {
        "x-llm-router-backend": backend_name,
        "x-llm-router-request-model": model_alias,
        "x-llm-router-provider-model": provider_model,
        "x-llm-router-fallback-used": "true" if fallback_used else "false",
    }
    if returned_last_error:
        headers["x-llm-router-returned-last-error"] = "true"
    return headers


def _backend_error_response(
    *,
    status_code: int,
    body: bytes,
    content_type: str | None,
    backend_name: str,
    model_alias: str,
    provider_model: str,
    fallback_used: bool,
) -> Response:
    media_type = content_type.split(";", 1)[0] if content_type else None
    return Response(
        content=body,
        status_code=status_code,
        headers=_router_response_headers(
            backend_name=backend_name,
            model_alias=model_alias,
            provider_model=provider_model,
            fallback_used=fallback_used,
            returned_last_error=True,
        ),
        media_type=media_type,
    )


def _stream_backend_error_response(
    *,
    status_code: int,
    body: bytes,
    backend_name: str,
    model_alias: str,
    provider_model: str,
    fallback_used: bool,
) -> StreamingResponse:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = error_response("Backend stream failed", "backend_error")

    async def _error_stream() -> Any:
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    return StreamingResponse(
        _error_stream(),
        status_code=status_code,
        headers=_router_response_headers(
            backend_name=backend_name,
            model_alias=model_alias,
            provider_model=provider_model,
            fallback_used=fallback_used,
            returned_last_error=True,
        ),
        media_type="text/event-stream",
    )


def _route_policy(model_alias: str, config: RouterConfig) -> PolicyConfig:
    route = config.models.get(model_alias)
    policy_name = route.policy if route else "default"
    return config.policies.get(policy_name) or next(iter(config.policies.values()))


def _state_key(model_alias: str, backend_name: str) -> tuple[str, str]:
    return (model_alias, backend_name)


def _backend_state(model_alias: str, backend_name: str) -> BackendState:
    return _BACKEND_STATE.setdefault(_state_key(model_alias, backend_name), BackendState())


def _is_backend_available(model_alias: str, backend_name: str, now: float) -> bool:
    state = _backend_state(model_alias, backend_name)
    if state.cooldown_until and state.cooldown_until <= now:
        state.cooldown_until = 0.0
        state.failures = 0
        return True
    if state.cooldown_until:
        return False
    return True


def _backend_cooldown_expired(model_alias: str, backend_name: str, now: float) -> bool:
    state = _backend_state(model_alias, backend_name)
    if state.cooldown_until <= now:
        return bool(state.cooldown_until)
    return False


def _record_backend_success(model_alias: str, backend_name: str) -> None:
    _BACKEND_STATE.pop(_state_key(model_alias, backend_name), None)


def _record_backend_failure(model_alias: str, backend_name: str, policy: PolicyConfig) -> None:
    if policy.max_backend_failures_before_cooldown <= 0:
        return
    state = _backend_state(model_alias, backend_name)
    state.failures += 1
    if state.failures >= policy.max_backend_failures_before_cooldown:
        state.failures = 0
        state.cooldown_until = time.monotonic() + policy.backend_cooldown_seconds
        logger = _get_logger()
        if logger:
            log_backend_state_change(
                logger,
                backend=backend_name,
                model_alias=model_alias,
                state="cooldown_started",
                cooldown_seconds=policy.backend_cooldown_seconds,
            )


def _select_backends(model_alias: str, config: RouterConfig) -> list[str]:
    base_order = backend_order(model_alias, config)
    now = time.monotonic()
    recovered = [
        backend_name
        for backend_name in base_order
        if _backend_cooldown_expired(model_alias, backend_name, now)
    ]
    available = [backend_name for backend_name in base_order if _is_backend_available(model_alias, backend_name, now)]
    if not available:
        return []
    if recovered:
        return recovered + [backend_name for backend_name in available if backend_name not in recovered]

    route = config.models.get(model_alias)
    strategy = route.routing_strategy if route else "priority"
    if strategy != "round_robin":
        return available

    offset = _ROUND_ROBIN_OFFSETS.get(model_alias, 0) % len(available)
    _ROUND_ROBIN_OFFSETS[model_alias] = offset + 1
    return available[offset:] + available[:offset]


def _should_retry_backend(
    exc: Exception,
    attempt_number: int,
    policy: PolicyConfig,
) -> bool:
    if attempt_number >= max(policy.max_attempts_per_backend, 1):
        return False
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return policy.retry_on_connection_error
    if isinstance(exc, httpx.TimeoutException):
        return policy.retry_on_timeout
    return False


async def _send_backend_request(
    backend: BackendConfig,
    proxied_payload: dict[str, Any],
    *,
    stream: bool,
) -> httpx.Response:
    if _HTTP_CLIENT is None:
        raise RuntimeError("HTTP client not initialized")

    request = _HTTP_CLIENT.build_request(
        "POST",
        f"{backend.base_url.rstrip('/')}/chat/completions",
        json=proxied_payload,
        headers=_build_headers(backend, None),
    )
    return await _HTTP_CLIENT.send(request, stream=stream)


@router.get("/health", response_model=None)
async def health() -> dict[str, Any]:
    config = _get_config()
    return {
        "ok": True,
        "version": "0.1.0",
        "config_loaded": True,
        "models": list(config.models.keys()),
        "backends": {name: {"type": b.type, "priority": b.priority} for name, b in config.backends.items()},
    }


@router.get("/v1/models", response_model=None)
async def list_models() -> dict[str, Any]:
    config = _get_config()
    data: list[dict[str, Any]] = []
    for alias, route in config.models.items():
        data.append(
            {
                "id": alias,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "llm-router",
            }
        )
    return {"object": "list", "data": data}


@router.get("/metrics", response_model=None)
async def metrics(
    request: Request,
    format: str | None = Query(default=None),
) -> dict[str, Any] | Response:
    snapshot = get_metrics().snapshot()
    accept = request.headers.get("accept", "")
    if format == "prometheus" or "text/plain" in accept:
        return Response(
            snapshot_to_prometheus(snapshot),
            media_type="text/plain; version=0.0.4",
        )
    return snapshot


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request,
    x_llm_client: str = Header(default="unknown"),
) -> StreamingResponse | JSONResponse | Response:
    config = _get_config()
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content=error_response("Invalid JSON", "invalid_request"))

    model_alias = payload.get("model")
    if not model_alias or not isinstance(model_alias, str):
        return JSONResponse(status_code=400, content=error_response("Missing or invalid 'model' field", "invalid_request"))

    if model_alias not in config.models:
        if config.runtime.unknown_model_strategy == "error":
            return _unknown_model_error(model_alias)
        # passthrough: use default backends
        backends = [name for name, b in sorted(config.backends.items(), key=lambda x: x[1].priority) if b.enabled]
    else:
        backends = _select_backends(model_alias, config)

    if not backends:
        return JSONResponse(status_code=503, content=error_response("No backends available", "no_backends"))

    request_id = str(uuid.uuid4())
    stream = payload.get("stream", False)
    client = x_llm_client
    fallback_used = False
    request_started = time.monotonic()

    policy = _route_policy(model_alias, config)

    for backend_index, backend_name in enumerate(backends):
        backend = config.backends[backend_name]
        provider_model = resolve_backend_model(model_alias, backend_name, config)
        proxied_payload = {**payload, "model": provider_model}

        max_attempts = max(policy.max_attempts_per_backend, 1)
        proxy_resp: httpx.Response | None = None
        try_next_backend = False
        for backend_attempt in range(1, max_attempts + 1):
            try:
                proxy_resp = await _send_backend_request(backend, proxied_payload, stream=stream)
                break
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
                _record_backend_failure(model_alias, backend_name, policy)
                metrics = get_metrics()  # type: ignore
                metrics.record_backend_failure(backend_name)
                is_last_backend = backend_index == len(backends) - 1
                duration_ms = (time.monotonic() - request_started) * 1000
                logger = _get_logger()
                if logger:
                    log_request(
                        logger,
                        request_id=request_id,
                        client=client,
                        path="/v1/chat/completions",
                        request_model=model_alias,
                        provider_model=provider_model,
                        backend=backend_name,
                        status_code=None,
                        limit_detected=False,
                        fallback_used=False,
                        duration_ms=duration_ms,
                    )
                if _should_retry_backend(exc, backend_attempt, policy):
                    continue
                if not is_last_backend and should_fallback(0, None, True, policy, config):
                    fallback_used = True
                    try_next_backend = True
                    break
                return JSONResponse(status_code=503, content=error_response("Connection error to all backends", "connection_error"))

        if try_next_backend:
            continue

        if proxy_resp is None:
            continue

        if proxy_resp.status_code < 300:
            _record_backend_success(model_alias, backend_name)
            # success
            status_code = proxy_resp.status_code
            duration_ms = (time.monotonic() - request_started) * 1000
            get_metrics().record_request(
                alias=model_alias,
                backend=backend_name,
                latency_ms=duration_ms,
                success=True,
                fallback_used=fallback_used,
                limit_detected=False,
            )
            response_headers = _router_response_headers(
                backend_name=backend_name,
                model_alias=model_alias,
                provider_model=provider_model,
                fallback_used=fallback_used,
            )
            logger = _get_logger()
            if logger:
                log_request(
                    logger,
                    request_id=request_id,
                    client=client,
                    path="/v1/chat/completions",
                    request_model=model_alias,
                    provider_model=provider_model,
                    backend=backend_name,
                    status_code=status_code,
                    limit_detected=False,
                    fallback_used=fallback_used,
                    duration_ms=(time.monotonic() - request_started) * 1000,
                )

            if stream:
                async def _stream_response(resp: httpx.Response) -> Any:
                    try:
                        async for chunk in resp.aiter_raw():
                            yield chunk
                    finally:
                        await resp.aclose()

                return StreamingResponse(
                    _stream_response(proxy_resp),
                    status_code=status_code,
                    headers=response_headers,
                    media_type="text/event-stream",
                )

            out_body = proxy_resp.content
            return JSONResponse(
                status_code=status_code,
                content=json.loads(out_body),
                headers=response_headers,
            )

        # error path – decide whether to fallback
        is_last = backend_index == len(backends) - 1

        resp_body = await proxy_resp.aread()
        limit_detected = looks_like_limit_error(proxy_resp.status_code, resp_body, config)
        fallbackable = should_fallback(proxy_resp.status_code, resp_body, False, policy, config)
        if fallbackable:
            _record_backend_failure(model_alias, backend_name, policy)
            get_metrics().record_cooldown(backend_name)
            get_metrics().record_backend_failure(backend_name)
        logger = _get_logger()
        if logger:
            log_request(
                logger,
                request_id=request_id,
                client=client,
                path="/v1/chat/completions",
                request_model=model_alias,
                provider_model=provider_model,
                backend=backend_name,
                status_code=proxy_resp.status_code,
                limit_detected=limit_detected,
                fallback_used=False,
                duration_ms=(time.monotonic() - request_started) * 1000,
            )
        get_metrics().record_request(
            alias=model_alias,
            backend=backend_name,
            latency_ms=(time.monotonic() - request_started) * 1000,
            success=False,
            fallback_used=fallback_used,
            limit_detected=limit_detected,
        )
        if not is_last and fallbackable:
            fallback_used = True
            continue

        # Final attempt failed or policy disallows another immediate backend.
        if policy.return_last_error_on_exhausted_backends:
            content_type = proxy_resp.headers.get("content-type")
            await proxy_resp.aclose()
            if stream:
                return _stream_backend_error_response(
                    status_code=proxy_resp.status_code,
                    body=resp_body,
                    backend_name=backend_name,
                    model_alias=model_alias,
                    provider_model=provider_model,
                    fallback_used=fallback_used,
                )
            return _backend_error_response(
                status_code=proxy_resp.status_code,
                body=resp_body,
                content_type=content_type,
                backend_name=backend_name,
                model_alias=model_alias,
                provider_model=provider_model,
                fallback_used=fallback_used,
            )

        # Legacy generic router error.
        if proxy_resp.status_code == 404 and config.runtime.unknown_model_strategy != "error":
            return JSONResponse(status_code=404, content=error_response("Model not found on backend", "model_not_found"))

        if proxy_resp.status_code >= 500:
            return JSONResponse(status_code=503, content=error_response("All backends failed", "all_backends_failed"))

    return JSONResponse(
        status_code=503,
        content=error_response("All backends failed", "all_backends_failed"),
    )
