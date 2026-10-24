"""Validated, declarative strategy definitions. No user-provided code is executed."""

from dataclasses import dataclass

from .data import SUPPORTED_INSTRUMENTS


@dataclass(frozen=True)
class MovingAverageCross:
    instrument: str
    timeframe: str
    fast_period: int
    slow_period: int
    version: str = "1"
    initial_capital: float = 100_000.0
    quantity: float = 1.0
    fee_rate: float = 0.0003
    slippage_rate: float = 0.0005

    def validate(self) -> None:
        if self.instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError("instrument is not supported")
        if self.timeframe not in {"1d", "5m", "15m", "1h"}:
            raise ValueError("unsupported timeframe")
        if not (2 <= self.fast_period < self.slow_period <= 500):
            raise ValueError("periods must satisfy 2 <= fast < slow <= 500")
        if not self.version.strip():
            raise ValueError("strategy version is required")
        if self.initial_capital <= 0 or self.quantity <= 0:
            raise ValueError("capital and quantity must be positive")
        if not (0 <= self.fee_rate <= 0.05 and 0 <= self.slippage_rate <= 0.05):
            raise ValueError("fee and slippage rates must be between 0 and 5 percent")
