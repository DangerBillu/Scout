"""Bounded, reproducible strategy-family discovery."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from .backtest import BacktestResult, run_backtest
from .data import Bar
from .strategy import MovingAverageCross


@dataclass(frozen=True)
class DiscoveryConfig:
    fast_periods: tuple[int, ...] = (5, 10, 20)
    slow_periods: tuple[int, ...] = (20, 30, 50)
    max_candidates: int = 10
    time_budget_seconds: float = 10.0
    approved_families: tuple[str, ...] = ("moving_average_crossover",)

    def validate(self) -> None:
        if self.max_candidates < 1 or self.max_candidates > 100:
            raise ValueError("max_candidates must be between 1 and 100")
        if self.time_budget_seconds <= 0 or self.time_budget_seconds > 300:
            raise ValueError("time budget must be between 0 and 300 seconds")
        if "moving_average_crossover" not in self.approved_families:
            raise ValueError("the only implemented discovery family is moving_average_crossover")


@dataclass(frozen=True)
class DiscoveryResult:
    status: str
    candidates: tuple[BacktestResult, ...]
    rejected: tuple[str, ...]
    configuration: DiscoveryConfig


def discover(bars: tuple[Bar, ...], instrument: str, timeframe: str, capital: float,
             dataset_version: str, config: DiscoveryConfig = DiscoveryConfig()) -> DiscoveryResult:
    config.validate()
    started = monotonic()
    candidates: list[BacktestResult] = []
    rejected: list[str] = []
    for fast in config.fast_periods:
        for slow in config.slow_periods:
            if len(candidates) >= config.max_candidates or monotonic() - started >= config.time_budget_seconds:
                return DiscoveryResult("TIME_BUDGET_EXHAUSTED" if monotonic() - started >= config.time_budget_seconds else "COMPLETE",
                                       tuple(candidates), tuple(rejected), config)
            try:
                strategy = MovingAverageCross(instrument, timeframe, fast, slow, initial_capital=capital)
                candidates.append(run_backtest(bars, strategy, dataset_version))
            except ValueError as exc:
                rejected.append(f"fast={fast},slow={slow}: {exc}")
    return DiscoveryResult("COMPLETE", tuple(candidates), tuple(rejected), config)
