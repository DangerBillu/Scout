"""Paper portfolio accounting and deterministic risk checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .data import SUPPORTED_INSTRUMENTS


@dataclass(frozen=True)
class Position:
    instrument: str
    quantity: float
    average_price: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    portfolio_id: str
    as_of: str
    cash: float
    positions: tuple[Position, ...]
    equity: float
    exposure: float
    risk_events: tuple[str, ...]


class PaperPortfolio:
    def __init__(self, portfolio_id: str, cash: float, max_exposure: float = 1.0):
        if not portfolio_id or cash <= 0 or not 0 < max_exposure <= 1:
            raise ValueError("portfolio id, positive cash, and max_exposure in (0,1] are required")
        self.portfolio_id, self.cash, self.max_exposure = portfolio_id, float(cash), max_exposure
        self._positions: dict[str, Position] = {}
        self._events: list[str] = []

    def apply_paper_fill(self, instrument: str, quantity: float, price: float) -> None:
        """Record a simulated fill; this function has no broker/network path."""
        if instrument not in SUPPORTED_INSTRUMENTS or quantity == 0 or price <= 0:
            raise ValueError("supported instrument, nonzero quantity, and positive price are required")
        existing = self._positions.get(instrument, Position(instrument, 0.0, 0.0))
        new_quantity = existing.quantity + quantity
        if new_quantity < 0:
            raise ValueError("paper sell exceeds held quantity")
        if quantity > 0:
            total = existing.quantity * existing.average_price + quantity * price
            average = total / new_quantity
        else:
            average = existing.average_price if new_quantity else 0.0
        self.cash -= quantity * price
        if new_quantity:
            self._positions[instrument] = Position(instrument, new_quantity, average)
        else:
            self._positions.pop(instrument, None)

    def snapshot(self, prices: dict[str, float]) -> PortfolioSnapshot:
        market_values = {instrument: position.quantity * prices[instrument]
                         for instrument, position in self._positions.items() if instrument in prices}
        equity = self.cash + sum(market_values.values())
        exposure = sum(abs(value) for value in market_values.values())
        ratio = exposure / equity if equity > 0 else float("inf")
        events = list(self._events)
        if ratio > self.max_exposure:
            events.append(f"exposure limit breached: {ratio:.2%} > {self.max_exposure:.2%}")
        if any(instrument not in prices for instrument in self._positions):
            events.append("stale or missing mark price")
        self._events = events[-100:]
        return PortfolioSnapshot(self.portfolio_id, datetime.now(timezone.utc).isoformat(), self.cash,
                                 tuple(self._positions.values()), equity, exposure, tuple(events))
