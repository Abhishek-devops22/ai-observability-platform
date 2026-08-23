"""Runtime configuration for the MCP server, loaded from environment
variables (or a local .env file — see .env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Backend endpoints
    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"
    tempo_url: str = "http://localhost:3200"

    # Kubernetes
    kubeconfig_path: str | None = None  # None => use in-cluster config / default kubeconfig
    default_namespace: str = "default"

    # Safety: the README's stated default is "read-only MCP access by
    # default". Mutating tools (restart_deployment, scale_deployment) check
    # this flag and refuse to act unless explicitly enabled.
    allow_mutations: bool = False

    # HTTP client behavior
    request_timeout_seconds: float = 15.0

    # MCP transport
    transport: str = "stdio"  # "stdio" or "streamable-http"
    http_host: str = "0.0.0.0"
    http_port: int = 8080


settings = Settings()
