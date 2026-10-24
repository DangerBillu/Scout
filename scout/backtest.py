"""Reproducible next-open-fill, long-only moving-average backtest."""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum

from .data import Bar, validate_bars
from .strategy import MovingAverageCross


@dataclass(frozen=True)
class Trade:
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    costs: float
    net_pnl: float
    entry_index: int
    slippage_cost: float = 0.0


@dataclass(frozen=True)
class Metrics:
    gross_pnl: float
    net_pnl: float
    return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float | None
    trade_count: int
    costs: float
    exposure_pct: float


@dataclass(frozen=True)
class BacktestResult:
    strategy: MovingAverageCross
    dataset_version: str
    trades: tuple[Trade, ...]
    equity_curve: tuple[float, ...]
    metrics: Metrics
    out_of_sample: Metrics
    split_index: int
    warnings: tuple[str, ...]


def _metrics(trades: tuple[Trade, ...], curve: tuple[float, ...], capital: float,
             bars_count: int, exposure_bars: int) -> Metrics:
    gross = fsum(t.gross_pnl for t in trades)
    costs = fsum(t.costs for t in trades)
    net = fsum(t.net_pnl for t in trades)
    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [-t.net_pnl for t in trades if t.net_pnl < 0]
    peak = capital
    drawdown = 0.0
    for equity in curve:
        peak = max(peak, equity)
        if peak:
            drawdown = max(drawdown, (peak - equity) / peak)
    return Metrics(gross, net, net / capital * 100, drawdown * 100,
                   len(wins) / len(trades) * 100 if trades else 0.0,
                   fsum(wins) / fsum(losses) if losses else (float("inf") if wins else None),
                   len(trades), costs, exposure_bars / bars_count * 100 if bars_count else 0.0)


def run_backtest(bars: tuple[Bar, ...], strategy: MovingAverageCross,
                 dataset_version: str, out_of_sample_fraction: float = 0.3) -> BacktestResult:
    strategy.validate()
    bars = validate_bars(bars, strategy.instrument)
    if not dataset_version.strip():
        raise ValueError("dataset version is required")
    if not 0.1 <= out_of_sample_fraction <= 0.5:
        raise ValueError("out-of-sample fraction must be between 10% and 50%")
    n = len(bars)
    split = max(strategy.slow_period + 1, int(n * (1 - out_of_sample_fraction)))
    if split >= n - 1:
        raise ValueError("not enough bars for the requested out-of-sample period")
    closes = [b.close for b in bars]
    signals = [False] * n
    for i in range(strategy.slow_period - 1, n):
        fast = fsum(closes[i - strategy.fast_period + 1:i + 1]) / strategy.fast_period
        slow = fsum(closes[i - strategy.slow_period + 1:i + 1]) / strategy.slow_period
        signals[i] = fast > slow

    trades: list[Trade] = []
    equity = [strategy.initial_capital] * n
    position = None
    realized = 0.0
    exposure = 0
    for i in range(1, n):
        desired = signals[i - 1]  # signal from prior close, executed at this bar's open
        if position is None and desired:
            raw_price = bars[i].open
            price = raw_price * (1 + strategy.slippage_rate)
            fee = price * strategy.quantity * strategy.fee_rate
            slippage = (price - raw_price) * strategy.quantity
            position = (i, price, fee + slippage, raw_price)
        elif position is not None and not desired:
            entry_i, entry, entry_cost, raw_entry = position
            raw_exit = bars[i].open
            exit_price = raw_exit * (1 - strategy.slippage_rate)
            exit_fee = exit_price * strategy.quantity * strategy.fee_rate
            exit_slippage = (raw_exit - exit_price) * strategy.quantity
            gross = (raw_exit - raw_entry) * strategy.quantity
            costs = entry_cost + exit_fee + exit_slippage
            trade = Trade(bars[entry_i].timestamp.isoformat(), bars[i].timestamp.isoformat(), entry,
                          exit_price, strategy.quantity, gross, costs, gross - costs, entry_i,
                          entry_cost - (entry * strategy.quantity * strategy.fee_rate) + exit_slippage)
            trades.append(trade)
            realized += trade.net_pnl
            position = None
        if position:
            exposure += 1
            entry_i, entry, entry_cost, raw_entry = position
            unrealized = (bars[i].close - entry) * strategy.quantity - entry_cost
        else:
            unrealized = 0.0
        equity[i] = strategy.initial_capital + realized + unrealized
    complete = tuple(trades)
    in_sample_curve = tuple(equity[:split])
    oos_trades = tuple(t for t in complete if t.entry_index >= split)
    oos_curve = tuple(equity[split:])
    # Flat when no trades occur; no synthetic bars or fills are introduced.
    return BacktestResult(strategy, dataset_version, complete, tuple(equity),
                          _metrics(complete, tuple(equity), strategy.initial_capital, n, exposure),
                          _metrics(oos_trades, oos_curve, strategy.initial_capital,
                                   max(1, n - split), sum(1 for i in range(split, n) if signals[i - 1])),
                          split, ("Signals use prior close and fills use next open.",
                                  "Open positions are marked to market and are not force-closed at dataset end.",
                                  "OOS metrics use fixed strategy parameters; no tuning is performed."))
