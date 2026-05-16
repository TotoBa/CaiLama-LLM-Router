from __future__ import annotations

from pydantic import BaseModel, RootModel


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 18080
    require_api_key: bool = False
    api_key_env: str | None = None


class BackendConfig(BaseModel):
    type: str = "openai_compatible"
    base_url: str
    api_key_env: str | None = None
    priority: int = 100
    enabled: bool = True


class ModelRouteConfig(BaseModel):
    provider_model: str
    backends: list[str] | None = None
    backend_models: dict[str, str] | None = None
    policy: str = "standard"
    routing_strategy: str = "priority"


class PolicyConfig(BaseModel):
    max_attempts_per_backend: int = 1
    max_backend_failures_before_cooldown: int = 2
    backend_cooldown_seconds: int = 300
    retry_on_connection_error: bool = True
    retry_on_timeout: bool = False
    fallback_on_limit: bool = True
    fallback_on_5xx: bool = False
    fallback_on_4xx: bool = False
    fallback_on_model_not_found: bool = False
    timeout_seconds: int = 300


class LimitDetectionConfig(BaseModel):
    status_codes: list[int] = [402, 403, 429]
    body_markers: list[str] = []


class LoggingConfig(BaseModel):
    level: str = "INFO"
    jsonl_path: str | None = None
    log_request_body: bool = False
    log_response_body: bool = False
    log_prompt_chars: bool = False
    log_headers: bool = False


class RuntimeConfig(BaseModel):
    request_timeout_seconds: int = 600
    connect_timeout_seconds: int = 10
    reload_config_on_request: bool = False
    unknown_model_strategy: str = "error"


class RouterConfig(RootModel[dict[str, object]]):
    root: dict[str, object]

    @property
    def server(self) -> ServerConfig:
        return ServerConfig.model_validate(self.root.get("server", {}))

    @property
    def runtime(self) -> RuntimeConfig:
        return RuntimeConfig.model_validate(self.root.get("runtime", {}))

    @property
    def backends(self) -> dict[str, BackendConfig]:
        raw = self.root.get("backends", {})
        return {k: BackendConfig.model_validate(v) for k, v in raw.items()}

    @property
    def models(self) -> dict[str, ModelRouteConfig]:
        raw = self.root.get("models", {})
        return {k: ModelRouteConfig.model_validate(v) for k, v in raw.items()}

    @property
    def policies(self) -> dict[str, PolicyConfig]:
        raw = self.root.get("policies", {})
        return {k: PolicyConfig.model_validate(v) for k, v in raw.items()}

    @property
    def limit_detection(self) -> LimitDetectionConfig:
        return LimitDetectionConfig.model_validate(self.root.get("limit_detection", {}))

    @property
    def logging(self) -> LoggingConfig:
        return LoggingConfig.model_validate(self.root.get("logging", {}))
