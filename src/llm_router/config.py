from __future__ import annotations

import os
from pathlib import Path

import yaml

from llm_router.schemas import BackendConfig, RouterConfig


def load_config(path: Path | str) -> RouterConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file '{path}' not found.")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    config = RouterConfig(**raw)

    # Validate model references
    for model_alias, model_conf in config.models.items():
        if model_conf.backends:
            for backend_name in model_conf.backends:
                if backend_name not in config.backends:
                    raise ValueError(
                        f"Model '{model_alias}' references backend '{backend_name}' which is not in backends config."
                    )
                if not config.backends[backend_name].enabled:
                    raise ValueError(
                        f"Model '{model_alias}' references disabled backend '{backend_name}'."
                    )

        if model_conf.backend_models:
            for backend_name in model_conf.backend_models:
                if backend_name not in config.backends:
                    raise ValueError(
                        f"Model '{model_alias}' references backend model for "
                        f"unknown backend '{backend_name}'."
                    )

        if model_conf.policy not in config.policies:
            raise ValueError(
                f"Model '{model_alias}' references policy '{model_conf.policy}' which is not in policies config."
            )
        if model_conf.routing_strategy not in {"priority", "round_robin"}:
            raise ValueError(
                f"Model '{model_alias}' has unsupported routing_strategy "
                f"'{model_conf.routing_strategy}'."
            )

    # Ensure at least one enabled backend
    enabled_backends = [b for b in config.backends.values() if b.enabled]
    if not enabled_backends:
        raise ValueError("At least one enabled backend is required in configuration.")

    # Validate runtime options
    strategy = config.runtime.unknown_model_strategy
    if strategy not in {"error", "passthrough"}:
        raise ValueError(
            f"Invalid unknown_model_strategy '{strategy}'. "
            f"Must be either 'error' or 'passthrough'."
        )

    return config


def resolve_api_key(backend: BackendConfig) -> str | None:
    if backend.api_key_env:
        return os.environ.get(backend.api_key_env)
    return None
