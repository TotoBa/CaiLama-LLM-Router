from __future__ import annotations

import pytest
from pathlib import Path

from llm_router.config import load_config


def test_load_example_config(example_config_path: Path):
    config = load_config(example_config_path)
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 18080
    assert "openai" in config.backends
    assert config.backends["openai"].priority == 10
    assert config.backends["hugging"].enabled is False


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


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_chess_alias_examples_include_dedicated_roles():
    repo_root = Path(__file__).resolve().parents[1]
    expected_models = {
        "chess-router": "deepseek-v4-flash:cloud",
        "chess-small": "deepseek-v4-flash:cloud",
        "chess-large": "gemma4:31b-cloud",
        "chess-task": "deepseek-v4-pro:cloud",
        "chess-coach": "gemma4:31b-cloud",
        "chess-analyst": "qwen3.5:397b-cloud",
        "chess-critic": "deepseek-v4-pro:cloud",
        "chess-vision": "gemma4:31b-cloud",
        "chess-scribe": "deepseek-v4-flash:cloud",
        "chess-researcher": "deepseek-v4-pro:cloud",
    }

    for config_name in (
        "router.chess-system.example.yaml",
        "router.vm-pi.example.yaml",
    ):
        config = load_config(repo_root / "configs" / config_name)
        for alias, provider_model in expected_models.items():
            assert alias in config.models
            assert config.models[alias].provider_model == provider_model
