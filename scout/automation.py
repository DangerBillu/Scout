"""Bounded monitoring job configuration; scheduling is explicit and paper-only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class AutomationJob:
    job_id: str
    name: str
    interval_seconds: int
    enabled: bool = True
    last_run: str | None = None
    last_status: str = "NEVER_RUN"

    def __post_init__(self) -> None:
        if not self.job_id or not self.name or not 60 <= self.interval_seconds <= 86_400:
            raise ValueError("job id/name and interval between 60 seconds and 24 hours are required")

    def request_run(self, *, actor: str) -> dict[str, str]:
        if not actor:
            raise ValueError("actor is required")
        if not self.enabled:
            raise PermissionError("automation is disabled")
        self.last_run = datetime.now(timezone.utc).isoformat()
        self.last_status = "REQUESTED"
        return {"job_id": self.job_id, "status": self.last_status, "requested_by": actor}

    def set_enabled(self, enabled: bool, *, actor: str) -> None:
        if not actor:
            raise ValueError("actor is required")
        self.enabled = bool(enabled)
