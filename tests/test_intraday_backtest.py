"""Synthetic intraday mechanics independent of the retired manifest API."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal as D
import unittest

from backtesting_api.domain.engine import run_fixed_signals
from backtesting_api.domain.market import Bar
from backtesting_api.domain.trading import FixedSignal
from backtesting_api.infrastructure.market_snapshot import LOCAL_TZ


class IntradayTest(unittest.TestCase):
    def test_close_signal_next_open_lunch_overnight_atc_and_final_pending(self):
        stamps = [datetime(2026, 3, 18, 11, 25, tzinfo=LOCAL_TZ),
                  datetime(2026, 3, 18, 13, 0, tzinfo=LOCAL_TZ),
                  datetime(2026, 3, 19, 9, 0, tzinfo=LOCAL_TZ),
                  datetime(2026, 3, 19, 14, 45, tzinfo=LOCAL_TZ)]
        bars = [Bar(t, D(100), D(100), t + timedelta(minutes=5)) for t in stamps]
        result = run_fixed_signals(bars, {
            stamps[0]: FixedSignal("BUY", quantity=1),
            stamps[1]: FixedSignal("SELL"), stamps[3]: FixedSignal("BUY", quantity=1),
        }, initial_cash=1000, fee_rate=0)
        self.assertEqual(result.signals[0].signal_date, stamps[0] + timedelta(minutes=5))
        self.assertEqual([f.fill_date for f in result.fills], stamps[1:3])
        self.assertEqual(result.orders[-1].status, "PENDING")
        self.assertEqual(result.equity_history[-1].trading_date.hour, 14)
        self.assertEqual(result.equity_history[-1].trading_date.minute, 50)
        with self.assertRaisesRegex(ValueError, "aware"):
            run_fixed_signals([replace(bars[0], close_time=None)], {}, initial_cash=1000, fee_rate=0)


if __name__ == "__main__":
    unittest.main()
