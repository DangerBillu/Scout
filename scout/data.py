"""Market bar types and strict validation. Timestamps must be ISO 8601 with timezone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable


SUPPORTED_INSTRUMENTS = {"NSE:NIFTY50", "NSE:NIFTYBANK"}


@dataclass(frozen=True)
class InstrumentMetadata:
    instrument: str
    display_name: str
    exchange: str
    timezone: str
    regular_session: str


INSTRUMENT_METADATA = {
    "NSE:NIFTY50": InstrumentMetadata("NSE:NIFTY50", "NIFTY 50", "NSE", "Asia/Kolkata", "09:15-15:30"),
    "NSE:NIFTYBANK": InstrumentMetadata("NSE:NIFTYBANK", "NIFTY BANK", "NSE", "Asia/Kolkata", "09:15-15:30"),
}


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class DatasetInfo:
    instrument: str
    timeframe: str
    source: str
    version: str
    ingested_at: datetime
    warnings: tuple[str, ...] = ()


def validate_bars(bars: Iterable[Bar], instrument: str) -> tuple[Bar, ...]:
    """Validate bars without filling gaps or altering source values."""
    if instrument not in SUPPORTED_INSTRUMENTS:
        raise ValueError(f"unsupported instrument: {instrument}")
    result = tuple(bars)
    if len(result) < 2:
        raise ValueError("at least two bars are required")
    previous = None
    for index, bar in enumerate(result):
        if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() is None:
            raise ValueError(f"bar {index}: timestamp must include a timezone")
        if previous is not None and bar.timestamp <= previous:
            raise ValueError(f"bar {index}: timestamps must be strictly increasing and unique")
        previous = bar.timestamp
        values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
        if not all(isfinite(float(value)) for value in values):
            raise ValueError(f"bar {index}: values must be finite")
        if min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0:
            raise ValueError(f"bar {index}: prices must be positive and volume non-negative")
        if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
            raise ValueError(f"bar {index}: invalid OHLC relationship")
    return result
