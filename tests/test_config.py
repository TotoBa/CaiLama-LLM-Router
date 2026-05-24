from __future__ import annotations

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from llm_router.app import create_app
from llm_router.backends import resolve_backend_model
from llm_router.config import load_config


def test_load_example_config(example_config_path: Path):
    config = load_config(example_config_path)
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 18080
    assert "openai" in config.backends
    assert config.backends["openai"].priority == 10
    assert config.backends["hugging"].enabled is False


def test_load_dual_ollama_benchmark_example_config():
    config = load_config("configs/router.vm-dual-ollama.example.yaml")
    assert config.runtime.request_timeout_seconds is None
    assert sorted(config.backends) == ["ollama-local", "ollama-vm-a", "ollama-vm-b"]
    assert config.backends["ollama-vm-a"].api_key_env == "OLLAMA_VM_A_API_KEY"
    assert config.backends["ollama-vm-b"].api_key_env == "OLLAMA_VM_B_API_KEY"
    assert config.backends["ollama-local"].api_key_env is None
    assert config.models["deepseek-v4-pro:cloud"].backends == [
        "ollama-vm-a",
        "ollama-vm-b",
    ]
    assert config.models["hemanth/chessplayer:latest"].provider_model == (
        "hemanth/chessplayer:latest"
    )
    assert config.models["hemanth/chessplayer:latest"].backends == ["ollama-local"]
    assert config.models["starling-lm:7b"].routing_strategy == "priority"


def test_null_request_timeout_means_no_long_running_deadline(tmp_path: Path):
    config_content = """
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: null
  connect_timeout_seconds: 10

backends:
  openai:
    type: openai_compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    priority: 10

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "router.yaml"
    path.write_text(config_content)
    config = load_config(path)
    assert config.runtime.request_timeout_seconds is None
    assert config.runtime.connect_timeout_seconds == 10

    from llm_router.app import create_app

    app = create_app(config=config)
    timeout = app.state.httpx_client.timeout
    assert timeout.connect == 10
    assert timeout.read is None
    assert timeout.write is None
    assert timeout.pool is None


def test_missing_backend_in_model_config(tmp_path: Path):
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

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - missing_backend
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)
    with pytest.raises(ValueError, match="not in backends"):
        load_config(path)


def test_disabled_backend_in_model_config(tmp_path: Path):
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
    enabled: false

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)
    with pytest.raises(ValueError, match="disabled"):
        load_config(path)


def test_missing_policy_in_model_config(tmp_path: Path):
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

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: missing_policy

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)
    with pytest.raises(ValueError, match="not in policies"):
        load_config(path)


def test_invalid_routing_strategy(tmp_path: Path):
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

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: standard
    routing_strategy: random

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)
    with pytest.raises(ValueError, match="unsupported routing_strategy"):
        load_config(path)


def test_no_enabled_backends(tmp_path: Path):
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
    enabled: false

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)
    with pytest.raises(ValueError, match="disabled"):
        load_config(path)


def test_invalid_unknown_model_strategy(tmp_path: Path):
    config_content = """
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 600
  unknown_model_strategy: invalid

backends:
  openai:
    type: openai_compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    priority: 10

models:
  gpt-4o:
    provider_model: gpt-4o
    backends:
      - openai
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)
    with pytest.raises(ValueError, match="Invalid unknown_model_strategy"):
        load_config(path)


def test_backend_specific_model_mapping_is_validated(tmp_path: Path):
    config_content = """
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 600

backends:
  vm:
    type: openai_compatible
    base_url: http://vm.example/v1
    priority: 10
  pi:
    type: openai_compatible
    base_url: http://pi.example/v1
    priority: 20

models:
  chess-small:
    provider_model: fallback-model
    backend_models:
      vm: qwen2.5:14b
      pi: qwen2.5:7b
    backends:
      - vm
      - pi
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "router.yaml"
    path.write_text(config_content)

    config = load_config(path)
    assert resolve_backend_model("chess-small", "vm", config) == "qwen2.5:14b"
    assert resolve_backend_model("chess-small", "pi", config) == "qwen2.5:7b"


def test_backend_specific_model_mapping_rejects_unknown_backend(tmp_path: Path):
    config_content = """
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 600

backends:
  vm:
    type: openai_compatible
    base_url: http://vm.example/v1
    priority: 10

models:
  chess-small:
    provider_model: fallback-model
    backend_models:
      missing: qwen2.5:7b
    backends:
      - vm
    policy: standard

policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
    path = tmp_path / "bad_router.yaml"
    path.write_text(config_content)

    with pytest.raises(ValueError, match="unknown backend"):
        load_config(path)


def test_reload_config_on_request_refreshes_models(tmp_path: Path, monkeypatch):
    path = tmp_path / "router.yaml"

    def write_config(extra_model: bool) -> None:
        extra = """
  chess-large:
    provider_model: large-model
    backends:
      - local
    policy: standard
""" if extra_model else ""
        path.write_text(
            f"""
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  reload_config_on_request: true

backends:
  local:
    type: openai_compatible
    base_url: http://local.example/v1
    priority: 10

models:
  chess-small:
    provider_model: small-model
    backends:
      - local
    policy: standard
{extra}
policies:
  standard:
    max_attempts_per_backend: 1

limit_detection:
  status_codes: [429]
  body_markers: []

logging:
  level: INFO
"""
        )

    write_config(extra_model=False)
    monkeypatch.setenv("LLM_ROUTER_CONFIG", str(path))
    client = TestClient(create_app())
    assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["chess-small"]

    write_config(extra_model=True)
    model_ids = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert model_ids == ["chess-small", "chess-large"]


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_chess_alias_examples_include_dedicated_roles():
    repo_root = Path(__file__).resolve().parents[1]
    expected_models = {
        "chess-router": "deepseek-v4-flash:cloud",
        "chess-small": "gemma4:31b-cloud",
        "chess-large": "kimi-k2.6:cloud",
        "chess-task": "kimi-k2.6:cloud",
        "chess-coach": "gemma4:31b-cloud",
        "chess-analyst": "qwen3.5:397b-cloud",
        "chess-critic": "kimi-k2.6:cloud",
        "chess-vision": "gemma4:31b-cloud",
        "chess-scribe": "deepseek-v4-flash:cloud",
        "chess-researcher": "kimi-k2.6:cloud",
    }

    for config_name in (
        "router.chess-system.example.yaml",
        "router.vm-pi.example.yaml",
    ):
        config = load_config(repo_root / "configs" / config_name)
        for alias, provider_model in expected_models.items():
            assert alias in config.models
            assert config.models[alias].provider_model == provider_model
