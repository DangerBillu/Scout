"""Deterministic health checks that work when a model is unavailable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .data import DatasetInfo
from .portfolio import PortfolioSnapshot


@dataclass(frozen=True)
class HealthAlert:
    severity: str
    code: str
    message: str


def check_health(snapshot: PortfolioSnapshot, dataset: DatasetInfo, *, now: datetime | None = None,
                 max_age: timedelta = timedelta(hours=24)) -> tuple[HealthAlert, ...]:
    now = now or datetime.now(timezone.utc)
    alerts: list[HealthAlert] = []
    if snapshot.risk_events:
        alerts.extend(HealthAlert("critical", "RISK_LIMIT", event) for event in snapshot.risk_events)
    if dataset.ingested_at.tzinfo is None or now - dataset.ingested_at > max_age:
        alerts.append(HealthAlert("warning", "STALE_DATA", "market dataset is older than configured freshness limit"))
    return tuple(alerts)
