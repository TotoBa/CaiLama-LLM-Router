from __future__ import annotations

from llm_router.schemas import RouterConfig


def resolve_backend_model(model_alias: str, backend_name: str, config: RouterConfig) -> str:
    route = config.models.get(model_alias)
    if route is None:
        return model_alias
    if route.backend_models and backend_name in route.backend_models:
        return route.backend_models[backend_name]
    return route.provider_model


def backend_order(model_alias: str, config: RouterConfig) -> list[str]:
    route = config.models.get(model_alias)
    if route and route.backends is not None:
        return [b for b in route.backends if config.backends[b].enabled]
    return [
        name for name, backend in sorted(config.backends.items(), key=lambda x: x[1].priority)
        if backend.enabled
    ]
