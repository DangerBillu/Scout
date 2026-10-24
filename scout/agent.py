"""Local agent boundary for the UI.

External model calls are intentionally disabled in the browser path. This keeps
spoken/user-entered prompts local until an approved, authenticated backend model
boundary is configured.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentReply:
    text: str
    available: bool
    model_id: str | None = None
    provider: str | None = None
    warnings: tuple[str, ...] = ()


def reply(message: str) -> AgentReply:
    if not isinstance(message, str) or not message.strip() or len(message) > 4_000:
        raise ValueError("message must be between 1 and 4,000 characters")
    return AgentReply(
        "The AI agent is not connected in this local build. I kept your message local. "
        "Use Idea Checker, Backtest, or Paper Portfolio for deterministic Scout tools.",
        False,
        warnings=("No model-backed answer was generated or sent to an external provider.",),
    )
