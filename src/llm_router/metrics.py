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
    ) -> None:
        self.total_requests += 1
        self.alias_counts[alias] = self.alias_counts.get(alias, 0) + 1
        self.backend_counts[backend] = self.backend_counts.get(backend, 0) + 1
        self.total_latency_ms += latency_ms
        if success:
            self.total_success += 1
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
