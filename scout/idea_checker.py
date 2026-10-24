"""Beginner-oriented strategy idea checker; deterministic and paper-only."""

from __future__ import annotations

from dataclasses import dataclass

from .data import SUPPORTED_INSTRUMENTS


@dataclass(frozen=True)
class IdeaCheckResult:
    verdict: str
    summary: str
    checks: tuple[dict[str, str], ...]
    warnings: tuple[str, ...]


def check_idea(*, instrument: str, timeframe: str, entry_rule: str, exit_rule: str,
               stop_loss_pct: float, take_profit_pct: float, risk_per_trade_pct: float) -> IdeaCheckResult:
    checks: list[dict[str, str]] = []
    warnings: list[str] = []
    failures: list[str] = []
    if instrument not in SUPPORTED_INSTRUMENTS:
        failures.append("instrument is not supported")
    if timeframe not in {"1m", "5m", "15m", "1h", "1d"}:
        failures.append("timeframe is not supported")
    if not entry_rule.strip() or not exit_rule.strip():
        failures.append("entry and exit rules are required")
    forbidden = ("guaranteed", "sure profit", "risk-free", "live order", "place an order")
    if any(term in f"{entry_rule} {exit_rule}".lower() for term in forbidden):
        failures.append("the idea contains an unsafe guarantee or live-trading instruction")
    if stop_loss_pct <= 0 or take_profit_pct <= 0:
        failures.append("stop-loss and take-profit must be positive")
    if risk_per_trade_pct <= 0 or risk_per_trade_pct > 5:
        failures.append("risk per trade must be greater than 0 and no more than 5%")
    if risk_per_trade_pct > 2:
        warnings.append("beginner guardrail: risk above 2% per trade needs extra review")
    if stop_loss_pct > 0 and take_profit_pct > 0:
        ratio = take_profit_pct / stop_loss_pct
        if ratio < 1:
            warnings.append(f"reward/risk is {ratio:.2f}; the target is smaller than the stop")
        checks.append({"name": "reward_risk", "status": "pass" if ratio >= 1.2 else "warning",
                       "detail": f"{ratio:.2f} reward-to-risk"})
    checks.extend(({"name": "paper_only", "status": "pass", "detail": "no broker order path"},
                   {"name": "bounded_rules", "status": "pass" if not failures else "fail",
                    "detail": "rules are checked before backtesting"}))
    if failures:
        checks.extend({"name": "input", "status": "fail", "detail": failure} for failure in failures)
        return IdeaCheckResult("REJECTED", "; ".join(failures), tuple(checks), tuple(warnings))
    if warnings:
        return IdeaCheckResult("NEEDS_REVIEW", "The idea can be backtested after reviewing the warnings.", tuple(checks), tuple(warnings))
    return IdeaCheckResult("READY_FOR_BACKTEST", "The idea has the required bounded risk fields.", tuple(checks), tuple())
