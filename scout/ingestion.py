"""Source-adapter boundary for validated CSV market data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Protocol

from .data import Bar, DatasetInfo, validate_bars


@dataclass(frozen=True)
class QualityReport:
    bar_count: int
    first_timestamp: str
    last_timestamp: str
    missing_intervals: int
    warnings: tuple[str, ...]


class MarketDataAdapter(Protocol):
    name: str

    def read(self, payload: str, *, instrument: str, timeframe: str, version: str,
             retrieved_at: datetime | None = None) -> tuple[tuple[Bar, ...], DatasetInfo, QualityReport]: ...


_INTERVALS = {"5m": timedelta(minutes=5), "15m": timedelta(minutes=15), "1h": timedelta(hours=1),
              "1d": timedelta(days=1)}


class CsvSourceAdapter:
    name = "csv-upload"

    def read(self, payload: str, *, instrument: str, timeframe: str, version: str,
             retrieved_at: datetime | None = None) -> tuple[tuple[Bar, ...], DatasetInfo, QualityReport]:
        if not isinstance(payload, str) or not payload.strip():
            raise ValueError("CSV payload is required")
        if timeframe not in _INTERVALS or not version.strip():
            raise ValueError("unsupported timeframe or missing dataset version")
        reader = csv.DictReader(StringIO(payload))
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not reader.fieldnames or not required.issubset({name.strip().lower() for name in reader.fieldnames}):
            raise ValueError("CSV must contain timestamp, open, high, low, close, and volume columns")
        bars = []
        for row_number, row in enumerate(reader, 2):
            try:
                normalized = {key.strip().lower(): value for key, value in row.items()}
                bars.append(Bar(datetime.fromisoformat(normalized["timestamp"].replace("Z", "+00:00")),
                                float(normalized["open"]), float(normalized["high"]), float(normalized["low"]),
                                float(normalized["close"]), float(normalized["volume"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"CSV row {row_number} is invalid: {exc}") from exc
        bars = validate_bars(bars, instrument)
        expected = _INTERVALS[timeframe]
        missing = sum(1 for previous, current in zip(bars, bars[1:])
                      if current.timestamp - previous.timestamp > expected)
        warnings = (f"{missing} interval gap(s) detected; gaps were not filled.",) if missing else ()
        retrieved = retrieved_at or datetime.now(timezone.utc)
        info = DatasetInfo(instrument, timeframe, self.name, version, retrieved, warnings)
        report = QualityReport(len(bars), bars[0].timestamp.isoformat(), bars[-1].timestamp.isoformat(), missing, warnings)
        return bars, info, report
