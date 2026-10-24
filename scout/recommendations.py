"""Server-side recommendation lifecycle and approval audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class RecommendationState(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    EVALUATION_PENDING = "EVALUATION_PENDING"
    BACKTEST_COMPLETE = "BACKTEST_COMPLETE"
    VALIDATED_CANDIDATE = "VALIDATED_CANDIDATE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISMISSED = "DISMISSED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS = {
    RecommendationState.HYPOTHESIS: {RecommendationState.EVALUATION_PENDING, RecommendationState.DISMISSED},
    RecommendationState.EVALUATION_PENDING: {RecommendationState.BACKTEST_COMPLETE, RecommendationState.FAILED},
    RecommendationState.BACKTEST_COMPLETE: {RecommendationState.VALIDATED_CANDIDATE, RecommendationState.FAILED},
    RecommendationState.VALIDATED_CANDIDATE: {RecommendationState.AWAITING_APPROVAL, RecommendationState.REJECTED},
    RecommendationState.AWAITING_APPROVAL: {RecommendationState.APPROVED, RecommendationState.REJECTED, RecommendationState.DISMISSED},
}


@dataclass(frozen=True)
class RecommendationEvent:
    state: RecommendationState
    actor: str
    at: str
    reason: str


@dataclass
class Recommendation:
    recommendation_id: str
    hypothesis: str
    baseline: dict
    candidate: dict
    dataset_version: str
    strategy_version: str
    evidence: dict
    state: RecommendationState = RecommendationState.HYPOTHESIS
    audit: list[RecommendationEvent] = field(default_factory=list)

    def transition(self, state: RecommendationState, actor: str, reason: str) -> None:
        if not actor or not reason:
            raise ValueError("actor and reason are required")
        if state not in ALLOWED_TRANSITIONS.get(self.state, set()):
            raise ValueError(f"invalid recommendation transition {self.state} -> {state}")
        self.state = state
        self.audit.append(RecommendationEvent(state, actor, datetime.now(timezone.utc).isoformat(), reason))

    def approve(self, actor: str, reason: str) -> None:
        if self.state != RecommendationState.AWAITING_APPROVAL:
            raise ValueError("only recommendations awaiting approval can be approved")
        self.transition(RecommendationState.APPROVED, actor, reason)
