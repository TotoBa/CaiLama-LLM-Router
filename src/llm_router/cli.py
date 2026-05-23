from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
import typer
import uvicorn

from llm_router.config import load_config
from llm_router.schemas import RouterConfig

cli = typer.Typer()

DEFAULT_CONFIG_PATH = Path(os.environ.get("LLM_ROUTER_CONFIG", "configs/router.local.yaml"))


def _load(path: Path) -> RouterConfig:
    if not path.is_absolute():
        path = Path.cwd() / path
    return load_config(path)


@cli.command()
def serve(
    config: Path = typer.Option(default=DEFAULT_CONFIG_PATH, help="Path to config YAML"),
    host: str = typer.Option(default="127.0.0.1", help="Bind host"),
    port: int = typer.Option(default=18080, help="Bind port"),
) -> None:
    """Start the LLM Router server."""
    os.environ["LLM_ROUTER_CONFIG"] = str(config.resolve())
    uvicorn.run("llm_router.app:app", host=host, port=port, log_level="info")


def _check_env_vars(cfg: RouterConfig) -> list[str]:
    """Check that referenced API key env vars are present in the environment."""
    missing: list[str] = []
    for name, backend in cfg.backends.items():
        if backend.api_key_env and backend.api_key_env not in os.environ:
            missing.append(
                f"Backend '{name}' references env var '{backend.api_key_env}' which is not set"
            )
    if cfg.server.require_api_key and cfg.server.api_key_env:
        if cfg.server.api_key_env not in os.environ:
            missing.append(
                f"Server requires API key env var '{cfg.server.api_key_env}' which is not set"
            )
    return missing


@cli.command()
def check_config(
    config: Path = typer.Option(default=DEFAULT_CONFIG_PATH, help="Path to config YAML"),
) -> None:
    """Validate configuration file and referenced environment variables."""
    try:
        cfg = _load(config)
        typer.echo("Configuration OK")
        typer.echo(f"Models: {list(cfg.models.keys())}")
        typer.echo(f"Backends: {list(cfg.backends.keys())}")
        typer.echo(f"Policies: {list(cfg.policies.keys())}")
        env_issues = _check_env_vars(cfg)
        if env_issues:
            for issue in env_issues:
                typer.echo(f"  ⚠ {issue}", err=True)
    except Exception as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(1)


@cli.command()
def list_models(
    config: Path = typer.Option(default=DEFAULT_CONFIG_PATH, help="Path to config YAML"),
) -> None:
    """List configured model routes."""
    cfg = _load(config)
    for alias, route in cfg.models.items():
        typer.echo(f"{alias} -> provider_model={route.provider_model} policy={route.policy}")


@cli.command()
def test_backends(
    config: Path = typer.Option(default=DEFAULT_CONFIG_PATH, help="Path to config YAML"),
) -> None:
    """Test connectivity to all configured backends."""
    cfg = _load(config)

    async def _check() -> None:
        async with httpx.AsyncClient() as client:
            for name, backend in cfg.backends.items():
                try:
                    resp = await client.get(
                        f"{backend.base_url.rstrip('/')}/models",
                        timeout=10,
                    )
                    typer.echo(f"{name}: {resp.status_code} {resp.status_code < 300}")
                except Exception as exc:
                    typer.echo(f"{name}: ERROR {exc}")

    asyncio.run(_check())


@cli.command()
def smoke_test(
    config: Path = typer.Option(default=DEFAULT_CONFIG_PATH, help="Path to config YAML"),
    model: str = typer.Option(..., help="Model alias to test"),
    prompt: str = typer.Option(default="Say hello in one word.", help="Prompt to send"),
) -> None:
    """Send a single chat completion to test end-to-end routing."""
    cfg = _load(config)
    base_url = f"http://{cfg.server.host}:{cfg.server.port}"
    headers: dict[str, str] = {}
    if cfg.server.require_api_key and cfg.server.api_key_env:
        key = os.environ.get(cfg.server.api_key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"

    async def _run() -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                },
                headers=headers,
                timeout=60,
            )
            typer.echo(f"Status: {resp.status_code}")
            typer.echo(json.dumps(resp.json(), indent=2))

    asyncio.run(_run())


def main() -> None:
    cli()


# ── Usage formatting (separate from CLI for testability) ──

