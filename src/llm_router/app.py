"""FastAPI application factory for the LLM Router."""

from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pathlib import Path

from llm_router.config import load_config
from llm_router.errors import RouterError, error_response
from llm_router.logging_jsonl import init_logger
from llm_router.metrics import init_metrics
from llm_router.openai_compat import router as openai_router, set_config, set_http_client, set_logger
from llm_router.schemas import RouterConfig


def _optional_timeout_seconds(value: int | None) -> float | None:
    if value is None or value <= 0:
        return None
    return float(value)


def create_app(config: RouterConfig | None = None) -> FastAPI:
    """Create a FastAPI app with the given (or loaded) configuration."""
    config_path: Path | None = None
    if config is None:
        import os
        config_path = Path(os.environ.get("LLM_ROUTER_CONFIG", "configs/router.local.yaml"))
        config = load_config(config_path)

    logger = init_logger(config)
    httpx_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            timeout=_optional_timeout_seconds(config.runtime.request_timeout_seconds),
            connect=_optional_timeout_seconds(config.runtime.connect_timeout_seconds),
        )
    )

    set_config(config, config_path=config_path)
    set_http_client(httpx_client)
    set_logger(logger)
    init_metrics()

    app = FastAPI(title="LLM Router", version="0.1.0")
    app.include_router(openai_router)

    @app.exception_handler(RouterError)
    async def _router_error_handler(_request, exc: RouterError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.message, exc.error_type),
        )

    # expose config and client so CLI / tests can access them
    app.state.config = config
    app.state.config_path = config_path
    app.state.httpx_client = httpx_client
    app.state.logger = logger

    return app


# module-level app for ASGI servers
try:
    app = create_app()
except Exception:
    # during import time config may not exist – will be created by create_app call
    app = FastAPI(title="LLM Router", version="0.1.0")
