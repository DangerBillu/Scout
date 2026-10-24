"""Bounded model adapter interface; calculations never depend on it."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import request

from .config import ModelConfig


@dataclass(frozen=True)
class ModelResult:
    text: str
    model_id: str
    provider: str
    attempts: int
    warnings: tuple[str, ...] = ()


class ModelAdapter(Protocol):
    def generate(self, prompt: str, *, schema: dict[str, Any] | None = None) -> ModelResult: ...


class HuggingFaceAdapter:
    """Adapter for providers exposing the Hugging Face inference API.

    The adapter is opt-in: no token means a clear error, and no fallback model
    is selected unless it is explicitly configured.
    """

    def __init__(self, config: ModelConfig, endpoint: str | None = None):
        self.config = config
        self.endpoint = endpoint or "https://api-inference.huggingface.co/models/" + config.model_id

    def generate(self, prompt: str, *, schema: dict[str, Any] | None = None) -> ModelResult:
        if not self.config.token:
            raise RuntimeError("HF_TOKEN is not configured")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        body = {"inputs": prompt, "parameters": {"return_full_text": False}}
        if schema:
            body["parameters"]["response_format"] = {"type": "json_schema", "json_schema": schema}
        headers = {"Authorization": f"Bearer {self.config.token}", "Content-Type": "application/json"}
        last_error = "provider error"
        for attempt in range(self.config.max_retries + 1):
            try:
                req = request.Request(self.endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
                with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                    raw = response.read(self.config.max_response_chars + 1)
                if len(raw) > self.config.max_response_chars:
                    raise RuntimeError("model response exceeded configured size limit")
                decoded = json.loads(raw.decode("utf-8"))
                text = self._extract_text(decoded)
                if schema:
                    json.loads(text)
                return ModelResult(text, self.config.model_id, self.config.provider, attempt + 1)
            except Exception as exc:  # provider failures must not crash quantitative services
                last_error = str(exc)
                if attempt < self.config.max_retries:
                    time.sleep(min(0.25 * (2 ** attempt), 2.0))
        raise RuntimeError(f"model provider failed after {self.config.max_retries + 1} attempts: {last_error}")

    @staticmethod
    def _extract_text(decoded: Any) -> str:
        if isinstance(decoded, list) and decoded and isinstance(decoded[0], dict):
            text = decoded[0].get("generated_text")
        elif isinstance(decoded, dict):
            text = decoded.get("generated_text") or decoded.get("text")
        else:
            text = None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("provider response did not contain generated text")
        return text


class UnavailableModel:
    """Explicit model-unavailable implementation used by deterministic flows."""

    def generate(self, prompt: str, *, schema: dict[str, Any] | None = None) -> ModelResult:
        raise RuntimeError("model is unavailable; deterministic services remain usable")
