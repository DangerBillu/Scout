"""Validated backend configuration. Secrets are never exposed to the browser."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _load_local_env() -> None:
    """Load simple KEY=value pairs without exposing them to the UI."""
    path = Path(os.getenv("SCOUT_ENV_FILE", ".env"))
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str
    fallback_model_id: str | None
    fallback_provider: str | None
    token: str | None
    max_retries: int
    timeout_seconds: int
    max_response_chars: int = 20_000

    @classmethod
    def from_env(cls) -> "ModelConfig":
        _load_local_env()
        model_id = os.getenv("HF_MODEL_ID", "Qwen/Qwen3-4B-Thinking-2507").strip()
        provider = os.getenv("HF_PROVIDER", "auto").strip()
        if not model_id:
            raise ValueError("HF_MODEL_ID cannot be empty")
        if not provider:
            raise ValueError("HF_PROVIDER cannot be empty")
        fallback = os.getenv("HF_FALLBACK_MODEL_ID", "").strip() or None
        fallback_provider = os.getenv("HF_FALLBACK_PROVIDER", "").strip() or None
        # A fallback model may be recorded for comparison while its provider is
        # intentionally unset. It must never be selected implicitly by the adapter.
        return cls(model_id, provider, fallback, fallback_provider, os.getenv("HF_TOKEN") or None,
                   _int_env("HF_MAX_RETRIES", 2, 0, 5),
                   _int_env("HF_REQUEST_TIMEOUT_SECONDS", 60, 1, 300))

    def public(self) -> dict[str, object]:
        """Return safe settings for the Integrations/Settings UI."""
        return {"model_id": self.model_id, "provider": self.provider,
                "fallback_model_id": self.fallback_model_id,
                "fallback_provider": self.fallback_provider,
                "token_configured": bool(self.token),
                "max_retries": self.max_retries, "timeout_seconds": self.timeout_seconds}
