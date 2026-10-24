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

from .data import Bar, SUPPORTED_INSTRUMENTS


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


class TwelveDataProvider:
    """Read the most recent validated bar from Twelve Data's REST API.

    Exact index symbols are provider metadata, so they are configurable rather
    than silently assumed. Configure and validate them with the provider before
    using a quote for paper trading.
    """

    name = "twelvedata"
    _intervals = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "1d": "1day"}

    def __init__(self, api_key: str | None = None, endpoint: str = "https://api.twelvedata.com/time_series"):
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY")
        self.endpoint = endpoint
        self.symbols = {
            "NSE:NIFTY50": os.getenv("TWELVE_DATA_NIFTY50_SYMBOL", "NIFTY"),
            "NSE:NIFTYBANK": os.getenv("TWELVE_DATA_NIFTYBANK_SYMBOL", "BANKNIFTY"),
        }

    def latest(self, instrument: str, timeframe: str = "5m") -> LiveQuote:
        if instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError("unsupported instrument")
        if timeframe not in self._intervals:
            raise ValueError("unsupported live timeframe")
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is not configured")
        symbol = self.symbols[instrument]
        query = urlencode({"symbol": symbol, "exchange": "NSE", "interval": self._intervals[timeframe],
                           "outputsize": 1, "timezone": "Asia/Kolkata", "apikey": self.api_key})
        request = Request(f"{self.endpoint}?{query}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=10) as response:
            raw = response.read(200_000)
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("status") == "error" or not isinstance(payload.get("values"), list) or not payload["values"]:
            raise RuntimeError(payload.get("message", "provider returned no market bar"))
        value = payload["values"][0]
        try:
            timestamp = datetime.fromisoformat(value["datetime"]).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            bar = Bar(timestamp, float(value["open"]), float(value["high"]), float(value["low"]),
                      float(value["close"]), float(value.get("volume", 0) or 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"provider returned an invalid bar: {exc}") from exc
        for field in (bar.open, bar.high, bar.low, bar.close, bar.volume):
            if not isfinite(field):
                raise RuntimeError("provider returned a non-finite quote")
        if min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0 or \
                bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
            raise RuntimeError("provider returned an invalid OHLC quote")
        return LiveQuote(instrument, symbol, timestamp.isoformat(), bar.open, bar.high, bar.low,
                         bar.close, bar.volume, self.name, False,
                         f"{self.name}:{symbol}:{timestamp.isoformat()}")

    def recent(self, instrument: str, timeframe: str = "5m", outputsize: int = 80) -> tuple[Bar, ...]:
        if instrument not in SUPPORTED_INSTRUMENTS or timeframe not in self._intervals:
            raise ValueError("unsupported instrument or live timeframe")
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is not configured")
        if not 2 <= outputsize <= 5000:
            raise ValueError("outputsize must be between 2 and 5000")
        query = urlencode({"symbol": self.symbols[instrument], "exchange": "NSE",
                           "interval": self._intervals[timeframe], "outputsize": outputsize,
                           "timezone": "Asia/Kolkata", "order": "asc", "apikey": self.api_key})
        request = Request(f"{self.endpoint}?{query}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read(1_000_000).decode("utf-8"))
        if payload.get("status") == "error" or not isinstance(payload.get("values"), list):
            raise RuntimeError(payload.get("message", "provider returned no market bars"))
        bars = []
        try:
            for value in payload["values"]:
                bars.append(Bar(datetime.fromisoformat(value["datetime"]).replace(tzinfo=ZoneInfo("Asia/Kolkata")),
                                float(value["open"]), float(value["high"]), float(value["low"]),
                                float(value["close"]), float(value.get("volume", 0) or 0)))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"provider returned invalid bars: {exc}") from exc
        if len(bars) < 2:
            raise RuntimeError("provider returned fewer than two bars")
        from .data import validate_bars
        return validate_bars(bars, instrument)


def market_provider_status() -> dict[str, object]:
    return {"provider": os.getenv("MARKET_DATA_PROVIDER", "twelvedata"),
            "configured": bool(os.getenv("TWELVE_DATA_API_KEY")),
            "live_trading": False,
            "message": "Configure a licensed provider API key; Scout never fabricates unavailable quotes."}