def _format_usage(data: dict[str, Any]) -> str:
    """Pretty-print aggregated router usage/diagnostics."""
    requests = data.get("requests", {})
    usage = data.get("usage", {})
    lines: list[str] = [
        f"Requests  total:    {requests.get('total', 0)}",
        f"  success:          {requests.get('success', 0)}",
        f"  errors:           {requests.get('errors', 0)}",
        f"  fallbacks:        {requests.get('fallbacks', 0)}",
        f"  avg latency:      {requests.get('average_latency_ms', 0)} ms",
        "",
        "Usage tokens",
        f"  prompt:           {usage.get('prompt_tokens', 0)}",
        f"  completion:       {usage.get('completion_tokens', 0)}",
        f"  total:            {usage.get('total_tokens', 0)}",
    ]

    aliases = data.get("aliases", {})
    if aliases:
        lines.append("")
        lines.append("Alias distribution")
        for alias, count in sorted(aliases.items()):
            lines.append(f"  {alias}: {count}")

    backends = data.get("backends", {})
    if backends:
        lines.append("")
        lines.append("Backend distribution")
        for backend, count in sorted(backends.items()):
            lines.append(f"  {backend}: {count}")

    cooldowns = data.get("cooldowns", {})
    if cooldowns:
        lines.append("")
        lines.append("Cooldowns")
        for backend, count in sorted(cooldowns.items()):
            lines.append(f"  {backend}: {count}")

    failures = data.get("backend_failures", {})
    if failures:
        lines.append("")
        lines.append("Backend failures")
        for backend, count in sorted(failures.items()):
            lines.append(f"  {backend}: {count}")

    limit_dets = data.get("limit_detections", {})
    if limit_dets:
        lines.append("")
        lines.append("Limit detections")
        for backend, count in sorted(limit_dets.items()):
            lines.append(f"  {backend}: {count}")

    return "\n".join(lines)


async def _usage_impl(metrics_url: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(metrics_url, timeout=10)
        if resp.status_code != 200:
            raise typer.Exit(1)
        return _format_usage(resp.json())


@cli.command()
def usage(
    metrics_url: str = typer.Option(default="http://127.0.0.1:18080/metrics", help="URL for /metrics endpoint"),
) -> None:
    """Show aggregated router usage (requests, fallbacks, latencies, tokens, distributions)."""
    try:
        output = asyncio.run(_usage_impl(metrics_url))
    except Exception as exc:
        typer.echo(f"Error fetching metrics: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(output)


# ── Benchmark export (privacy-safe JSON for CaiLama-Master) ──

def _build_benchmark(data: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timezone
    requests = data.get("requests", {})
    usage = data.get("usage", {})
    total = max(requests.get("total", 0), 1)
    return {
        "git_ref": None,
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requests": {
            "total": requests.get("total", 0),
            "success": requests.get("success", 0),
            "errors": requests.get("errors", 0),
            "fallbacks": requests.get("fallbacks", 0),
            "average_latency_ms": requests.get("average_latency_ms", 0.0),
        },
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "error_rate": round(requests.get("errors", 0) / total, 4),
        "fallback_rate": round(requests.get("fallbacks", 0) / total, 4),
        "aliases": data.get("aliases", {}),
        "backends": data.get("backends", {}),
        "cooldowns": data.get("cooldowns", {}),
        "backend_failures": data.get("backend_failures", {}),
        "limit_detections": data.get("limit_detections", {}),
    }


async def _benchmark_impl(metrics_url: str, git_ref: str | None) -> str:
    import subprocess
    async with httpx.AsyncClient() as client:
        resp = await client.get(metrics_url, timeout=10)
        if resp.status_code != 200:
            raise typer.Exit(1)
        bench = _build_benchmark(resp.json())
        if git_ref is None:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    git_ref = result.stdout.strip()[:12]
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        bench["git_ref"] = git_ref
        return json.dumps(bench, indent=2)


@cli.command()
def benchmark_export(
    metrics_url: str = typer.Option(default="http://127.0.0.1:18080/metrics", help="URL for /metrics endpoint"),
    git_ref: str = typer.Option(default=None, help="Git ref of the codebase (auto-detected if available)"),
) -> None:
    """Export privacy-safe benchmark JSON for CaiLama-Master."""
    try:
        output = asyncio.run(_benchmark_impl(metrics_url, git_ref))
    except Exception as exc:
        typer.echo(f"Error fetching metrics: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(output)


if __name__ == "__main__":
    main()
