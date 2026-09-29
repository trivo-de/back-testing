"""Synthetic intraday mechanics independent of the retired manifest API."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal as D

from backtest_hpg.domain.engine import run_fixed_signals
from backtest_hpg.domain.market import Bar, StrategyBar
from backtest_hpg.domain.strategies.canslim_breakout_v0 import run
from backtest_hpg.domain.trading import FixedSignal
from backtest_hpg.infrastructure.market_snapshot import LOCAL_TZ


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

    def test_independent_market_samples_availability_and_causality(self):
        start = datetime(2026, 3, 18, 9, tzinfo=LOCAL_TZ)
        futures = [StrategyBar(start + timedelta(minutes=5*i), D(100), D(101), D(99),
                               D(100), D(1000), close_time=start + timedelta(minutes=5*(i+1)))
                   for i in range(220)]
        one_market = [Bar(start, D(100), D(100), start + timedelta(minutes=5))]
        result = run(futures, market_bars=one_market, initial_cash=1000, fee_rate=0, slippage_rate=0)
        self.assertTrue(all(row["status"] == "UNEVALUABLE" for row in result.evaluations))
        self.assertEqual(result.evaluations[-1]["market_sample_count"], 1)
        market = [Bar(b.trading_date, D(100), D(100), b.close_time) for b in futures]
        futures[202] = replace(futures[202], high=D(103), close=D(102), volume=D(1500))
        market[202] = replace(market[202], close=D(101))
        result = run(futures, market_bars=market, initial_cash=1000, fee_rate=0, slippage_rate=0)
        cutoff = futures[205].closed_at
        prefix = run(futures[:206], market_bars=market[:206], initial_cash=1000, fee_rate=0, slippage_rate=0)
        self.assertEqual(prefix.equity_history, tuple(p for p in result.equity_history if p.trading_date <= cutoff))
        self.assertEqual(prefix.evaluations, result.evaluations[:206])
        self.assertEqual(prefix.fills, tuple(f for f in result.fills if f.fill_date <= cutoff))
        self.assertEqual(run(futures, market_bars=market, initial_cash=1000, fee_rate=0, slippage_rate=0), result)
        changed = market[:206] + [replace(b, close=D(10000)) for b in market[206:]]
        altered = run(futures, market_bars=changed, initial_cash=1000, fee_rate=0, slippage_rate=0)
        self.assertEqual(altered.evaluations[:206], result.evaluations[:206])
        self.assertTrue(all(row["market_available_at"] <= row["time"] for row in result.evaluations))


if __name__ == "__main__":
    unittest.main()
