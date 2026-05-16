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
