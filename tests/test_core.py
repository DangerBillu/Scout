import unittest
from datetime import datetime, timedelta, timezone

from scout.backtest import run_backtest
from scout.data import Bar, validate_bars
from scout.strategy import MovingAverageCross
from scout.tools import Tool, ToolRegistry


def bars_from(closes):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return tuple(Bar(start + timedelta(days=i), p, p + 1, p - 1, p, 1000) for i, p in enumerate(closes))


class DataTests(unittest.TestCase):
    def test_validates_timezone_and_order(self):
        rows = bars_from([10, 11, 12])
        self.assertEqual(validate_bars(rows, "NSE:NIFTY50"), rows)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            validate_bars((rows[0], rows[0]), "NSE:NIFTY50")
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_bars((Bar(datetime(2025, 1, 1), 10, 11, 9, 10, 1), rows[1]), "NSE:NIFTY50")

    def test_rejects_ohlc_and_unknown_instrument(self):
        with self.assertRaisesRegex(ValueError, "OHLC"):
            validate_bars((Bar(datetime.now(timezone.utc), 10, 8, 9, 10, 1), bars_from([11, 12])[1]), "NSE:NIFTY50")
        with self.assertRaisesRegex(ValueError, "unsupported instrument"):
            validate_bars(bars_from([10, 11]), "NSE:UNKNOWN")


class BacktestTests(unittest.TestCase):
    def test_reproducible_and_costs_reduce_pnl(self):
        prices = [100, 101, 102, 104, 106, 108, 105, 102, 99, 97, 100, 104, 108, 112, 109, 105, 101, 98, 102, 106, 110, 114, 111, 107, 103, 100, 104, 108, 112, 116]
        strategy = MovingAverageCross("NSE:NIFTY50", "1d", 2, 4, fee_rate=0.001, slippage_rate=0.001)
        result = run_backtest(bars_from(prices), strategy, "fixture-v1")
        self.assertEqual(result, run_backtest(bars_from(prices), strategy, "fixture-v1"))
        self.assertGreater(result.metrics.costs, 0)
        self.assertLess(result.metrics.net_pnl, result.metrics.gross_pnl)
        self.assertEqual(len(result.equity_curve), len(prices))

    def test_rejects_unsafe_parameters(self):
        with self.assertRaises(ValueError):
            run_backtest(bars_from([10, 11, 12, 13, 14, 15, 16, 17]),
                         MovingAverageCross("NSE:NIFTY50", "1d", 4, 2), "v1")


class RegistryTests(unittest.TestCase):
    def test_permission_and_registration(self):
        registry = ToolRegistry()
        registry.register(Tool("market.read", "Read only test tool", True, "market:read", lambda args: {"ok": True}))
        self.assertEqual(registry.names_for({"market:read"}), ("market.read",))
        with self.assertRaises(PermissionError):
            registry.call("market.read", {}, set())
        self.assertEqual(registry.call("market.read", {}, {"market:read"}), {"ok": True})
        with self.assertRaises(ValueError):
            registry.register(Tool("market.read", "duplicate", True, "market:read", lambda args: {}))


if __name__ == "__main__":
    unittest.main()
