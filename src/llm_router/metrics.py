"""Privacy-safe in-memory metrics for the LLM Router.

No prompt/response content is ever recorded.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestMetrics:
    total_requests: int = 0
    total_fallbacks: int = 0
    total_success: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    alias_counts: dict[str, int] = field(default_factory=dict)
    backend_counts: dict[str, int] = field(default_factory=dict)
    cooldown_counts: dict[str, int] = field(default_factory=dict)
    backend_failure_counts: dict[str, int] = field(default_factory=dict)
    limit_detection_counts: dict[str, int] = field(default_factory=dict)

    def record_request(
        self,
        *,
        alias: str,
        backend: str,
        latency_ms: float,
        success: bool,
        fallback_used: bool,
        limit_detected: bool,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.total_requests += 1
        self.alias_counts[alias] = self.alias_counts.get(alias, 0) + 1
        self.backend_counts[backend] = self.backend_counts.get(backend, 0) + 1
        self.total_latency_ms += latency_ms
        if success:
            self.total_success += 1
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_tokens += total_tokens
        else:
            self.total_errors += 1
        if fallback_used:
            self.total_fallbacks += 1
        if limit_detected:
            self.limit_detection_counts[backend] = self.limit_detection_counts.get(backend, 0) + 1

    def record_cooldown(self, backend_name: str) -> None:
        self.cooldown_counts[backend_name] = self.cooldown_counts.get(backend_name, 0) + 1

    def record_backend_failure(self, backend_name: str) -> None:
        self.backend_failure_counts[backend_name] = self.backend_failure_counts.get(backend_name, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "timestamp": time.time(),
            "requests": {
                "total": self.total_requests,
                "success": self.total_success,
                "errors": self.total_errors,
                "fallbacks": self.total_fallbacks,
                "average_latency_ms": round(self.total_latency_ms / max(self.total_requests, 1), 2),
            },
            "usage": {
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_tokens,
            },
            "aliases": self.alias_counts,
            "backends": self.backend_counts,
            "cooldowns": self.cooldown_counts,
            "backend_failures": self.backend_failure_counts,
            "limit_detections": self.limit_detection_counts,
        }


_METRICS: RequestMetrics | None = None


def init_metrics() -> RequestMetrics:
    global _METRICS
    _METRICS = RequestMetrics()
    return _METRICS


def get_metrics() -> RequestMetrics:
    if _METRICS is None:
        return init_metrics()
    return _METRICS


def snapshot_to_prometheus(snapshot: dict[str, Any]) -> str:
    """Render a privacy-safe Prometheus text exposition from a metrics snapshot."""
    requests = snapshot.get("requests", {})
    usage = snapshot.get("usage", {})
    lines = [
        "# HELP llm_router_requests_total Total proxied chat completion requests.",
        "# TYPE llm_router_requests_total counter",
        f"llm_router_requests_total {requests.get('total', 0)}",
        "# HELP llm_router_requests_success_total Successful proxied requests.",
        "# TYPE llm_router_requests_success_total counter",
        f"llm_router_requests_success_total {requests.get('success', 0)}",
        "# HELP llm_router_requests_errors_total Failed proxied requests.",
        "# TYPE llm_router_requests_errors_total counter",
        f"llm_router_requests_errors_total {requests.get('errors', 0)}",
        "# HELP llm_router_requests_fallbacks_total Requests that used fallback.",
        "# TYPE llm_router_requests_fallbacks_total counter",
        f"llm_router_requests_fallbacks_total {requests.get('fallbacks', 0)}",
        "# HELP llm_router_request_average_latency_ms Average request latency.",
        "# TYPE llm_router_request_average_latency_ms gauge",
        f"llm_router_request_average_latency_ms {requests.get('average_latency_ms', 0)}",
        "# HELP llm_router_usage_prompt_tokens_total Aggregated prompt tokens from successful requests.",
        "# TYPE llm_router_usage_prompt_tokens_total counter",
        f"llm_router_usage_prompt_tokens_total {usage.get('prompt_tokens', 0)}",
        "# HELP llm_router_usage_completion_tokens_total Aggregated completion tokens from successful requests.",
        "# TYPE llm_router_usage_completion_tokens_total counter",
        f"llm_router_usage_completion_tokens_total {usage.get('completion_tokens', 0)}",
        "# HELP llm_router_usage_total_tokens_total Aggregated total tokens from successful requests.",
        "# TYPE llm_router_usage_total_tokens_total counter",
        f"llm_router_usage_total_tokens_total {usage.get('total_tokens', 0)}",
    ]

    for alias, count in sorted(snapshot.get("aliases", {}).items()):
        lines.append(f'llm_router_alias_requests_total{{alias="{alias}"}} {count}')
    for backend, count in sorted(snapshot.get("backends", {}).items()):
        lines.append(f'llm_router_backend_requests_total{{backend="{backend}"}} {count}')
    for backend, count in sorted(snapshot.get("cooldowns", {}).items()):
        lines.append(f'llm_router_backend_cooldowns_total{{backend="{backend}"}} {count}')
    for backend, count in sorted(snapshot.get("backend_failures", {}).items()):
        lines.append(f'llm_router_backend_failures_total{{backend="{backend}"}} {count}')
    for backend, count in sorted(snapshot.get("limit_detections", {}).items()):
        lines.append(f'llm_router_limit_detections_total{{backend="{backend}"}} {count}')

    return "\n".join(lines) + "\n"
