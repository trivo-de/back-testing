from decimal import Decimal as D
import unittest

from backtesting_api.domain.execution import Bracket, ContractExecution
from backtesting_api.domain.multi_execution import MultiContractExecution
from backtesting_api.domain.orders import OrderRequest
from backtesting_api.domain.trading import FixedSignal
from test_contract_execution import ACCOUNTING, bar


def entry(key, quantity=1, side='LONG'):
    return FixedSignal(side, quantity, order=OrderRequest('LO', D(1000)), position_id=key)


class MultiExecutionTest(unittest.TestCase):
    def test_same_order_continuation_preserves_protection_and_caps_quantity(self):
        from dataclasses import replace
        executor = self.executor()
        stamp = bar(0).trading_date
        signal = entry('A', 2)
        executor.execute(signal, stamp, stamp, D(1000), order_quantity=5)
        first = executor.lots['A'].entry_fill
        executor.execute(replace(signal, quantity=3), stamp, bar(1).trading_date, D('1000.1'),
                         continuation=True, order_quantity=5)
        position = executor.portfolio.lot('A')
        self.assertEqual((position.quantity, position.initial_quantity, position.entry_price), (5, 5, D('1000.06')))
        self.assertEqual(executor.lots['A'].active_stop, 994)
        self.assertEqual(executor.lots['A'].entry_fill, first)
        original = executor.portfolio
        with self.assertRaisesRegex(ValueError, 'ENTRY_CONTINUATION_EXCEEDS_ORDER'):
            executor.execute(entry('A', 1), stamp, stamp, D(1000), continuation=True)
        self.assertEqual(executor.portfolio, original)
        executor.execute(FixedSignal('CLOSE', 2, position_id='A'), stamp, stamp, D(1001))
        executor.execute(FixedSignal('CLOSE', 3, position_id='A'), stamp, stamp, D(1001))
        self.assertEqual(executor.portfolio.quantity, 0)
        self.assertEqual(executor.portfolio.cash - 200000000, executor.portfolio.realized_pnl)

    def executor(self, cash=200000000):
        return MultiContractExecution(cash, lambda amount: ContractExecution(
            amount, ACCOUNTING, bracket=Bracket(D(6), ((D(12), None),))))

    def test_independent_protection_and_shared_cash(self):
        executor = self.executor()
        stamp = bar(0).trading_date
        executor.execute(entry('A'), stamp, stamp, D(1000))
        executor.execute(entry('B'), stamp, stamp, D(1004))
        self.assertEqual(executor.lots['A'].active_stop, 994)
        self.assertEqual(executor.lots['B'].active_stop, 998)
        events = executor.intrabar(bar(1, 1000, 1001, 997, 1000))
        self.assertEqual(len(events), 1)
        signal, fill, trade = events[0]
        self.assertEqual((signal.position_id, fill.position_id, trade.position_id), ('B', 'B', 'B'))
        self.assertEqual((fill.price, trade.entry_price, signal.reason), (998, 1004, 'STOP_LOSS'))
        self.assertIsNotNone(executor.portfolio.lot('A'))
        self.assertIsNone(executor.portfolio.lot('B'))
        events = executor.intrabar(bar(2, 1000, 1013, 999, 1012))
        self.assertEqual([(f.position_id, f.price) for _, f, _ in events], [('A', 1012)])
        self.assertEqual(executor.portfolio.positions, ())
        self.assertEqual(executor.portfolio.cash - 200000000, executor.portfolio.realized_pnl)

    def test_reservation_counts_held_and_pending_and_clips_later_order(self):
        executor = self.executor()
        stamp = bar(0).trading_date
        executor.execute(entry('held'), stamp, stamp, D(1000))
        first = executor.prepare_order(entry('A', 3))
        second = executor.prepare_order(entry('B', 3), pending=(first,))
        self.assertEqual((first.quantity, second.quantity), (3, 1))
        with self.assertRaisesRegex(ValueError, 'MAX_CONTRACTS_RESERVED'):
            executor.prepare_order(entry('C'), pending=(first, second))
        with self.assertRaisesRegex(ValueError, 'POSITION_ORDER_PENDING'):
            executor.prepare_order(entry('A'), pending=(first,))
        # Removing an expired order releases its reservation without changing cash.
        self.assertEqual(executor.prepare_order(entry('C', 3), pending=(second,)).quantity, 3)
        executor.execute(first, stamp, stamp, D(1000))
        executor.execute(second, stamp, stamp, D(1000))
        self.assertEqual(executor.portfolio.quantity, 5)
        close = executor.prepare_order(FixedSignal('CLOSE', position_id='A'))
        self.assertEqual(close.quantity, 3)
        with self.assertRaisesRegex(ValueError, 'POSITION_ORDER_PENDING'):
            executor.prepare_order(close, pending=(close,))
        executor.execute(close, stamp, stamp, D(1000))
        self.assertEqual(executor.prepare_order(entry('C', 3)).quantity, 3)

    def test_pending_direction_blocks_opposite_before_any_fill(self):
        executor = self.executor()
        first = executor.prepare_order(entry('A'))
        with self.assertRaisesRegex(ValueError, 'OPPOSITE_ORDER_PENDING'):
            executor.prepare_order(entry('B', side='SHORT'), pending=(first,))
        self.assertEqual(executor.portfolio.quantity, 0)

    def test_limit_touch_suppresses_only_that_lots_targets(self):
        executor = self.executor()
        stamp = bar(0).trading_date
        executor.execute(entry('A'), stamp, stamp, D(1000))
        executor.execute(entry('B'), stamp, stamp, D(1004))
        events = executor.intrabar(bar(1, 1005, 1017, 1004, 1010), intrabar_entries={'B'})
        self.assertEqual([f.position_id for _, f, _ in events], ['A'])
        self.assertEqual(executor.portfolio.quantity, 1)
        self.assertEqual(executor.lots['B'].target_index, 0)

    def test_rejection_does_not_change_other_lots_or_protection(self):
        executor = self.executor(30000000)
        stamp = bar(0).trading_date
        executor.execute(entry('A'), stamp, stamp, D(1000))
        original = executor.portfolio
        for signal, error in ((entry('B'), 'INSUFFICIENT_MARGIN_AFTER_COSTS'),
                              (entry('A'), 'INVALID_POSITION_ID'),
                              (entry('C', side='SHORT'), 'OPPOSITE_POSITION_EXISTS'),
                              (FixedSignal('LONG', 1, position_id='D'), 'MULTI_ENTRY_REQUIRES_LO_OR_ATO'),
                              (FixedSignal('CLOSE', 2, position_id='A'), 'INVALID_QUANTITY'),
                              (FixedSignal('CLOSE', position_id='missing'), 'EXIT_REQUIRES_POSITION')):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                executor.execute(signal, stamp, stamp, D(1000))
            self.assertEqual(executor.portfolio, original)
            self.assertEqual(executor.lots['A'].active_stop, 994)
        fill, trade = executor.execute(FixedSignal('CLOSE', position_id='A'), stamp, stamp, D(1001))
        self.assertEqual((fill.position_id, trade.position_id), ('A', 'A'))
        self.assertEqual(executor.portfolio.quantity, 0)


if __name__ == '__main__':
    unittest.main()
