from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest
from backtesting_api.domain.contract_accounting import ContractAccounting, ContractPortfolio
from backtesting_api.domain.engine import run_engine
from backtesting_api.domain.execution import Bracket, ContractExecution
from backtesting_api.domain.market import StrategyBar
from backtesting_api.domain.trading import FixedSignal


ACCOUNTING = ContractAccounting(D('.17'), D('.001'), D(2700), D(2550), D(0))


def bar(index, opened=1000, high=1001, low=999, close=1000):
    start = datetime(2026, 3, 25, 9, 0, tzinfo=timezone(timedelta(hours=7))) + timedelta(minutes=5 * index)
    return StrategyBar(start, D(str(opened)), D(str(high)), D(str(low)), D(str(close)),
                       D(10), close_time=start + timedelta(minutes=5))


def run(bars, signals, bracket=None):
    return run_engine(bars, lambda c: signals.get(c.bars[-1].trading_date), initial_cash=100000000,
                      fee_rate=0, slippage_rate=0,
                      execution=lambda cash: ContractExecution(cash, ACCOUNTING, bracket=bracket))


class ContractExecutionTest(unittest.TestCase):
    def test_long_short_partial_cash_fees_and_margin(self):
        for direction, first, last, first_net, total in (
                ('LONG', 1006, 1012, 572449, 2917245),
                ('SHORT', 994, 988, 572551, 2917755)):
            with self.subTest(direction=direction):
                p, costs = ContractPortfolio.open(100000000, ACCOUNTING).enter(direction, 3, 1000)
                self.assertEqual(costs.total, 41250)
                self.assertEqual(p.cash, 99958750)
                self.assertEqual(p.mark(1000).required_margin, 51000000)
                self.assertEqual(p.mark(first).unrealized_pnl, 1800000)
                p, _, allocated, net = p.exit(1, first)
                self.assertEqual((allocated, net), (13750, first_net))
                self.assertEqual(p.mark(first).unrealized_pnl, 1200000)
                self.assertEqual(p.mark(first).equity, p.cash + 1200000)
                p, _, allocated, _ = p.exit(2, last)
                self.assertEqual(allocated, 27500)
                self.assertEqual(p.realized_pnl, total)
                self.assertEqual(p.cash - 100000000, total)
                self.assertEqual(p.mark(last).unrealized_pnl, 0)
                self.assertEqual(p.mark(last).required_margin, 0)
                self.assertIsNone(p.position)

    def test_residual_costs_margin_rejection_and_multiplier(self):
        p, costs = ContractPortfolio.open(100000000, ACCOUNTING).enter('LONG', 3, D('1000.2'))
        allocations = []
        for _ in range(3):
            p, _, allocated, _ = p.exit(1, D('1000.2'))
            allocations.append(allocated)
        self.assertEqual(allocations, [13752, 13752, 13751])
        self.assertEqual(sum(allocations), costs.total)
        self.assertEqual(p.cash - 100000000, p.realized_pnl)
        for direction, quantity, cash in (('LONG', 1, 18700000), ('SHORT', 6, 1000000000), ('LONG', True, 100000000)):
            with self.assertRaises(ValueError):
                ContractPortfolio.open(cash, ACCOUNTING).enter(direction, quantity, 1000)
        accounting = ContractAccounting('.17', '0', '0', '0', '0', contract_multiplier='10')
        p, _ = ContractPortfolio.open(1000000, accounting).enter('SHORT', 2, 1000)
        p, _, _, net = p.exit(2, 990)
        self.assertEqual(net, 200)

    def test_engine_long_short_next_open_partial_exit_and_repeat(self):
        bars = [bar(0), bar(1), bar(2, 1006, 1007, 1005, 1006), bar(3, 1012, 1013, 1011, 1012)]
        for side, total in (('LONG', 2917245), ('SHORT', -3082755)):
            signals = {bars[0].trading_date: FixedSignal(side, 3), bars[1].trading_date: FixedSignal('CLOSE', 1),
                       bars[2].trading_date: FixedSignal('CLOSE')}
            result = run(bars, signals)
            self.assertEqual(result, run(bars, signals))
            self.assertEqual(result.fills[0].fill_date, bars[1].trading_date)
            self.assertEqual([f.quantity for f in result.fills], [3, 1, 2])
            self.assertEqual(result.summary.realized_pnl, total)
            self.assertEqual(result.portfolio.cash - 100000000, total)
            self.assertEqual(sum(t.net_pnl for t in result.trades), total)
            self.assertEqual(result.trades[0].direction, side)
            self.assertEqual(result.fills[0].costs.pit, 25500)

    def test_stop_priority_gap_and_targets_on_entry_bar(self):
        bracket = Bracket(D(6), ((D(6), 1), (D(12), None)))
        first = bar(0)
        for direction, opened, high, low, expected in (
                ('LONG', 1000, 1020, 993, 994), ('SHORT', 1000, 1007, 980, 1006)):
            result = run([first, bar(1, opened, high, low)], {first.trading_date: FixedSignal(direction, 3)}, bracket)
            self.assertEqual([f.price for f in result.fills], [1000, expected])
            self.assertEqual(result.signals[-1].reason, 'STOP_LOSS')
        for direction, opened, high, low in (('LONG', 990, 992, 989), ('SHORT', 1010, 1011, 1009)):
            result = run([first, bar(1), bar(2, opened, high, low, opened)],
                         {first.trading_date: FixedSignal(direction, 3)}, bracket)
            self.assertEqual(result.fills[-1].price, opened)
            self.assertEqual(result.fills[-1].fill_date, bar(2).trading_date)
        result = run([first, bar(1), bar(2, 1020, 1022, 1019, 1021)],
                     {first.trading_date: FixedSignal('LONG', 3)}, bracket)
        self.assertEqual([f.price for f in result.fills], [1000, 1006, 1012])
        self.assertEqual([f.quantity for f in result.fills], [3, 1, 2])
        self.assertIsNone(result.portfolio.position)
        equal = Bracket(D(6), ((D(6), 1), (D(6), None)))
        result = run([first, bar(1, 1000, 1007, 999, 1006)], {first.trading_date: FixedSignal('LONG', 3)}, equal)
        self.assertEqual([f.price for f in result.fills], [1000, 1006, 1006])

    def test_trailing_excludes_tp1_bar_and_tightens_only_next_bar(self):
        bracket = Bracket(D(6), ((D(6), 2), (D(12), None)), D(6))
        bars = [bar(0), bar(1, 1000, 1011, 999, 1006), bar(2, 1006, 1011, 1001, 1010),
                bar(3, 1004, 1005, 999, 1000)]
        signals = {bars[0].trading_date: FixedSignal('LONG', 5)}
        prefix = run(bars[:3], signals, bracket)
        result = run(bars, signals, bracket)
        self.assertEqual(result.equity_history[:3], prefix.equity_history)
        self.assertEqual(result.fills[:2], prefix.fills)
        self.assertEqual([f.price for f in result.fills], [1000, 1006, 1004])
        self.assertEqual(result.signals[-1].reason, 'TRAILING_STOP')
        self.assertEqual(prefix.portfolio.position.quantity, 3)
        short_bars = [bar(0), bar(1, 1000, 1001, 989, 994), bar(2, 994, 999, 989, 990),
                      bar(3, 996, 1001, 995, 1000)]
        result = run(short_bars, {short_bars[0].trading_date: FixedSignal('SHORT', 5)}, bracket)
        self.assertEqual([f.price for f in result.fills], [1000, 994, 996])

    def test_pending_exit_precedes_bracket_and_invalid_fill_does_not_mutate(self):
        bars = [bar(0), bar(1), bar(2, 1002, 1020, 990, 1000)]
        signals = {bars[0].trading_date: FixedSignal('LONG', 2), bars[1].trading_date: FixedSignal('CLOSE')}
        result = run(bars, signals, Bracket(D(6), ((D(6), 1), (D(12), None))))
        self.assertEqual([f.price for f in result.fills], [1000, 1002])
        executor = ContractExecution(100000000, ACCOUNTING)
        initial = executor.portfolio
        for signal, price in ((FixedSignal('LONG', 6), 1000), (FixedSignal('SHORT', 1), D('1000.01'))):
            with self.assertRaises(ValueError): executor.execute(signal, bars[0].closed_at, bars[1].trading_date, price)
            self.assertEqual(executor.portfolio, initial)
        with self.assertRaises(ValueError):
            run_engine(bars, lambda c: None, initial_cash=100000000, fee_rate='.001', slippage_rate=0,
                       execution=lambda cash: ContractExecution(cash, ACCOUNTING))
