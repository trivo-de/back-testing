from datetime import date, timedelta
from decimal import Decimal
import unittest

from backtest_hpg.domain.market import StrategyBar
from backtest_hpg.domain.strategies.canslim_breakout_v0 import run as run_strategy


D = Decimal


def strategy_bars() -> list[StrategyBar]:
    start = date(2025, 1, 1)
    bars = [StrategyBar(start + timedelta(days=i), D(90), D(100), D(80), D(90), D(1000), D(100)) for i in range(203)]
    bars[200] = StrategyBar(bars[200].trading_date, D(100), D(101), D(99), D(101), D(1500), D(101))
    bars[201] = StrategyBar(bars[201].trading_date, D(102), D(121), D(100), D(120), D(1000), D(101))
    bars[202] = StrategyBar(bars[202].trading_date, D(122), D(123), D(121), D(122), D(1000), D(101))
    return bars


class StrategyBacktestTest(unittest.TestCase):
    def test_strategy_sizing_slippage_and_next_open(self):
        bars = strategy_bars()
        result = run_strategy(bars, initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual([(signal.side, signal.reason) for signal in result.signals], [("BUY", "ALL_ENTRY_RULES_PASS"), ("SELL", "TAKE_PROFIT")])
        self.assertEqual((result.fills[0].fill_date, result.fills[0].price, result.fills[0].quantity), (bars[201].trading_date, D("102.204"), 27))
        self.assertEqual((result.fills[1].fill_date, result.fills[1].price), (bars[202].trading_date, D("121.756")))
        self.assertEqual((result.portfolio.cash, result.trades[0].net_pnl), (D("10521.857080"), D("521.857080")))

    def test_results_through_t_do_not_depend_on_future_bars(self):
        bars = strategy_bars()
        full = run_strategy(bars, initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual(full, run_strategy(bars, initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002"))
        truncated = run_strategy(bars[:201], initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        cutoff = bars[200].trading_date
        self.assertEqual(tuple(x for x in full.signals if x.signal_date <= cutoff), truncated.signals)
        self.assertEqual(tuple(x for x in full.equity_history if x.trading_date <= cutoff), truncated.equity_history)
        self.assertEqual((truncated.orders[-1].status, truncated.fills), ("PENDING", ()))
        open_position = run_strategy(bars[:202], initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual(open_position.portfolio.position.quantity, 27)
        self.assertEqual((open_position.summary.final_equity, open_position.summary.unrealized_pnl), (D("10477.732492"), D("477.732492")))
        self.assertEqual(open_position.orders[-1].status, "PENDING")


if __name__ == "__main__":
    unittest.main()
