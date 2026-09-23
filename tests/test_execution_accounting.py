from datetime import date
from decimal import Decimal
import unittest

from backtest_hpg.domain.engine import run_fixed_signals
from backtest_hpg.domain.market import Bar
from backtest_hpg.domain.trading import FixedSignal


D = Decimal


def bar(day: int, open_: int, close: int) -> Bar:
    return Bar(date(2026, 1, day), D(open_), D(close))


class ExecutionAccountingTest(unittest.TestCase):
    def run_round_trip(self, initial_cash: int, quantity: int, buy: int, mark: int, sell: int):
        bars = [bar(1, buy - 1, buy - 1), bar(2, buy, mark), bar(3, sell, sell)]
        signals = {bars[0].trading_date: FixedSignal("BUY", quantity), bars[1].trading_date: FixedSignal("SELL")}
        return run_fixed_signals(bars, signals, initial_cash=initial_cash, fee_rate="0.001")

    def test_acc_01(self):
        result = self.run_round_trip(8_000_000, 200, 15_000, 16_000, 17_000)
        holding = result.equity_history[1].snapshot
        self.assertEqual((holding.cash, holding.market_value, holding.unrealized_pnl, holding.equity), (D(4_997_000), D(3_200_000), D(197_000), D(8_197_000)))
        self.assertEqual((result.portfolio.cash, result.portfolio.realized_pnl), (D(8_393_600), D(393_600)))
        self.assertEqual((result.summary.final_equity, result.summary.total_return), (D(8_393_600), D("0.0492")))
        self.assertEqual((result.fills[0].fill_date, result.fills[1].fill_date), (date(2026, 1, 2), date(2026, 1, 3)))

    def test_acc_02(self):
        result = self.run_round_trip(8_000_000, 200, 15_000, 14_000, 14_000)
        self.assertEqual((result.portfolio.cash, result.portfolio.realized_pnl), (D(7_794_200), D(-205_800)))

    def test_acc_03(self):
        result = self.run_round_trip(5_000_000, 100, 10_000, 11_000, 12_000)
        holding = result.equity_history[1].snapshot
        self.assertEqual((holding.equity, holding.unrealized_pnl), (D(5_099_000), D(99_000)))
        self.assertEqual((result.portfolio.cash, result.portfolio.realized_pnl), (D(5_197_800), D(197_800)))

    def test_rejection_and_final_signal_do_not_create_fills(self):
        bars = [bar(1, 10, 10), bar(2, 10, 10)]
        rejected = run_fixed_signals(
            bars,
            {bars[0].trading_date: FixedSignal("BUY", 100)},
            initial_cash=100,
            fee_rate="0.001",
        )
        pending = run_fixed_signals(
            bars,
            {bars[-1].trading_date: FixedSignal("BUY", 1)},
            initial_cash=100,
            fee_rate="0.001",
        )
        quantity_below_one = run_fixed_signals(
            bars,
            {bars[0].trading_date: FixedSignal("BUY")},
            initial_cash=1,
            fee_rate="0.001",
            size_buy=lambda context: int(context.cash // (context.fill_price * (1 + context.fee_rate))),
        )
        self.assertEqual((rejected.orders[0].status, rejected.fills), ("REJECTED", ()))
        self.assertEqual((pending.orders[0].status, pending.fills), ("PENDING", ()))
        self.assertEqual((quantity_below_one.orders[0].status, quantity_below_one.fills), ("REJECTED", ()))

    def test_invalid_execution_config_is_rejected(self):
        bars = [bar(1, 10, 10)]
        with self.assertRaises(ValueError):
            run_fixed_signals(bars, {}, initial_cash=100, fee_rate="0.001", slippage_rate="1")


if __name__ == "__main__":
    unittest.main()
