"""Configurable live market-data adapter with strict validation and provenance."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .data import Bar, SUPPORTED_INSTRUMENTS, validate_bars


@dataclass(frozen=True)
class LiveQuote:
    instrument: str
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    provider: str
    delayed: bool
    provenance: str


class YahooFinanceProvider:
    """Read validated index bars from Yahoo Finance's server-side chart feed."""

    name = "yahoo_finance"
    endpoint = "https://query1.finance.yahoo.com/v8/finance/chart/"
    _intervals = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
    symbols = {"NSE:NIFTY50": "^NSEI", "NSE:NIFTYBANK": "^NSEBANK"}

    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or self.endpoint

    def _fetch(self, instrument: str, timeframe: str, outputsize: int) -> tuple[dict, tuple[Bar, ...]]:
        if instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError("unsupported instrument")
        if timeframe not in self._intervals:
            raise ValueError("unsupported live timeframe")
        if not 1 <= outputsize <= 500:
            raise ValueError("outputsize must be between 1 and 500")
        range_value = "1d" if timeframe != "1d" else "1y"
        query = urlencode({"range": range_value, "interval": self._intervals[timeframe], "includePrePost": "false"})
        request = Request(f"{self.endpoint}{self.symbols[instrument]}?{query}",
                          headers={"Accept": "application/json", "User-Agent": "Scout-paper-research/0.1"})
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Yahoo Finance request failed: {exc}") from exc
        chart = payload.get("chart", {}) if isinstance(payload, dict) else {}
        results = chart.get("result") if isinstance(chart, dict) else None
        if not results:
            error = chart.get("error") if isinstance(chart, dict) else None
            message = error.get("description") if isinstance(error, dict) else "no chart data returned"
            raise RuntimeError(f"Yahoo Finance returned no data: {message}")
        result = results[0]
        values = result.get("indicators", {}).get("quote", [{}])[0]
        timestamps = result.get("timestamp") or []
        bars: list[Bar] = []
        for index, seconds in enumerate(timestamps):
            try:
                fields = [values.get(name, [None] * len(timestamps))[index]
                          for name in ("open", "high", "low", "close", "volume")]
                if any(value is None for value in fields):
                    continue
                bars.append(Bar(datetime.fromtimestamp(int(seconds), tz=timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")),
                                *(float(value) for value in fields)))
            except (IndexError, TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError(f"Yahoo Finance returned an invalid bar: {exc}") from exc
        bars = bars[-outputsize:]
        if not bars:
            raise RuntimeError("Yahoo Finance returned no complete OHLCV bars")
        for bar in bars:
            if not all(isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close, bar.volume)):
                raise RuntimeError("Yahoo Finance returned non-finite OHLCV values")
            if min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0 or \
                    bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
                raise RuntimeError("Yahoo Finance returned an invalid OHLC relationship")
        return result, validate_bars(bars, instrument) if len(bars) >= 2 else tuple(bars)

    def recent(self, instrument: str, timeframe: str = "5m", outputsize: int = 80) -> tuple[Bar, ...]:
        _, bars = self._fetch(instrument, timeframe, outputsize)
        return bars

    def latest(self, instrument: str, timeframe: str = "5m") -> LiveQuote:
        result, bars = self._fetch(instrument, timeframe, 1)
        bar = bars[-1]
        meta = result.get("meta", {})
        close = meta.get("regularMarketPrice")
        close = float(close) if close is not None and isfinite(float(close)) else bar.close
        symbol = self.symbols[instrument]
        return LiveQuote(instrument, symbol, bar.timestamp.isoformat(), bar.open, bar.high, bar.low,
                         close, bar.volume, self.name, True,
                         f"Yahoo Finance chart:{symbol}:{bar.timestamp.isoformat()}")


def market_provider_status() -> dict[str, object]:
    return {"provider": os.getenv("MARKET_DATA_PROVIDER", "yahoo_finance"),
            "configured": True,
            "api_key_required": False,
            "live_trading": False,
            "message": "Yahoo Finance chart data may be delayed or rate-limited; verify provenance before research use."}
